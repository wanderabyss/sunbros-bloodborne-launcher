// SPDX-License-Identifier: GPL-2.0-or-later
#include "gpu/shim/bbport_map_spatial.h"
#include "gpu/shadps4/common/draining_queue.h"
#include "gpu/shadps4/video_core/renderer_vulkan/pipeline_cache_data.h"
#include "gpu/shadps4/video_core/renderer_vulkan/vram_pressure.h"
#include <cassert>
#include <atomic>
#include <cstdio>
#include <random>
#include <stdexcept>

int main() {
    // Compare indexed selection to exhaustive culling, including source order,
    // shared cells, negative coordinates, boundary points and oversized boxes.
    std::mt19937 rng(42);
    std::uniform_real_distribution<float> position(-500, 500), extent(0, 80);
    std::vector<BbMap::MapBounds> boxes{{-32,-32,0,0},{0,0,32,32},{-1e7f,-1e7f,1e7f,1e7f}};
    for (int i = 0; i < 500; ++i) {
        float x=position(rng), z=position(rng);
        boxes.push_back({x,z,x+extent(rng),z+extent(rng)});
    }
    BbMap::MapSpatialIndex index; index.Build(boxes);
    const auto compare = [&](BbMap::MapBounds v) {
        std::vector<uint32_t> expected, actual;
        for (uint32_t i=0;i<boxes.size();++i) {
            auto b=boxes[i];
            if (b.x0<=v.x1 && b.x1>=v.x0 && b.z0<=v.z1 && b.z1>=v.z0) expected.push_back(i);
        }
        index.Visit(v,[&](uint32_t i){actual.push_back(i);});
        assert(actual==expected);
    };
    compare({0,0,0,0}); compare({-32,-32,-32,-32}); compare({-1e7f,-1e7f,1e7f,1e7f});
    for(int i=0;i<1000;++i) {float x=position(rng),z=position(rng);compare({x,z,x+extent(rng),z+extent(rng)});}
    index.Build({}); index.Visit({0,0,32,32},[](uint32_t){assert(false);});

    assert(!Vulkan::RtPressureActive(false, 899, 1000));
    assert(Vulkan::RtPressureActive(false, 900, 1000));
    assert(Vulkan::RtPressureActive(true, 870, 1000));
    assert(!Vulkan::RtPressureActive(true, 849, 1000));
    assert(!Vulkan::RtPressureActive(true, 999, 0));
    assert(Vulkan::RtPressureTarget(950,1000,200,180,true)==100);
    assert(Vulkan::RtPressureTarget(950,1000,50,180,true)==0);
    assert(Vulkan::RtPressureTarget(800,1000,200,180,false)==180);
    assert(Vulkan::RtPressureTarget(999,0,200,180,true)==180);
    assert(Vulkan::RtPressureTarget(850,1000,200,180,true)==180);

    std::array<uint8_t,16> uuid{}; uuid[5]=17;
    std::vector<uint8_t> bytes(48);
    uint32_t header[]={32,1,0x10de,0x2684};
    std::memcpy(bytes.data(),header,sizeof(header)); std::memcpy(bytes.data()+16,uuid.data(),16);
    assert(Vulkan::CompatiblePipelineData(bytes,0x10de,0x2684,uuid));
    assert(!Vulkan::CompatiblePipelineData(bytes,0x1002,0x2684,uuid));
    assert(!Vulkan::CompatiblePipelineData(bytes,0x10de,1,uuid));
    bytes[16]^=1; assert(!Vulkan::CompatiblePipelineData(bytes,0x10de,0x2684,uuid));
    bytes.resize(31); assert(!Vulkan::CompatiblePipelineData(bytes,0x10de,0x2684,uuid));

    // Normal shutdown must retain the tail of a long cache-write batch even if
    // an earlier task fails. Serial ordering is observable in the result vector.
    std::vector<int> completed;
    Common::DrainingQueue queue;
    std::promise<void> entered, release;
    auto gate = release.get_future();
    assert(queue.Push(std::packaged_task<void()>{[&] { entered.set_value(); gate.wait(); }}));
    entered.get_future().wait();
    for(int i=0;i<1000;++i) assert(queue.Push(std::packaged_task<void()>{[&,i]{completed.push_back(i);}}));
    assert(queue.Push(std::packaged_task<void()>{[]{throw std::runtime_error("test failure");}}));
    assert(queue.Push(std::packaged_task<void()>{[&]{completed.push_back(1000);}}));
    // Stop begins with the entire batch still queued behind the blocked writer.
    std::thread stopper([&] { queue.Stop(); });
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    bool stopped = false;
    while (!(stopped = !queue.Push(std::packaged_task<void()>{[] {}})) &&
           std::chrono::steady_clock::now() < deadline) std::this_thread::yield();
    release.set_value();
    stopper.join();
    assert(stopped);
    queue.Stop();
    assert(completed.size()==1001);
    for(int i=0;i<=1000;++i) assert(completed[i]==i);
    assert(!queue.Push(std::packaged_task<void()>{[]{}}));
    std::puts("Render maintenance: PASS (spatial equivalence, pressure target, driver identity, FIFO drain)");
}
