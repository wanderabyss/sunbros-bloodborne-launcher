// SPDX-License-Identifier: GPL-2.0-or-later
// Standalone CPU regression checks: no game, Vulkan device or window required.
#include <array>
#include <cassert>
#include <cstdio>
#include "gpu/shadps4/video_core/renderer_vulkan/motion_history.h"
#include "gpu/shadps4/video_core/renderer_vulkan/motion_capture_budget.h"

using namespace Vulkan::Motion;

int main() {
    constexpr uint32_t Mi = 1u << 20;
    for (const char* invalid : {"", "0", "65", "-1", "+16", "16x", " 16", "16 ",
                                "999999999999999999999999"}) {
        assert(ParseCaptureBudget(invalid) == 0);
    }
    assert(ParseCaptureBudget(nullptr) == 0);
    assert(ParseCaptureBudget("1") == Mi && ParseCaptureBudget("64") == 64 * Mi);
    const auto defaults = CaptureBudget::Choose(0, nullptr, true);
    assert(defaults.base == 4 * Mi && defaults.rt == 12 * Mi);
    const auto rt_only = CaptureBudget::Choose(0, "16", true);
    assert(rt_only.Capacity(false) == 4 * Mi && rt_only.Capacity(true) == 16 * Mi);
    assert(CaptureBudget::Choose(8 * Mi, "16", true).rt == 16 * Mi);
    assert(CaptureBudget::Choose(8 * Mi, "bad", true).rt == 8 * Mi);
    assert(CaptureBudget::Choose(0, "65", true).rt == 12 * Mi);
    assert(CaptureBudget::Choose(32 * Mi, "16", true).rt == 32 * Mi);
    assert(CaptureBudget::Choose(0, "64", false).rt == 4 * Mi);
    assert(CaptureBudget::Bytes(16 * Mi) == 512ull * Mi + 16);
    assert(CaptureBudget::Bytes(12 * Mi) == 384ull * Mi + 16);
    // RT reserve survives equal base/RT capacities (legacy override), and a
    // failed growth using the base buffer. Turning RT off restores base policy.
    for (const auto budget : {CaptureBudget::Choose(4 * Mi, nullptr, true), rt_only}) {
        History transition(budget.base);
        Draw world{.instances = 1, .vertices = {0, budget.base}};
        assert(transition.Prepare(world, false, false).store);
        transition.NextFrame();
        transition.SetReserve(CaptureBudget::Reserve(budget.base, true));
        assert(!transition.Prepare(world, false, false).store);
        const uint32_t reserve = transition.Reserved();
        world.vertices.count = budget.base - reserve;
        assert(transition.Prepare(world, false, false).store);
        world.vertices.count = reserve;
        assert(transition.Prepare(world, true).store);
        transition.NextFrame();
        transition.SetReserve(CaptureBudget::Reserve(budget.base, false));
        world.vertices.count = budget.base;
        assert(transition.Prepare(world, false, false).store);
    }
    const std::array<uint16_t, 5> indices{1000, 1007, 1002, 1007, UINT16_MAX};
    const auto range = IndexedRange(std::span(indices), -900, true);
    assert(range.first == 100 && range.count == 8);
    assert(IndexedRange(std::span(indices), -1001, true).count == 0);
    assert(IndexedRange(std::span(indices), 0, false).count == 64536);
    const std::array<uint32_t, 3> large{100000, 100003, UINT32_MAX};
    assert(IndexedRange(std::span(large), 7, true).count == 4);
    assert(IndexedRange(std::span(large), INT32_MAX, true).count == 0);
    const std::array<uint16_t, 1> restart{UINT16_MAX};
    assert(IndexedRange(std::span(restart), 0, true).count == 0);
    assert(IndexedRange(std::span<const uint16_t>{}, 0, false).count == 0);

    Draw draw{.shader = 1, .geometry = 2, .indices = 3, .topology = 4,
              .index_count = 5, .instances = 2, .first_instance = 100,
              .vertices = range};
    History history(32);
    history.NextFrame();
    const auto first = history.Prepare(draw);
    const auto duplicate = history.Prepare(draw);
    assert(first.store && !first.load && first.first_vertex == 100);
    assert(first.first_instance == 100 && first.instances == 2);
    assert(duplicate.store == first.store + 16); // shared geometry, different draw
    assert(history.Used() == 32); // firstInstance must NOT multiply the allocation
    assert(!history.Prepare(draw).store && history.stats.exhausted == 1);
    assert(history.stats.exhausted_capacity == 1 && history.stats.exhausted_reserve == 0);
    history.NextFrame();
    const auto next = history.Prepare(draw);
    assert(next.load == first.store && next.store != first.store);
    assert(history.Prepare(draw).load == duplicate.store);
    history.NextFrame(); // a missing frame invalidates the match
    history.NextFrame();
    assert(!history.Prepare(draw).load);
    // Store only (ray tracing's static world): no load, but the next frame can load it.
    history.NextFrame();
    const auto stored_only = history.Prepare(draw, false, false);
    assert(stored_only.store && !stored_only.load && history.stats.store_only == 1);
    history.NextFrame();
    assert(history.Prepare(draw).load == stored_only.store);

    // A changed index buffer may reference formerly unused holes inside the same min/max.
    // Do not accept that history merely because its addresses/counts stayed the same.
    history.NextFrame();
    auto changed = draw;
    changed.topology++;
    assert(!history.Prepare(changed).load);
    changed = draw;
    changed.first_instance++;
    assert(!history.Prepare(changed).load);
    history.NextFrame();
    changed = draw;
    changed.vertices.first++;
    assert(!history.Prepare(changed).load);

    // A reserve for priority draws (characters): the rest stop short of it.
    History reserved(32, 8);
    reserved.NextFrame();
    Draw small = draw;
    small.instances = 1;
    small.vertices = {0, 12};
    assert(reserved.Prepare(small).store && reserved.Prepare(small).store); // 24 of 24
    assert(!reserved.Prepare(small).store);                                  // the reserve is kept
    small.vertices.count = 8;
    assert(!reserved.Prepare(small).store); // fits total capacity, blocked only by reserve
    assert(reserved.stats.exhausted_reserve == 1 && reserved.Reserved() == 8);
    assert(reserved.Prepare(small, true).store && reserved.Used() == 32);    // a character fits
    assert(!reserved.Prepare(small, true).store);                            // and then it is full
    assert(reserved.stats.exhausted_capacity == 2);
    assert(reserved.stats.exhausted == reserved.stats.exhausted_capacity +
                                       reserved.stats.exhausted_reserve);
    reserved.NextFrame();
    reserved.stats = {}; // optional diagnostics reset must not alter allocation behavior
    assert(reserved.Prepare(small).store && reserved.stats.exhausted == 0);
    assert(History(8, 9).Prepare(small, false).store != 0);                  // reserve > capacity: ignored

    History overflow(32);
    draw.vertices.first = 0;
    draw.vertices.count = INT32_MAX;
    draw.instances = UINT32_MAX;
    draw.first_instance = 0;
    assert(!overflow.Prepare(draw).store);
    assert(overflow.stats.exhausted == 1);
    assert(overflow.stats.exhausted_capacity == 1 && overflow.stats.exhausted_reserve == 0);
    draw.first_instance = 10;
    assert(!overflow.Prepare(draw).store && overflow.stats.invalid == 1);
    draw.first_instance = 0;
    draw.vertices.first = INT32_MAX;
    draw.vertices.count = 2;
    assert(!overflow.Prepare(draw).store && overflow.stats.invalid == 2);

    // Small skeletons: history only while the bone palette changes (weapon spinning).
    History gated(1024);
    const History::GateKey weapon{.shader = 7, .index_count = 3, .instances = 1};
    const auto frame = [&](uint64_t palette) {
        gated.NextFrame();
        return gated.Moving(weapon, palette);
    };
    assert(!gated.Moving(weapon, 1) && gated.stats.still == 1); // first sight
    assert(!frame(1));                    // same bones: camera motion
    assert(frame(2) && frame(3));         // spinning
    assert(!frame(3));                    // stopped
    gated.NextFrame();
    gated.NextFrame();
    assert(!gated.Moving(weapon, 4));     // after a skipped frame: no comparison
    assert(!gated.Moving(weapon, 5));     // second occurrence of the same draw
    assert(ClassifyBuffer(864) == BufferRole::Other && ClassifyBuffer(416) == BufferRole::Other);
    assert(ClassifyBuffer(96) == BufferRole::SmallSkeleton &&
           ClassifyBuffer(384) == BufferRole::SmallSkeleton);
    assert(ClassifyBuffer(656) == BufferRole::Skeleton && ClassifyBuffer(64) == BufferRole::Other);

    // Index ranges: reused between full scans, rescanned every Revalidate frames, trimmed.
    IndexRangeCache ranges;
    uint32_t scans = 0;
    const IndexRangeCache::Key mesh{.address = 0x1000, .count = 3, .index_size = 2};
    const auto scan = [&] {
        ++scans;
        return IndexRangeCache::Result{{4, 3}, 99};
    };
    assert(ranges.Get(mesh, 0, scan).topology == 99 && scans == 1);
    assert(ranges.Get(mesh, IndexRangeCache::Revalidate - 1, scan).range == (VertexRange{4, 3}));
    assert(scans == 1);
    ranges.Get(mesh, IndexRangeCache::Revalidate, scan);
    assert(scans == 2);
    // Draws stored only for ray tracing: verified every RevalidateStatic frames instead.
    const IndexRangeCache::Key world{.address = 0x2000, .count = 3, .index_size = 2};
    ranges.Get(world, 0, scan, IndexRangeCache::RevalidateStatic);
    ranges.Get(world, IndexRangeCache::RevalidateStatic - 1, scan, IndexRangeCache::RevalidateStatic);
    assert(scans == 3);
    ranges.Get(world, IndexRangeCache::RevalidateStatic, scan, IndexRangeCache::RevalidateStatic);
    assert(scans == 4);
    ranges.Trim(IndexRangeCache::RevalidateStatic + IndexRangeCache::Unused + 1);
    assert(ranges.Size() == 0);

    assert(JitterPhases(1920, 1920) == 8);
    assert(JitterPhases(1280, 1920) == 18);
    assert(JitterPhases(960, 1920) == 32);
    assert(JitterPhases(640, 1920) == 72);
    assert(JitterPhases(0, 1920) == 8);
    std::puts("Motion history: PASS (ranges, restart, offsets, matching, capacity, gating, index cache, jitter)");
}
