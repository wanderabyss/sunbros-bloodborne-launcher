// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: hardware ray tracing (see vk_ray_tracing.h).

// First: it sets up Vulkan (beta extensions) before vk_mem_alloc.h pulls in the C headers.
#include "video_core/renderer_vulkan/vk_ray_tracing.h"
#include "video_core/renderer_vulkan/vram_pressure.h"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include <vk_mem_alloc.h>

#include "bbport_frame_times.h"
#include "bbport_settings.h"

#include "video_core/host_shaders/rt_check_comp.h"
#include "video_core/host_shaders/rt_gather_indices_comp.h"
#include "video_core/host_shaders/rt_gather_vertices_comp.h"
#include "video_core/host_shaders/rt_instances_comp.h"
#include "video_core/renderer_vulkan/vk_gpu_profiler.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_object_motion.h"
#include "video_core/renderer_vulkan/vk_platform.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/renderer_vulkan/vk_shader_util.h"

namespace Vulkan {

namespace {

RayTracing* active = nullptr;

struct GatherPush {
    u64 items;
    u64 positions;
    u64 frame;
    u64 sig_vertices;
    u64 errors;
    u32 item_count;
    u32 thread_count;
};

struct InstancesPush {
    u64 items;
    u64 positions;
    u64 frame;
    u64 sig_vertices;
    u64 sig_positions;
    u64 results;
    u64 out_instances;
    u64 stats;
    u64 siblings;
    u32 count;
    u32 pad;
};
static_assert(sizeof(InstancesPush) <= 128);

struct CheckPush {
    float proj[4];
    float size[2];
    float jitter[2];
    u32 mask;
    u32 pad;
    u64 stats;
};

/// rt_common.glsl FrameConstants.
struct FrameConstants {
    float view[12];
    float inv_view[12];
    float proj[4];
    float inv_scale[2];
    float jitter[2];
    float size[2];
    u32 frame_index;
    u32 pad;
    float light[4];
};

const auto& Dispatcher() {
    return VULKAN_HPP_DEFAULT_DISPATCHER;
}

u64 Mix(u64 h, u64 v) {
    h ^= v + 0x9e3779b97f4a7c15ULL + (h << 6) + (h >> 2);
    return h * 0xff51afd7ed558ccdULL;
}

/// Adds the time until it goes out of scope to `sum` (microseconds); nothing when not `on`.
struct CpuTimer {
    double& sum;
    bool on = true;
    std::chrono::steady_clock::time_point start =
        on ? std::chrono::steady_clock::now() : std::chrono::steady_clock::time_point{};
    ~CpuTimer() {
        if (on) {
            sum += std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() -
                                                             start)
                       .count();
        }
    }
};

/// Report lines written to stdout in one call: stdout is unbuffered (src/probe.c), and printf
/// then wrote a long line piece by piece (about 55 ms for the report on the render thread).
class ReportText {
public:
    template <class... Args>
    void Add(const char* format, Args... args) {
        if (used < sizeof(text) - 1) {
            const int n = std::snprintf(text + used, sizeof(text) - used, format, args...);
            used = n > 0 ? std::min(sizeof(text) - 1, used + size_t(n)) : used;
        }
    }
    ~ReportText() {
        std::fwrite(text, 1, used, stdout);
    }

private:
    char text[4096];
    size_t used = 0;
};

u64 EnvNumber(const char* name, u64 fallback) {
    const char* value = std::getenv(name);
    if (!value || !*value) {
        return fallback;
    }
    char* end = nullptr;
    const unsigned long long n = std::strtoull(value, &end, 10);
    return end && *end == '\0' ? u64(n) : fallback;
}

vk::DeviceSize Align(vk::DeviceSize value, vk::DeviceSize alignment) {
    return (value + alignment - 1) / alignment * alignment;
}

VkAccelerationStructureGeometryKHR Triangles(u64 vertices, u32 vertex_count, u64 indices) {
    return {
        .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_GEOMETRY_KHR,
        .geometryType = VK_GEOMETRY_TYPE_TRIANGLES_KHR,
        .geometry = {.triangles = {
            .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_GEOMETRY_TRIANGLES_DATA_KHR,
            .vertexFormat = VK_FORMAT_R32G32B32_SFLOAT,
            .vertexData = {.deviceAddress = vertices},
            .vertexStride = 16,
            .maxVertex = vertex_count - 1,
            .indexType = indices ? VK_INDEX_TYPE_UINT32 : VK_INDEX_TYPE_NONE_KHR,
            .indexData = {.deviceAddress = indices},
        }},
        .flags = VK_GEOMETRY_OPAQUE_BIT_KHR,
    };
}

constexpr VkBuildAccelerationStructureFlagsKHR StaticFlags =
    VK_BUILD_ACCELERATION_STRUCTURE_PREFER_FAST_TRACE_BIT_KHR |
    VK_BUILD_ACCELERATION_STRUCTURE_ALLOW_COMPACTION_BIT_KHR;
constexpr VkBuildAccelerationStructureFlagsKHR DynamicFlags =
    VK_BUILD_ACCELERATION_STRUCTURE_PREFER_FAST_BUILD_BIT_KHR |
    VK_BUILD_ACCELERATION_STRUCTURE_ALLOW_UPDATE_BIT_KHR;

} // namespace

RayTracing* RayTracing::Get() {
    return active;
}

bool RayTracing::Allowed() {
    static const bool allowed = [] {
        const char* value = std::getenv("BB_RT");
        return !(value && value[0] == '0');
    }();
    return allowed;
}

namespace {
/// BB_RT=1: the structure is built whatever the setting (research).
bool Forced() {
    static const bool forced = [] {
        const char* value = std::getenv("BB_RT");
        return value && value[0] == '1';
    }();
    return forced;
}
} // namespace

bool RayTracing::WantedAtStart() {
    return Allowed() && (Forced() || BbSettings::RayTracingWanted());
}

bool RayTracing::Wanted() const {
    const auto effect = BbSettings::RayTracingEffective();
    return available && !setup_failed && (Forced() || effect.ao || effect.shadows);
}

RayTracing::RayTracing(const Instance& instance_, Scheduler& scheduler_, ObjectMotion* motion)
    : instance{instance_}, scheduler{scheduler_}, object_motion{motion} {
    if (!instance.IsRayTracingSupported()) {
        return;
    }
    if (!object_motion || !object_motion->Enabled() || !object_motion->PositionsAddress()) {
        std::printf("Ray tracing: off (it builds on object motion, which is off)\n");
        BbSettings::Get().ray_tracing_supported = false;
        return;
    }
    device = instance.GetDevice();
    budget_bytes = EnvNumber("BB_RT_BUDGET_MB", 768) << 20;
    build_budget = EnvNumber("BB_RT_BUILD_BUDGET", 1u << 20);
    check_every = u32(EnvNumber("BB_RT_CHECK", 8));
    check_mask = u32(EnvNumber("BB_RT_CHECK_MASK", 0x07)); // not the kept structures
    const auto props = instance.GetPhysicalDevice()
                           .getProperties2<vk::PhysicalDeviceProperties2,
                                           vk::PhysicalDeviceAccelerationStructurePropertiesKHR>()
                           .get<vk::PhysicalDeviceAccelerationStructurePropertiesKHR>();
    scratch_alignment = std::max<vk::DeviceSize>(props.minAccelerationStructureScratchOffsetAlignment, 1);
    available = true;
    active = this;
    BbSettings::Get().ray_tracing_small_budget = object_motion->RayTracingBudget() < (12u << 20);
    std::printf("Ray tracing: available (%s at start)\n", WantedAtStart() ? "on" : "off");
}

bool RayTracing::CreateResources() {
    using Usage = vk::BufferUsageFlagBits;
    const auto input = Usage::eAccelerationStructureBuildInputReadOnlyKHR | Usage::eStorageBuffer;
    bool ok = CreateBuffer(gather_positions, vk::DeviceSize(GatherVertices) * 16, input, Host::None) &&
              CreateBuffer(gather_indices, vk::DeviceSize(GatherIndices) * 4, input, Host::None) &&
              CreateBuffer(signatures, vk::DeviceSize(MaxEntries) * 4 * 16, Usage::eStorageBuffer,
                           Host::None) &&
              CreateBuffer(sig_vertices, vk::DeviceSize(MaxEntries) * 16, Usage::eStorageBuffer,
                           Host::None) &&
              CreateBuffer(tlas_instances, vk::DeviceSize(MaxInstances) * 64, input, Host::None) &&
              CreateBuffer(coverage_stats, vk::DeviceSize(MaxEntries) * 16,
                           Usage::eStorageBuffer | Usage::eTransferDst, Host::None);
    for (auto& f : frames) {
        ok = ok && CreateBuffer(f.constants, 256, Usage::eStorageBuffer, Host::Write) &&
             CreateBuffer(f.index_items, vk::DeviceSize(MaxItems) * sizeof(IndexItem),
                          Usage::eStorageBuffer, Host::Write) &&
             CreateBuffer(f.vertex_items, vk::DeviceSize(MaxItems) * sizeof(VertexItem),
                          Usage::eStorageBuffer, Host::Write) &&
             CreateBuffer(f.instance_items, vk::DeviceSize(MaxInstances) * sizeof(InstanceItem),
                          Usage::eStorageBuffer, Host::Write) &&
             CreateBuffer(f.siblings, vk::DeviceSize(SiblingWords) * 4, Usage::eStorageBuffer,
                          Host::Write) &&
             CreateBuffer(f.results, vk::DeviceSize(MaxInstances + MaxItems) * 4,
                          Usage::eStorageBuffer | Usage::eTransferDst, Host::Read);
        if (ok) {
            f.sizes = Check(device.createQueryPool({
                .queryType = vk::QueryType::eAccelerationStructureCompactedSizeKHR,
                .queryCount = MaxItems,
            }));
        }
    }
    // The top level: sized for MaxInstances, rebuilt every frame.
    if (ok) {
        const VkAccelerationStructureGeometryKHR geometry{
            .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_GEOMETRY_KHR,
            .geometryType = VK_GEOMETRY_TYPE_INSTANCES_KHR,
            .geometry = {.instances = {.sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_GEOMETRY_INSTANCES_DATA_KHR}},
        };
        const VkAccelerationStructureBuildGeometryInfoKHR info{
            .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_BUILD_GEOMETRY_INFO_KHR,
            .type = VK_ACCELERATION_STRUCTURE_TYPE_TOP_LEVEL_KHR,
            .flags = VK_BUILD_ACCELERATION_STRUCTURE_PREFER_FAST_BUILD_BIT_KHR,
            .mode = VK_BUILD_ACCELERATION_STRUCTURE_MODE_BUILD_KHR,
            .geometryCount = 1,
            .pGeometries = &geometry,
        };
        const u32 count = MaxInstances;
        VkAccelerationStructureBuildSizesInfoKHR sizes{
            .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_BUILD_SIZES_INFO_KHR};
        Dispatcher().vkGetAccelerationStructureBuildSizesKHR(
            device, VK_ACCELERATION_STRUCTURE_BUILD_TYPE_DEVICE_KHR, &info, &count, &sizes);
        ok = CreateBuffer(tlas_buffer, sizes.accelerationStructureSize,
                          Usage::eAccelerationStructureStorageKHR, Host::None) &&
             EnsureScratch(sizes.buildScratchSize);
        if (ok) {
            const VkAccelerationStructureCreateInfoKHR create{
                .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_CREATE_INFO_KHR,
                .buffer = tlas_buffer.buffer,
                .size = sizes.accelerationStructureSize,
                .type = VK_ACCELERATION_STRUCTURE_TYPE_TOP_LEVEL_KHR,
            };
            VkAccelerationStructureKHR handle{};
            ok = Dispatcher().vkCreateAccelerationStructureKHR(device, &create, nullptr, &handle) ==
                 VK_SUCCESS;
            tlas = handle;
        }
    }
    if (!ok || (!check_pipeline && !CreatePipelines())) {
        std::printf("Ray tracing: setup failed, off\n");
        ReleaseResources();
        setup_failed = true;
        return false;
    }
    entries.resize(MaxEntries);
    swap_stamps.assign(MaxEntries, 0);
    free_slots.reserve(MaxEntries);
    for (u32 i = MaxEntries; i-- > 0;) {
        free_slots.push_back(i);
    }
    lookup.Reserve(MaxEntries);
    enabled = true;
    std::printf("Ray tracing: on - a cached structure per draw (budget %llu MiB, %llu new "
                "triangles a frame), depth check every %u frames\n",
                (unsigned long long)(budget_bytes >> 20), (unsigned long long)build_budget,
                check_every);
    return true;
}

void RayTracing::ReleaseResources() {
    // The GPU may still use them: each goes once it is past the work recorded so far.
    for (u32 s = 0; s < entries.size(); ++s) {
        FreeEntry(s);
    }
    for (auto& c : compact_switched) {
        DeferDestroy(c.old_storage, c.old_blas);
    }
    vk::AccelerationStructureKHR none{};
    for (Buffer* b : {&gather_positions, &gather_indices, &signatures, &sig_vertices,
                      &tlas_instances, &coverage_stats, &scratch}) {
        DeferDestroy(*b, none);
    }
    DeferDestroy(tlas_buffer, tlas);
    for (auto& f : frames) {
        for (Buffer* b : {&f.constants, &f.index_items, &f.vertex_items, &f.instance_items,
                          &f.results, &f.check_counters, &f.siblings}) {
            DeferDestroy(*b, none);
        }
        if (f.sizes) {
            scheduler.DeferOperation([d = device, pool = f.sizes] { d.destroyQueryPool(pool); });
        }
        f = Frame{};
    }
    entries = {};
    swap_stamps = {};
    free_slots = {};
    lookup.Clear();
    occurrences.clear();
    size_cache.clear();
    dynamic_keys.clear();
    failed_keys.clear();
    moving_meshes.clear();
    mesh_slots.clear();
    mismatch_counts.clear();
    pending.clear();
    kept_slots.clear();
    misses.clear();
    previous_misses.clear();
    stale.clear();
    compact_ready.clear();
    compact_switched.clear();
    index_items.clear();
    vertex_items.clear();
    instance_items.clear();
    builds.clear();
    verified.clear();
    index_threads = vertex_threads = 0;
    new_triangles = 0;
    used_bytes = 0;
    pressure_limit = budget_bytes;
    memory_pressure = false;
    pressure_reclaimed = 0;
    evict_after = 0;
    coverage_cleared = false;
    scene_ready = false;
    recorded_frame = previous_recorded = 0;
    sums = {};
    enabled = false;
}

RayTracing::~RayTracing() {
    if (active == this) {
        active = nullptr;
    }
    if (!device || !enabled) {
        return;
    }
    scheduler.Finish();
    for (auto& e : entries) {
        if (e.blas) {
            Dispatcher().vkDestroyAccelerationStructureKHR(device, e.blas, nullptr);
        }
        DestroyBuffer(e.storage);
    }
    if (tlas) {
        Dispatcher().vkDestroyAccelerationStructureKHR(device, tlas, nullptr);
    }
    for (Buffer* b : {&gather_positions, &gather_indices, &signatures, &sig_vertices,
                      &tlas_instances, &coverage_stats, &tlas_buffer, &scratch}) {
        DestroyBuffer(*b);
    }
    for (auto& f : frames) {
        for (Buffer* b : {&f.constants, &f.index_items, &f.vertex_items, &f.instance_items,
                          &f.results, &f.check_counters, &f.siblings}) {
            DestroyBuffer(*b);
        }
        if (f.sizes) {
            device.destroyQueryPool(f.sizes);
        }
    }
}

bool RayTracing::CreateBuffer(Buffer& out, vk::DeviceSize size, vk::BufferUsageFlags usage,
                              Host host, vk::DeviceSize alignment) {
    const VkBufferCreateInfo buffer_ci{
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .size = size,
        .usage = static_cast<VkBufferUsageFlags>(usage | vk::BufferUsageFlagBits::eShaderDeviceAddress),
    };
    VmaAllocationCreateInfo alloc_ci{.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE};
    if (host == Host::Write) {
        // Device-local and host-visible where there is such memory (ReBAR): the passes read it
        // from VRAM, not over PCIe. Written in order (memcpy), never read on the CPU.
        alloc_ci.requiredFlags = VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
        alloc_ci.flags = VMA_ALLOCATION_CREATE_MAPPED_BIT |
                         VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT;
    } else if (host == Host::Read) {
        alloc_ci.usage = VMA_MEMORY_USAGE_AUTO;
        alloc_ci.requiredFlags = VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
        alloc_ci.flags = VMA_ALLOCATION_CREATE_MAPPED_BIT |
                         VMA_ALLOCATION_CREATE_HOST_ACCESS_RANDOM_BIT;
    }
    VkBuffer raw{};
    VmaAllocationInfo info{};
    const VkResult result =
        alignment ? vmaCreateBufferWithAlignment(instance.GetAllocator(), &buffer_ci, &alloc_ci,
                                                 alignment, &raw, &out.allocation, &info)
                  : vmaCreateBuffer(instance.GetAllocator(), &buffer_ci, &alloc_ci, &raw,
                                    &out.allocation, &info);
    if (result != VK_SUCCESS) {
        out = {};
        return false;
    }
    out.buffer = raw;
    out.mapped = info.pMappedData;
    out.size = size;
    out.address = device.getBufferAddress({.buffer = out.buffer});
    return out.address != 0 && (host == Host::None || out.mapped);
}

void RayTracing::DestroyBuffer(Buffer& b) {
    if (b.buffer) {
        vmaDestroyBuffer(instance.GetAllocator(), b.buffer, b.allocation);
    }
    b = {};
}

void RayTracing::DeferDestroy(Buffer& b, vk::AccelerationStructureKHR& structure) {
    // The GPU may still use them: destroyed once it is past the work recorded so far.
    if (b.buffer || structure) {
        scheduler.DeferOperation([d = device, s = VkAccelerationStructureKHR(structure),
                                  allocator = instance.GetAllocator(), buffer = b.buffer,
                                  allocation = b.allocation] {
            if (s) {
                VULKAN_HPP_DEFAULT_DISPATCHER.vkDestroyAccelerationStructureKHR(d, s, nullptr);
            }
            if (buffer) {
                vmaDestroyBuffer(allocator, buffer, allocation);
            }
        });
    }
    b = {};
    structure = vk::AccelerationStructureKHR{};
}

bool RayTracing::EnsureScratch(vk::DeviceSize size) {
    if (scratch.buffer && scratch.size >= size) {
        return true;
    }
    vk::AccelerationStructureKHR none{};
    DeferDestroy(scratch, none);
    return CreateBuffer(scratch, size + size / 4, vk::BufferUsageFlagBits::eStorageBuffer,
                        Host::None, scratch_alignment);
}

bool RayTracing::CreatePipelines() {
    const vk::PushConstantRange push_range{.stageFlags = vk::ShaderStageFlagBits::eCompute,
                                           .size = 128};
    push_only_layout = Check(device.createPipelineLayoutUnique({
        .pushConstantRangeCount = 1,
        .pPushConstantRanges = &push_range,
    }));
    const std::array<vk::DescriptorSetLayoutBinding, 3> bindings = {{
        {.binding = 0, .descriptorType = vk::DescriptorType::eSampledImage,
         .descriptorCount = 1, .stageFlags = vk::ShaderStageFlagBits::eCompute},
        {.binding = 1, .descriptorType = vk::DescriptorType::eAccelerationStructureKHR,
         .descriptorCount = 1, .stageFlags = vk::ShaderStageFlagBits::eCompute},
        {.binding = 2, .descriptorType = vk::DescriptorType::eStorageBuffer,
         .descriptorCount = 1, .stageFlags = vk::ShaderStageFlagBits::eCompute},
    }};
    check_layout = Check(device.createDescriptorSetLayoutUnique({
        .flags = vk::DescriptorSetLayoutCreateFlagBits::ePushDescriptorKHR,
        .bindingCount = u32(bindings.size()),
        .pBindings = bindings.data(),
    }));
    const vk::PushConstantRange check_range{.stageFlags = vk::ShaderStageFlagBits::eCompute,
                                            .size = sizeof(CheckPush)};
    check_pipeline_layout = Check(device.createPipelineLayoutUnique({
        .setLayoutCount = 1,
        .pSetLayouts = &*check_layout,
        .pushConstantRangeCount = 1,
        .pPushConstantRanges = &check_range,
    }));
    const auto make = [&](std::span<const u32> code, vk::PipelineLayout layout) {
        const auto module = CompileSPV(code, device);
        auto pipeline = Check(device.createComputePipelineUnique(
            {}, vk::ComputePipelineCreateInfo{
                    .stage = {.stage = vk::ShaderStageFlagBits::eCompute,
                              .module = module,
                              .pName = "main"},
                    .layout = layout,
                }));
        device.destroyShaderModule(module);
        return pipeline;
    };
    gather_indices_pipeline = make(RT_GATHER_INDICES_COMP, *push_only_layout);
    gather_vertices_pipeline = make(RT_GATHER_VERTICES_COMP, *push_only_layout);
    instances_pipeline = make(RT_INSTANCES_COMP, *push_only_layout);
    check_pipeline = make(RT_CHECK_COMP, *check_pipeline_layout);
    return gather_indices_pipeline && gather_vertices_pipeline && instances_pipeline &&
           check_pipeline;
}

u32 RayTracing::AllocateEntry(u64 key) {
    if (free_slots.empty()) {
        return ~0u;
    }
    const u32 s = free_slots.back();
    free_slots.pop_back();
    Entry& e = entries[s];
    const u32 generation = e.generation + 1;
    e = {};
    e.generation = generation;
    e.key = key;
    lookup.Set(key, s);
    return s;
}

void RayTracing::FreeEntry(u32 s) {
    Entry& e = entries[s];
    if (e.state == State::Free) {
        return;
    }
    used_bytes -= std::min<u64>(used_bytes, e.storage.size);
    DeferDestroy(e.storage, e.blas);
    lookup.EraseIf(e.key, s);
    if (const auto it = mesh_slots.find(e.mesh); it != mesh_slots.end()) {
        auto& slots = it->second;
        if (const auto at = std::find(slots.begin(), slots.end(), s); at != slots.end()) {
            *at = slots.back();
            slots.pop_back();
        }
        if (slots.empty()) {
            mesh_slots.erase(it);
        }
    }
    e.state = State::Free;
    ++e.generation;
    free_slots.push_back(s);
}

bool RayTracing::CreateStructure(Entry& e, vk::DeviceSize size, vk::DeviceSize extra) {
    const vk::DeviceSize total = Align(size, 256) + extra;
    if (!CreateBuffer(e.storage, total,
                      vk::BufferUsageFlagBits::eAccelerationStructureStorageKHR |
                          vk::BufferUsageFlagBits::eAccelerationStructureBuildInputReadOnlyKHR |
                          vk::BufferUsageFlagBits::eStorageBuffer,
                      Host::None, 256)) {
        return false;
    }
    const VkAccelerationStructureCreateInfoKHR create{
        .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_CREATE_INFO_KHR,
        .buffer = e.storage.buffer,
        .size = size,
        .type = VK_ACCELERATION_STRUCTURE_TYPE_BOTTOM_LEVEL_KHR,
    };
    VkAccelerationStructureKHR handle{};
    if (Dispatcher().vkCreateAccelerationStructureKHR(device, &create, nullptr, &handle) !=
        VK_SUCCESS) {
        DestroyBuffer(e.storage);
        return false;
    }
    e.blas = handle;
    e.index_offset = Align(size, 256);
    const VkAccelerationStructureDeviceAddressInfoKHR address_info{
        .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_DEVICE_ADDRESS_INFO_KHR,
        .accelerationStructure = handle,
    };
    e.address = Dispatcher().vkGetAccelerationStructureDeviceAddressKHR(device, &address_info);
    used_bytes += e.storage.size;
    return e.address != 0;
}

void RayTracing::AddDraw(const DrawInput& draw) {
    if (!Active()) {
        return;
    }
    CpuTimer timer{sums.cpu_draws, timed_frame};
    const bool indexed = draw.index_address != 0;
    const u32 count = indexed ? draw.index_count : draw.vertices;
    const u32 instance_count = std::min(draw.instances, MaxInstancesPerDraw);
    if (!draw.store || !draw.vertices || count < 3 || !instance_count ||
        (indexed && draw.index_size != 2 && draw.index_size != 4)) {
        ++skipped;
        return;
    }
    if (frames[slot].recorded) {
        ++skipped; // after this frame's scene was built: it would be dropped unbuilt next frame
        return;
    }
    const u32 triangles = count / 3;
    // Identity: a static draw by its mesh and where it is, so repeated props keep their own
    // structures whichever of them culling leaves in; characters and meshes seen moving by mesh
    // and order in the frame (their placement changes every frame). A small skeleton that
    // animated stays dynamic for a while: no rebuild each time it pauses.
    bool moving = false;
    if (!draw.character) {
        if (draw.dynamic) {
            MarkMoving(draw.key);
            moving = true;
        } else if (!moving_meshes.empty()) {
            const auto it = moving_meshes.find(draw.key);
            moving = it != moving_meshes.end() && frame - it->second < MovingFrames;
        }
    }
    const bool placed = draw.placement != 0 && !draw.dynamic && !moving;
    const u64 base = placed ? Mix(draw.key, draw.placement) : draw.key;
    const u32 occurrence = occurrences[base]++;
    // Instanced draws (foliage, repeated props): a structure per instance. A character drawn
    // instanced (about 5 instances a draw in crowds): one structure with a geometry per instance
    // (their positions follow each other), refit as one: each refit is a build call on the CPU.
    const u32 parts = draw.character ? instance_count : 1;
    for (u32 i = 0; i < instance_count / parts; ++i) {
        if (instance_items.size() >= MaxInstances) {
            ++over_budget;
            return;
        }
        const u64 key = Mix(Mix(base, occurrence), i);
        if (!failed_keys.empty()) {
            if (const auto failed = failed_keys.find(key); failed != failed_keys.end()) {
                if (frame - failed->second < KeyMemoryFrames) {
                    continue;
                }
                failed_keys.erase(failed);
            }
        }
        // Found moving by the depth check (a door, a lift): its pose is not known.
        const bool keyed_dynamic = !dynamic_keys.empty() && dynamic_keys.contains(key);
        const bool dynamic = draw.dynamic || moving || keyed_dynamic;
        const u32 store = draw.store + i * draw.vertices;
        u32 s = ~0u;
        if (const u32 found = lookup.Find(key); found != RtKeyMap::Empty) {
            s = found;
            Entry& e = entries[s];
            if (e.state == State::Pending) {
                continue; // seen twice in a frame (should not happen: keys count occurrences)
            }
            // Its matrix changed by less than the placement's step: it moves (this frame it
            // keeps the structure, freed next frame); and a moving mesh keeps moving.
            if (draw.matrix && e.matrix && e.matrix != draw.matrix && (placed || moving)) {
                MarkMoving(draw.key);
                if (placed && !e.dynamic) {
                    stale.emplace_back(s, e.generation);
                }
            }
            e.matrix = draw.matrix;
            if (e.dynamic != dynamic || e.vertices != draw.vertices ||
                e.index_count != (indexed ? count : 0) || e.parts != parts) {
                FreeEntry(s); // its shape changed: built again
                s = ~0u;
            }
        }
        bool fresh = false;
        if (s == ~0u) {
            // The first build of a frame always fits (a draw larger than the budget builds
            // alone); the memory budget is for static structures (characters always get one).
            if ((!dynamic && new_triangles > 0 && new_triangles + triangles > build_budget) ||
                (!dynamic && used_bytes >= (memory_pressure ? pressure_limit : budget_bytes)) || pending.size() >= MaxNewPerFrame ||
                (pending.size() >= MinNewPerFrame && create_us >= CreateBudgetUs)) {
                ++over_budget;
                continue;
            }
            s = AllocateEntry(key);
            if (s == ~0u) {
                ++over_budget;
                continue;
            }
            Entry& e = entries[s];
            e.mesh = draw.key;
            mesh_slots[e.mesh].push_back(s);
            e.matrix = draw.matrix;
            e.placed = placed;
            e.dynamic = dynamic;
            e.vertices = draw.vertices;
            e.index_count = indexed ? count : 0;
            e.triangles = triangles;
            e.parts = parts;
            const auto create_start = std::chrono::steady_clock::now();
            VkAccelerationStructureBuildSizesInfoKHR sizes{
                .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_BUILD_SIZES_INFO_KHR};
            const u64 shape = Mix(Mix(u64(draw.vertices) << 32 | triangles, parts),
                                  u64(dynamic) << 1 | u64(indexed));
            if (const auto cached = size_cache.find(shape); cached != size_cache.end()) {
                sizes.accelerationStructureSize = cached->second[0];
                sizes.buildScratchSize = cached->second[1];
                sizes.updateScratchSize = cached->second[2];
            } else {
                size_geometries.assign(parts, Triangles(0, draw.vertices, indexed ? 1 : 0));
                size_primitives.assign(parts, triangles);
                const VkAccelerationStructureBuildGeometryInfoKHR info{
                    .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_BUILD_GEOMETRY_INFO_KHR,
                    .type = VK_ACCELERATION_STRUCTURE_TYPE_BOTTOM_LEVEL_KHR,
                    .flags = dynamic ? DynamicFlags : StaticFlags,
                    .mode = VK_BUILD_ACCELERATION_STRUCTURE_MODE_BUILD_KHR,
                    .geometryCount = parts,
                    .pGeometries = size_geometries.data(),
                };
                Dispatcher().vkGetAccelerationStructureBuildSizesKHR(
                    device, VK_ACCELERATION_STRUCTURE_BUILD_TYPE_DEVICE_KHR, &info,
                    size_primitives.data(), &sizes);
                if (size_cache.size() >= MaxEntries) {
                    size_cache.clear();
                }
                size_cache.emplace(shape, std::array{sizes.accelerationStructureSize,
                                                     sizes.buildScratchSize,
                                                     sizes.updateScratchSize});
            }
            // Dynamic structures keep their indices after the structure (refits reuse them).
            const vk::DeviceSize index_bytes = dynamic && indexed ? vk::DeviceSize(count) * 4 : 0;
            const bool created = CreateStructure(e, sizes.accelerationStructureSize, index_bytes);
            create_us += std::chrono::duration<double, std::micro>(
                             std::chrono::steady_clock::now() - create_start)
                             .count();
            if (!created) {
                e.state = State::Pending; // so FreeEntry releases the slot
                FreeEntry(s);
                ++over_budget;
                continue;
            }
            e.build_scratch = sizes.buildScratchSize;
            e.update_scratch = sizes.updateScratchSize;
            e.state = State::Pending;
            pending.push_back(s);
            if (!dynamic) {
                new_triangles += triangles;
            }
            if (placed) {
                misses.push_back({draw.key, draw.origin, s, e.generation});
            }
            last_new_frame = frame;
            fresh = true;
        }
        Entry& e = entries[s];
        e.last_used = frame;
        sums.placed += placed ? 1 : 0;
        e.alpha = draw.alpha_tested;
        e.character = draw.character;
        // World positions: for a new structure, and every frame for a dynamic one.
        u32 vertex_item = ~0u;
        // Dynamic structures are refit every frame within 10 m of the camera (the distance the
        // GPU read back), every 2nd frame within 25 m, else every 4th; in crowds about
        // RefitBudget a frame (each refit is a build call on the CPU). Three frames old at most:
        // the effects' temporal filter lags more.
        bool refit = false;
        if (e.dynamic) {
            ++dynamic_count;
            const u32 crowd = std::min(4u, (last_dynamic_count + RefitBudget - 1) / RefitBudget);
            const u32 stride = std::max({e.distance < 10 ? 1u : e.distance < 25 ? 2u : 4u, crowd, 1u});
            refit = (s + frame) % stride == 0 || frame - e.built >= RebuildFrames;
            // Its bones and placement are those it holds (a corpse, an idle NPC): so are its
            // positions, and neither the gather nor the refit is needed (the periodic rebuild
            // still runs, to tighten boxes earlier refits grew).
            if (refit && !fresh && draw.pose != 0 && draw.pose == e.pose && !keyed_dynamic &&
                frame - e.built < RebuildFrames) {
                refit = false;
                ++sums.refits_unchanged;
            }
        }
        const u32 elements = draw.vertices * parts; // every part's positions, one after another
        if (fresh || refit) {
            if (vertex_items.size() >= MaxItems || vertex_threads + elements > GatherVertices ||
                (fresh && indexed &&
                 (index_items.size() >= MaxItems || (!dynamic && index_threads + count > GatherIndices)))) {
                if (fresh) {
                    pending.pop_back();
                    FreeEntry(s);
                    if (!dynamic) {
                        new_triangles -= triangles;
                    }
                }
                ++over_budget;
                continue;
            }
            vertex_item = u32(vertex_items.size());
            vertex_items.push_back({gather_positions.address + u64(vertex_threads) * 16,
                                    vertex_threads, elements, store, {}});
            vertex_threads += elements;
            e.pose = draw.pose;
        }
        u64 indices = 0;
        if (indexed) {
            indices = e.dynamic ? e.storage.address + e.index_offset : 0;
            if (fresh) {
                if (!e.dynamic) {
                    indices = gather_indices.address + u64(index_threads) * 4;
                }
                const u32 error_slot = u32(frames[slot].built.size());
                frames[slot].built.emplace_back(s, e.generation);
                index_items.push_back({
                    .src = draw.index_address,
                    .dst = indices,
                    .start = index_threads,
                    .count = count,
                    .rebase = s32(s64(draw.base_vertex) - s64(draw.first_vertex)),
                    .vertices = draw.vertices,
                    .index_size = draw.index_size,
                    .sig_slot = e.dynamic ? ~0u : s,
                    .error_slot = error_slot,
                    .pad = 0,
                });
                index_threads += count;
            }
        }
        if (vertex_item != ~0u) {
            const bool rebuild = !fresh && frame - e.built >= RebuildFrames;
            builds.push_back({s, vertex_item, indices, !fresh && !rebuild});
        }
        u32 flags = (indexed ? 0 : InstanceNonIndexed) | (e.alpha ? InstanceAlpha : 0) |
                    (e.character ? InstanceCharacter : 0);
        if (!e.dynamic) {
            flags |= fresh ? InstanceSignature : InstanceVerify;
            if (!fresh && !placed) {
                flags |= InstanceSiblings; // listed in Record, after the frame's last free
            }
        }
        if (fresh) {
            flags |= InstanceNew; // its slot's coverage counts start over, static or dynamic
        }
        verified.emplace_back(flags & InstanceVerify ? s : e.dynamic ? s | DistanceTag : ~0u,
                              e.generation);
        instance_items.push_back({e.address, s, flags, store, draw.vertices, {}});
        sums.triangles += u64(e.triangles) * e.parts;
        sums.alpha += e.alpha ? 1 : 0;
        sums.characters += e.character ? e.parts : 0;
    }
}

void RayTracing::ReadResults(Frame& f) {
    if (!f.recorded) {
        f.verified.clear();
        f.built.clear();
        f.queried.clear();
        f.checked = false;
        return;
    }
    f.recorded = false;
    const auto* words = static_cast<const u32*>(f.results.mapped);
    if (f.checked) {
        const auto* c = static_cast<const u32*>(f.check_counters.mapped);
        for (u32 i = 0; i < 5; ++i) {
            sums.check[i] += c[i];
        }
        f.checked = false;
    }
    // Static structures that no longer match their draw.
    const u64 swap_pass = frame + 1; // swap_stamps: 0 is never a pass
    for (size_t i = 0; i < f.verified.size(); ++i) {
        const auto [s, generation] = f.verified[i];
        if (s != ~0u && (s & DistanceTag)) {
            Entry& e = entries[s & ~DistanceTag];
            if (e.generation == generation) {
                e.distance = words[i];
            }
            continue;
        }
        if (s == ~0u || !words[i]) {
            continue;
        }
        Entry& e = entries[s];
        if (e.state != State::Ready || e.generation != generation) {
            continue;
        }
        if (words[i] & SiblingMatch) {
            // The instance was another structure of its mesh (culling changed which instance
            // is which): the two swap keys instead of being built again. A slot swaps once a
            // pass (two instances that traded places both report it).
            const u32 j = words[i] & ~SiblingMatch;
            const auto touched = [&](u32 slot) { return swap_stamps[slot] == swap_pass; };
            // The structure listed then, not one built in its slot since.
            const auto listed = std::find_if(
                f.siblings_listed.begin(), f.siblings_listed.end(),
                [j](const auto& l) { return l.first == j; });
            if (j < entries.size() && j != s && !touched(s) && !touched(j) &&
                listed != f.siblings_listed.end() && entries[j].generation == listed->second) {
                Entry& other = entries[j];
                if (other.state == State::Ready && !other.dynamic && !other.placed &&
                    other.mesh == e.mesh) {
                    std::swap(e.key, other.key);
                    lookup.Set(e.key, s);
                    lookup.Set(other.key, j);
                    swap_stamps[s] = swap_stamps[j] = swap_pass;
                    ++sums.rematched;
                }
            }
            continue;
        }
        ++sums.mismatches;
        sums.mismatches_placed += e.placed ? 1 : 0;
        const u64 key = e.key;
        FreeEntry(s);
        auto& [count, last] = mismatch_counts[key];
        count = last && frame - last < MismatchWindow ? count + 1 : 1;
        last = frame;
        if (count >= MismatchesToDynamic) {
            dynamic_keys[key] = frame; // a door, a lift, a moving platform
            mismatch_counts.erase(key);
            ++sums.to_dynamic;
        }
    }
    // Builds whose indices were out of range.
    const u32* errors = words + MaxInstances;
    for (size_t i = 0; i < f.built.size(); ++i) {
        const auto [s, generation] = f.built[i];
        if (!errors[i]) {
            continue;
        }
        ++sums.errors;
        Entry& e = entries[s];
        if (e.state != State::Free && e.generation == generation) {
            failed_keys[e.key] = frame;
            FreeEntry(s);
        }
    }
    // Compacted sizes of static builds: the copies are recorded in the next Record.
    if (!f.queried.empty()) {
        std::vector<u64> sizes(f.queried.size());
        const auto result = device.getQueryPoolResults(
            f.sizes, 0, u32(sizes.size()), sizes.size() * sizeof(u64), sizes.data(), sizeof(u64),
            vk::QueryResultFlagBits::e64);
        if (result == vk::Result::eSuccess) {
            for (size_t i = 0; i < f.queried.size(); ++i) {
                const auto [s, generation] = f.queried[i];
                Entry& e = entries[s];
                if (e.state == State::Ready && e.generation == generation && sizes[i] &&
                    Align(sizes[i], 256) < e.storage.size) {
                    compact_ready.push_back({s, generation, sizes[i]});
                }
            }
        }
    }
    f.verified.clear();
    f.built.clear();
    f.queried.clear();
}

bool RayTracing::Evict(u64 target) {
    // Not drawn for a while, or over the memory budget: the least recently drawn first (never
    // one drawn in the frames the GPU may still be working on).
    auto& candidates = evict_candidates;
    candidates.clear();
    for (u32 s = 0; s < MaxEntries; ++s) {
        const Entry& e = entries[s];
        if (e.state == State::Ready && frame - e.last_used > FrameSlots) {
            candidates.emplace_back(e.last_used, s);
        }
    }
    std::sort(candidates.begin(), candidates.end());
    bool freed = false;
    u32 count = 0;
    for (const auto& [last_used, s] : candidates) {
        if (frame - last_used <= UnusedFrames && used_bytes <= target) {
            break;
        }
        FreeEntry(s);
        ++sums.evicted;
        freed = true;
        if (++count == 128) break; // amortize a long-session sweep over frames
    }
    return freed;
}

void RayTracing::MarkMoving(u64 mesh) {
    const auto [it, added] = moving_meshes.try_emplace(mesh, frame);
    if (added || frame - it->second >= MovingFrames) {
        // Its old structures are no off-screen casters (they would be left where it was): out
        // of the kept list, without a rescan of every structure.
        std::erase_if(kept_slots, [this, mesh](u32 s) { return entries[s].mesh == mesh; });
        ++sums.started_moving;
    }
    it->second = frame;
}

void RayTracing::DetectMoves() {
    // A placement-keyed structure built this frame within NearMove of one built last frame for
    // the same mesh that was not drawn this frame: the object moved (a weapon, a thrown
    // object, a door that started fast). Both copies go; the mesh is keyed as moving.
    if (!misses.empty() && !previous_misses.empty()) {
        std::sort(previous_misses.begin(), previous_misses.end(),
                  [](const Miss& a, const Miss& b) { return a.mesh < b.mesh; });
        for (const Miss& m : misses) {
            auto p = std::lower_bound(previous_misses.begin(), previous_misses.end(), m.mesh,
                                      [](const Miss& a, u64 mesh) { return a.mesh < mesh; });
            for (; p != previous_misses.end() && p->mesh == m.mesh; ++p) {
                const Entry& e = entries[p->slot];
                if (e.state == State::Free || e.generation != p->generation || e.last_used == frame) {
                    continue;
                }
                const float dx = m.origin[0] - p->origin[0], dy = m.origin[1] - p->origin[1],
                            dz = m.origin[2] - p->origin[2];
                if (dx * dx + dy * dy + dz * dz > NearMove * NearMove) {
                    continue;
                }
                MarkMoving(m.mesh);
                stale.emplace_back(p->slot, p->generation);
                stale.emplace_back(m.slot, m.generation);
                break;
            }
        }
    }
    previous_misses.swap(misses);
    misses.clear();
}

void RayTracing::OnFrameStart() {
    // BB_TEST_MARK_FILE=<file> (scripted tests, scripts\ingame-session.ps1): when it appears,
    // its text goes to the log as "Mark: <text>" and the file is removed; a test's steps split
    // the log there. Also without ray tracing (BB_RT=0 runs).
    static const char* mark_file = std::getenv("BB_TEST_MARK_FILE");
    if (mark_file && ++mark_file_frames % 16 == 0) {
        if (FILE* file = std::fopen(mark_file, "r")) {
            char text[256] = {};
            const size_t n = std::fread(text, 1, sizeof(text) - 1, file);
            std::fclose(file);
            std::remove(mark_file);
            text[n] = 0;
            std::printf("Mark: %s (frame %llu)\n", text, (unsigned long long)mark_file_frames);
            BbFrameTimes::Line('m', text);
        }
    }
    if (!available) {
        return;
    }
    // Last frame's top level and camera are not this frame's: Record sets it again.
    scene_ready = false;
    // BB_RT_LEVEL_FILE=<file> holding a ray tracing level (0 Off .. 5 Custom), for Custom
    // optionally followed by the AO and moon shadow tiers (0 Off .. 4 Ultra), read about once a
    // second: switches them as the menu does (scripted tests of live switching).
    static const char* level_file = std::getenv("BB_RT_LEVEL_FILE");
    if (level_file && ++level_file_frames % 64 == 0) {
        if (FILE* file = std::fopen(level_file, "r")) {
            int level = -1, ao = -1, shadows = -1;
            const int read = std::fscanf(file, "%d %d %d", &level, &ao, &shadows);
            auto& settings = BbSettings::Get();
            if (read >= 1 && level >= 0 && level < BbSettings::RtQualityCount) {
                settings.ray_tracing = level;
            }
            if (read == 3 && ao >= 0 && ao < BbSettings::TierCount && shadows >= 0 &&
                shadows < BbSettings::TierCount) {
                settings.rt_ao_quality = ao;
                settings.rt_shadow_quality = shadows;
            }
            std::fclose(file);
        }
    }
    // On while the setting turns an effect on (or BB_RT=1): set up at the first such frame,
    // released ReleaseFrames after it was switched off (kept if it is switched on before).
    const auto effect = BbSettings::RayTracingEffective();
    const bool want = Forced() || effect.ao || effect.shadows;
    if (want && !enabled && !setup_failed) {
        CreateResources();
    }
    if (!want || !enabled) {
        on.store(false, std::memory_order_relaxed);
        if (enabled && ++off_frames >= ReleaseFrames) {
            ReleaseResources();
            std::printf("Ray tracing: off, its structures and buffers released\n");
        }
        return;
    }
    off_frames = 0;
    on.store(true, std::memory_order_relaxed);
    CpuTimer timer{sums.cpu_frame};
    // Structures allocated last frame but never built (no Record): dropped.
    for (const u32 s : pending) {
        FreeEntry(s);
    }
    pending.clear();
    // Static structures of objects that moved: last frame was their last.
    DetectMoves();
    for (const auto& [s, generation] : stale) {
        if (entries[s].generation == generation) {
            FreeEntry(s);
        }
    }
    stale.clear();
    // A compacted copy switched to but never recorded: back to the original.
    for (const auto& c : compact_switched) {
        Entry& e = entries[c.slot];
        if (e.generation == c.generation) {
            used_bytes -= std::min<u64>(used_bytes, e.storage.size);
            DeferDestroy(e.storage, e.blas);
            e.storage = c.old_storage;
            e.blas = c.old_blas;
            e.address = c.old_address;
            e.compacting = false;
        } else {
            Buffer old = c.old_storage;
            vk::AccelerationStructureKHR old_blas = c.old_blas;
            used_bytes -= std::min<u64>(used_bytes, old.size);
            DeferDestroy(old, old_blas);
        }
    }
    compact_switched.clear();

    ++frame;
    slot = u32(frame % FrameSlots);
    // Per-draw CPU time (AddDraw, the rasterizer's object motion) is taken in one frame in
    // TimedStride, so that timing a few thousand draws costs little; the report scales it up.
    if (timed_frame) {
        ++sums.timed_frames; // the frame that just ended
    }
    timed_frame = frame % TimedStride == 0;
    Frame& f = frames[slot];
    // This slot's buffers were last used FrameSlots frames ago, and its camera read as the
    // previous one by the frame after; normally long done.
    {
        CpuTimer wait_timer{sums.cpu_wait};
        if (f.tick && !scheduler.IsFree(f.tick)) {
            scheduler.Wait(f.tick);
        }
        if (const u64 next = frames[(slot + 1) % FrameSlots].tick; next && !scheduler.IsFree(next)) {
            scheduler.Wait(next);
        }
    }
    f.tick = 0;
    ReadResults(f);
    // Texture/buffer collectors already run automatically. RT also responds to
    // device-wide pressure, including allocations outside its own fixed budget.
    if (frame % 60 == 0 && instance.CanReportMemoryUsage()) {
        const u64 usage = instance.GetDeviceMemoryUsage();
        const u64 budget = instance.GetDeviceMemoryBudgetNow();
        memory_pressure = RtPressureActive(memory_pressure, usage, budget);
        pressure_limit = RtPressureTarget(usage, budget, used_bytes, budget_bytes, memory_pressure);
        const u64 before = used_bytes;
        Evict(memory_pressure ? pressure_limit : budget_bytes * 9 / 10);
        pressure_reclaimed += before - used_bytes;
        if (frame % 600 == 0) {
            std::printf("RT memory sweep: usage %llu / %llu MiB, pressure=%u, RT %llu MiB, "
                        "static limit %llu MiB, retired %llu MiB (GPU-deferred)\n",
                        (unsigned long long)(usage >> 20), (unsigned long long)(budget >> 20),
                        unsigned(memory_pressure), (unsigned long long)(used_bytes >> 20),
                        (unsigned long long)(pressure_limit >> 20),
                        (unsigned long long)(pressure_reclaimed >> 20));
            pressure_reclaimed = 0;
        }
    } else if ((frame % 60 == 0) || (used_bytes > budget_bytes && frame >= evict_after)) {
        if (!Evict(budget_bytes * 9 / 10) && used_bytes > budget_bytes)
            evict_after = frame + EvictRetryFrames;
    }
    if (frame % 60 == 30) { // not in the frame of the periodic Evict
        // Off-screen casters: recently drawn static structures, the most recent first; not
        // those of meshes that move (they would be left where the object was).
        kept_slots.clear();
        for (u32 s = 0; s < MaxEntries; ++s) {
            const Entry& e = entries[s];
            if (e.state != State::Ready || e.dynamic || frame - e.last_used > KeepFrames) {
                continue;
            }
            if (!moving_meshes.empty()) {
                const auto it = moving_meshes.find(e.mesh);
                if (it != moving_meshes.end() && frame - it->second < MovingFrames) {
                    continue;
                }
            }
            kept_slots.push_back(s);
        }
        if (kept_slots.size() > MaxKept) {
            std::partial_sort(kept_slots.begin(), kept_slots.begin() + MaxKept, kept_slots.end(),
                              [this](u32 a, u32 b) { return entries[a].last_used > entries[b].last_used; });
            kept_slots.resize(MaxKept);
        }
    }
    if (frame % 600 == 0) {
        std::erase_if(mismatch_counts,
                      [this](const auto& m) { return frame - m.second.second > MismatchWindow; });
        const auto expired = [this](const auto& k) { return frame - k.second >= KeyMemoryFrames; };
        std::erase_if(dynamic_keys, expired);
        std::erase_if(failed_keys, expired);
        std::erase_if(moving_meshes,
                      [this](const auto& m) { return frame - m.second >= MovingFrames; });
    }
    // Compacted copies: created now, so this frame's instances use them; Record copies into
    // them before its top level.
    // At most MaxCompactPerFrame a frame (area entry readies hundreds at once).
    const size_t compact_now = std::min<size_t>(compact_ready.size(), MaxCompactPerFrame);
    for (size_t c = 0; c < compact_now; ++c) {
        const auto [s, generation, size] = compact_ready[c];
        Entry& e = entries[s];
        if (e.state != State::Ready || e.compacting || e.generation != generation) {
            continue;
        }
        Entry copy{};
        if (!CreateStructure(copy, size, 0)) {
            continue;
        }
        compact_switched.push_back({s, e.generation, e.storage, e.blas, e.address});
        sums.compacted_before += e.storage.size;
        sums.compacted_after += copy.storage.size;
        e.storage = copy.storage;
        e.blas = copy.blas;
        e.address = copy.address;
        e.compacting = true;
    }
    compact_ready.erase(compact_ready.begin(), compact_ready.begin() + compact_now);

    occurrences.clear();
    create_us = 0.0;
    index_items.clear();
    vertex_items.clear();
    instance_items.clear();
    builds.clear();
    verified.clear();
    index_threads = vertex_threads = 0;
    new_triangles = 0;
    last_dynamic_count = dynamic_count;
    dynamic_count = 0;
    sums.skipped += skipped;
    sums.over_budget += over_budget;
    skipped = over_budget = 0;

    if (frame % ReportFrames == 0) {
        ReportText report;
        // Draws object motion had no room for are missing from the scene.
        const u64 dropped = object_motion->DroppedDraws() - reported_dropped;
        reported_dropped += dropped;
        const auto capture = object_motion->TakeCaptureReport();
        if (dropped && !warned_dropped) {
            warned_dropped = true;
            report.Add("Ray tracing: object motion's capture is full: %llu draws in the last %llu "
                        "frames are missing from the scene (see capture limits below)\n",
                        (unsigned long long)dropped, (unsigned long long)ReportFrames);
        }
        report.Add("Ray tracing capture: %llu parameter-slot drops, %llu vertex-capacity drops, "
                   "%llu character-reserve drops; peak slots %u/%u, peak vertices %u; "
                   "current capacity %u (%u reserved, %.2f MiB positions), largest rejected draw %llu vertices "
                   "(BB_RT_CAPTURE_BUDGET changes RT vertex capacity only; 15%% character reserve)\n",
                   (unsigned long long)capture.parameter_drops,
                   (unsigned long long)capture.capacity_drops,
                   (unsigned long long)capture.reserve_drops, capture.peak_parameters,
                   ObjectMotion::CaptureReport::ParameterCapacity, capture.peak_vertices,
                   capture.vertex_capacity, capture.reserved_vertices,
                   double((1 + 2 * u64(capture.vertex_capacity)) * 16) / (1u << 20),
                   (unsigned long long)capture.largest_rejected_vertices);
        const u64 checked = sums.check[0];
        const auto pct = [checked](u64 n) { return checked ? 100.0 * double(n) / double(checked) : 0.0; };
        const double n = double(std::max<u64>(sums.frames, 1));
        u32 live = 0;
        for (const auto& e : entries) {
            live += e.state == State::Ready ? 1 : 0;
        }
        size_t moving = 0;
        for (const auto& [mesh, last] : moving_meshes) {
            moving += frame - last < MovingFrames ? 1 : 0;
        }
        report.Add(
            "Ray tracing: %llu frames, %.0f instances (%.0f placed, %.0f alpha-tested, %.0f characters, %.0f kept) and %.0f "
            "triangles a frame; %u structures (%.1f MiB); built %llu (%.0f triangles), refit %llu (%llu more unchanged), rebuilt %llu, compacted %llu "
            "(%.1f -> %.1f MiB), moved %llu (%llu placed, %llu matched to a sibling, %llu now dynamic), %zu meshes moving (%llu new), "
            "evicted %llu, bad indices %llu, over budget %llu, skipped %llu, dropped %llu draws",
            (unsigned long long)sums.frames, double(sums.instances) / n, double(sums.placed) / n,
            double(sums.alpha) / n,
            double(sums.characters) / n, double(sums.kept) / n, double(sums.triangles) / n, live, double(used_bytes) / (1024.0 * 1024.0),
            (unsigned long long)sums.builds, double(sums.built_triangles),
            (unsigned long long)sums.refits, (unsigned long long)sums.refits_unchanged,
            (unsigned long long)sums.rebuilds,
            (unsigned long long)sums.compacted, double(sums.compacted_before) / (1024.0 * 1024.0),
            double(sums.compacted_after) / (1024.0 * 1024.0), (unsigned long long)sums.mismatches,
            (unsigned long long)sums.mismatches_placed, (unsigned long long)sums.rematched,
            (unsigned long long)sums.to_dynamic, moving,
            (unsigned long long)sums.started_moving, (unsigned long long)sums.evicted,
            (unsigned long long)sums.errors, (unsigned long long)sums.over_budget,
            (unsigned long long)sums.skipped, (unsigned long long)dropped);
        if (checked) {
            report.Add("; depth check of %llu pixels: %.1f%% match, %.1f%% hit in front, %.1f%% "
                        "behind, %.1f%% missed",
                        (unsigned long long)checked, pct(sums.check[1]), pct(sums.check[2]),
                        pct(sums.check[3]), pct(sums.check[4]));
        }
        report.Add("\n");
        const double per_frame = 1.0 / double(ReportFrames);
        const double per_timed = sums.timed_frames ? 1.0 / double(sums.timed_frames) : 0.0;
        const auto& m = sums.cpu_motion;
        const double draws = sums.cpu_draws * per_timed;
        const double motion = (m[0] + m[1] + m[2] + m[3]) * per_timed;
        report.Add("Ray tracing CPU: %.0f us a frame (draws %.0f, object motion %.0f: gate %.0f, "
                    "index ranges %.0f, history %.0f, placement %.0f; record %.0f, frame start "
                    "%.0f of which waiting for the GPU %.0f, effects %.0f)\n",
                    draws + motion +
                        (sums.cpu_record + sums.cpu_frame + sums.cpu_effects) * per_frame,
                    draws, motion, m[0] * per_timed, m[1] * per_timed, m[2] * per_timed,
                    m[3] * per_timed, sums.cpu_record * per_frame, sums.cpu_frame * per_frame,
                    sums.cpu_wait * per_frame, sums.cpu_effects * per_frame);
        sums = {};
    }
}

void RayTracing::Record(vk::CommandBuffer cmdbuf, vk::ImageView depth_view, u32 width, u32 height,
                        const Camera& camera) {
    if (!Active() || camera.proj[0] == 0.0f || camera.proj[1] == 0.0f) {
        return;
    }
    CpuTimer timer{sums.cpu_record};
    const auto record_start = std::chrono::steady_clock::now();
    Frame& f = frames[slot];
    if (f.recorded) {
        return; // this frame was built already
    }
    scene_ready = false;
    if (instance_items.empty()) {
        return;
    }
    f.recorded = true;
    // Structures kept though not drawn this frame (off-screen casters): no positions this frame,
    // so no check; their stored signature places them for the distance test.
    for (const u32 s : kept_slots) {
        const Entry& e = entries[s];
        if (instance_items.size() >= MaxInstances) {
            break;
        }
        if (e.state != State::Ready || e.dynamic || e.last_used == frame ||
            frame - e.last_used > KeepFrames) {
            continue;
        }
        instance_items.push_back({e.address, s, InstanceKept | (e.alpha ? InstanceAlpha : 0), 0,
                                  e.vertices, {}});
        verified.emplace_back(~0u, e.generation);
        ++sums.kept;
        sums.triangles += e.triangles;
        sums.alpha += e.alpha ? 1 : 0;
    }
    // Sibling lists for the instances that may have swapped (InstanceSiblings): each mesh's
    // Ready static structures, written once a frame per mesh. Here, after the frame's last free,
    // so every listed structure stays alive while this frame's top level uses it.
    sibling_lists.clear();
    f.siblings_listed.clear();
    auto* sibling_words = static_cast<u32*>(f.siblings.mapped);
    u32 sibling_used = 0;
    for (auto& item : instance_items) {
        if (!(item.flags & InstanceSiblings)) {
            continue;
        }
        const u64 mesh = entries[item.custom].mesh;
        u32& listed = sibling_lists[mesh]; // offset + 1, count in the high half
        if (!listed) {
            const u32 first = sibling_used;
            u32 count = 0;
            if (const auto it = mesh_slots.find(mesh); it != mesh_slots.end()) {
                for (const u32 j : it->second) {
                    const Entry& o = entries[j];
                    if (count >= MaxSiblings || (sibling_used + 1) * 3 > SiblingWords) {
                        break;
                    }
                    // Not those keyed by placement: a swap is for repeated meshes culling
                    // reorders.
                    if (o.state != State::Ready || o.dynamic || o.compacting || o.placed) {
                        continue;
                    }
                    f.siblings_listed.emplace_back(j, o.generation);
                    sibling_words[sibling_used * 3] = j;
                    sibling_words[sibling_used * 3 + 1] = u32(o.address);
                    sibling_words[sibling_used * 3 + 2] = u32(o.address >> 32);
                    ++sibling_used;
                    ++count;
                }
            }
            listed = (count << 16 | (first + 1));
        }
        item.siblings = (listed & 0xFFFF) - 1;
        item.sibling_count = listed >> 16;
        if (item.sibling_count < 2) {
            item.flags &= ~InstanceSiblings;
        }
    }
    f.verified = verified;
    previous_recorded = recorded_frame;
    recorded_frame = frame;
    // BB_GPU_PROFILE: the ray tracing passes get their own labels, then the caller's continues.
    auto* profiler = GpuProfiler::Get();
    const u64 resume = profiler ? profiler->Current() : 0;
    if (profiler) {
        profiler->Mark(0xF5B0'0001ull, [] { return std::string{"ray tracing: structure"}; });
    }

    // Inputs of the passes, in this slot's host-visible buffers.
    FrameConstants constants{};
    std::memcpy(constants.view, camera.view.data(), sizeof(constants.view));
    std::memcpy(constants.inv_view, camera.inv_view.data(), sizeof(constants.inv_view));
    std::memcpy(constants.proj, camera.proj.data(), sizeof(constants.proj));
    constants.inv_scale[0] = 1.0f / camera.proj[0];
    constants.inv_scale[1] = 1.0f / camera.proj[1];
    constants.jitter[0] = camera.jitter[0];
    constants.jitter[1] = camera.jitter[1];
    constants.size[0] = float(width);
    constants.size[1] = float(height);
    constants.frame_index = u32(frame);
    constants.light[0] = camera.light[0];
    constants.light[1] = camera.light[1];
    constants.light[2] = camera.light[2];
    std::memcpy(f.constants.mapped, &constants, sizeof(constants));
    std::memcpy(f.index_items.mapped, index_items.data(), index_items.size() * sizeof(IndexItem));
    std::memcpy(f.vertex_items.mapped, vertex_items.data(),
                vertex_items.size() * sizeof(VertexItem));
    std::memcpy(f.instance_items.mapped, instance_items.data(),
                instance_items.size() * sizeof(InstanceItem));

    using Stage = vk::PipelineStageFlagBits2;
    using Access = vk::AccessFlagBits2;
    const auto barrier = [&](vk::PipelineStageFlags2 src, vk::AccessFlags2 src_access,
                             vk::PipelineStageFlags2 dst, vk::AccessFlags2 dst_access) {
        const vk::MemoryBarrier2 b{.srcStageMask = src, .srcAccessMask = src_access,
                                   .dstStageMask = dst, .dstAccessMask = dst_access};
        cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &b});
    };
    const auto as_stage = Stage::eAccelerationStructureBuildKHR;
    const auto as_rw = Access::eAccelerationStructureReadKHR | Access::eAccelerationStructureWriteKHR;
    // 1. The G-buffer's position stores, the index uploads, and last frame's builds and ray
    // queries (they use the same buffers) come first.
    barrier(Stage::eVertexShader | Stage::eTransfer | as_stage | Stage::eComputeShader,
            Access::eShaderWrite | Access::eTransferWrite | Access::eShaderRead | as_rw,
            Stage::eComputeShader | as_stage | Stage::eTransfer,
            Access::eShaderRead | Access::eShaderWrite | as_rw | Access::eTransferWrite);

    if (!coverage_cleared) {
        cmdbuf.fillBuffer(coverage_stats.buffer, 0, VK_WHOLE_SIZE, 0);
        barrier(Stage::eTransfer, Access::eTransferWrite, Stage::eComputeShader,
                Access::eShaderRead | Access::eShaderWrite);
        coverage_cleared = true;
    }

    // 2. Compacted copies made this frame (OnFrameStart switched the instances to them).
    bool copied = false;
    for (const auto& c : compact_switched) {
        Buffer old = c.old_storage;
        vk::AccelerationStructureKHR old_blas = c.old_blas;
        Entry& e = entries[c.slot];
        if (e.generation != c.generation) {
            // Dropped since (its copy went with it).
            used_bytes -= std::min<u64>(used_bytes, old.size);
            DeferDestroy(old, old_blas);
            continue;
        }
        const VkCopyAccelerationStructureInfoKHR copy{
            .sType = VK_STRUCTURE_TYPE_COPY_ACCELERATION_STRUCTURE_INFO_KHR,
            .src = c.old_blas,
            .dst = e.blas,
            .mode = VK_COPY_ACCELERATION_STRUCTURE_MODE_COMPACT_KHR,
        };
        Dispatcher().vkCmdCopyAccelerationStructureKHR(cmdbuf, &copy);
        used_bytes -= std::min<u64>(used_bytes, old.size);
        DeferDestroy(old, old_blas);
        e.compacting = false;
        ++sums.compacted;
        copied = true;
    }
    compact_switched.clear();
    if (copied) {
        // The top level reads them (also when no build of this frame puts a barrier first).
        barrier(as_stage, Access::eAccelerationStructureWriteKHR, as_stage, as_rw);
    }

    // 3. Build inputs: rebased indices and world positions.
    if (profiler) {
        profiler->Mark(0xF5B0'0010ull + 2, [] { return std::string{"ray tracing: structure: gather"}; });
    }
    // The build error words start at zero: cleared here on the CPU (the GPU finished this slot's
    // last frame before OnFrameStart read it; the memory is coherent), not by a fill and barrier.
    if (!f.built.empty()) {
        std::memset(static_cast<u8*>(f.results.mapped) + size_t(MaxInstances) * 4, 0,
                    f.built.size() * 4);
    }
    GatherPush gather{
        .items = f.index_items.address,
        .positions = object_motion->PositionsAddress(),
        .frame = f.constants.address,
        .sig_vertices = sig_vertices.address,
        .errors = f.results.address + u64(MaxInstances) * 4,
        .item_count = u32(index_items.size()),
        .thread_count = index_threads,
    };
    if (index_threads) {
        cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, *gather_indices_pipeline);
        cmdbuf.pushConstants(*push_only_layout, vk::ShaderStageFlagBits::eCompute, 0,
                             sizeof(gather), &gather);
        cmdbuf.dispatch((index_threads + 255) / 256, 1, 1);
    }
    if (vertex_threads) {
        gather.items = f.vertex_items.address;
        gather.item_count = u32(vertex_items.size());
        gather.thread_count = vertex_threads;
        cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, *gather_vertices_pipeline);
        cmdbuf.pushConstants(*push_only_layout, vk::ShaderStageFlagBits::eCompute, 0,
                             sizeof(gather), &gather);
        cmdbuf.dispatch((vertex_threads + 255) / 256, 1, 1);
    }
    barrier(Stage::eComputeShader, Access::eShaderWrite, Stage::eComputeShader | as_stage,
            Access::eShaderRead | Access::eShaderWrite);

    // 4. Top-level instances, and the check of the static structures.
    if (profiler) {
        profiler->Mark(0xF5B0'0010ull + 3, [] { return std::string{"ray tracing: structure: instances"}; });
    }
    const InstancesPush instances_push{
        .items = f.instance_items.address,
        .positions = object_motion->PositionsAddress(),
        .frame = f.constants.address,
        .sig_vertices = sig_vertices.address,
        .sig_positions = signatures.address,
        .results = f.results.address,
        .out_instances = tlas_instances.address,
        .stats = coverage_stats.address,
        .siblings = f.siblings.address,
        .count = u32(instance_items.size()),
        .pad = 0,
    };
    cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, *instances_pipeline);
    cmdbuf.pushConstants(*push_only_layout, vk::ShaderStageFlagBits::eCompute, 0,
                         sizeof(instances_push), &instances_push);
    cmdbuf.dispatch((instances_push.count + 63) / 64, 1, 1);

    // 5. Bottom levels: new structures, refits and rebuilds, in batches that fit the scratch.
    if (profiler) {
        profiler->Mark(0xF5B0'0010ull + 4, [] { return std::string{"ray tracing: structure: bottom levels"}; });
    }
    auto& batches = record_batches;
    auto& scratch_offsets = record_scratch_offsets;
    batches.clear();
    scratch_offsets.resize(builds.size());
    vk::DeviceSize batch_scratch = 0, max_scratch = 0;
    constexpr vk::DeviceSize ScratchChunk = 128ull << 20;
    for (size_t i = 0; i < builds.size(); ++i) {
        const Entry& e = entries[builds[i].slot];
        const vk::DeviceSize need = Align(builds[i].update ? e.update_scratch : e.build_scratch,
                                          scratch_alignment);
        if (batches.empty() || (batch_scratch + need > ScratchChunk && batches.back().count)) {
            batches.push_back({i, 0});
            batch_scratch = 0;
        }
        scratch_offsets[i] = batch_scratch;
        batch_scratch += need;
        batches.back().count++;
        max_scratch = std::max(max_scratch, batch_scratch);
    }
    if (!EnsureScratch(max_scratch)) {
        std::printf("Ray tracing: no memory for %.0f MiB of build scratch, off\n",
                    double(max_scratch) / (1024.0 * 1024.0));
        ReleaseResources(); // deferred: the commands recorded above still use the buffers
        setup_failed = true;
        on.store(false, std::memory_order_relaxed);
        return;
    }
    auto& geometries = record_geometries;
    auto& infos = record_infos;
    auto& ranges = record_ranges;
    auto& range_pointers = record_range_pointers;
    size_t total_parts = 0;
    for (const Build& b : builds) {
        total_parts += entries[b.slot].parts;
    }
    geometries.resize(total_parts);
    ranges.resize(total_parts);
    infos.resize(builds.size());
    range_pointers.resize(builds.size());
    f.queried.clear();
    size_t part = 0;
    // This frame's full builds by kind, triangles (the heavy-frame line below).
    u64 new_static = 0, new_dynamic = 0, rebuilt = 0;
    for (size_t i = 0; i < builds.size(); ++i) {
        const Build& b = builds[i];
        Entry& e = entries[b.slot];
        // One geometry per part: its positions follow the previous part's.
        for (u32 p = 0; p < e.parts; ++p) {
            geometries[part + p] = Triangles(vertex_items[b.vertex_item].dst + u64(p) * e.vertices * 16,
                                             e.vertices, b.indices);
            ranges[part + p] = {.primitiveCount = e.triangles};
        }
        infos[i] = {
            .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_BUILD_GEOMETRY_INFO_KHR,
            .type = VK_ACCELERATION_STRUCTURE_TYPE_BOTTOM_LEVEL_KHR,
            .flags = e.dynamic ? DynamicFlags : StaticFlags,
            .mode = b.update ? VK_BUILD_ACCELERATION_STRUCTURE_MODE_UPDATE_KHR
                             : VK_BUILD_ACCELERATION_STRUCTURE_MODE_BUILD_KHR,
            .srcAccelerationStructure = b.update ? VkAccelerationStructureKHR(e.blas) : VK_NULL_HANDLE,
            .dstAccelerationStructure = e.blas,
            .geometryCount = e.parts,
            .pGeometries = &geometries[part],
            .scratchData = {.deviceAddress = scratch.address + scratch_offsets[i]},
        };
        range_pointers[i] = &ranges[part];
        part += e.parts;
        if (b.update) {
            ++sums.refits;
        } else {
            const u64 triangles = u64(e.triangles) * e.parts;
            if (e.state == State::Ready) {
                ++sums.rebuilds;
                rebuilt += triangles;
            } else {
                ++sums.builds;
                sums.built_triangles += triangles;
                (e.dynamic ? new_dynamic : new_static) += triangles;
            }
            e.built = frame;
        }
        e.state = State::Ready;
    }
    for (const auto& batch : batches) {
        Dispatcher().vkCmdBuildAccelerationStructuresKHR(
            cmdbuf, u32(batch.count), infos.data() + batch.first, range_pointers.data() + batch.first);
        // The next batch reuses the scratch; the top level reads these.
        barrier(as_stage, Access::eAccelerationStructureWriteKHR, as_stage, as_rw);
    }
    // A heavy frame, printed at once: twice the static build budget in full builds, or 4 ms of
    // CPU so far in Record.
    const double record_us =
        std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - record_start).count();
    if (new_static + new_dynamic + rebuilt > 2 * build_budget || record_us > 4000.0) {
        std::printf("Ray tracing: heavy frame %llu: %zu builds, triangles %llu new static, %llu new "
                    "dynamic, %llu rebuilt; Record %.0f us, creation %.0f us\n",
                    (unsigned long long)frame, builds.size(), (unsigned long long)new_static,
                    (unsigned long long)new_dynamic, (unsigned long long)rebuilt, record_us, create_us);
    }
    pending.clear();
    // Compacted sizes of the new static structures, read back a few frames later.
    auto& query_structures = record_queries;
    query_structures.clear();
    for (const Build& b : builds) {
        const Entry& e = entries[b.slot];
        if (!e.dynamic && e.built == frame && query_structures.size() < MaxItems) {
            query_structures.push_back(e.blas);
            f.queried.emplace_back(b.slot, e.generation);
        }
    }
    if (!query_structures.empty()) {
        cmdbuf.resetQueryPool(f.sizes, 0, u32(query_structures.size()));
        Dispatcher().vkCmdWriteAccelerationStructuresPropertiesKHR(
            cmdbuf, u32(query_structures.size()), query_structures.data(),
            VK_QUERY_TYPE_ACCELERATION_STRUCTURE_COMPACTED_SIZE_KHR, f.sizes, 0);
    }

    // 6. The top level, from the instances of step 4.
    if (profiler) {
        profiler->Mark(0xF5B0'0010ull + 5, [] { return std::string{"ray tracing: structure: top level"}; });
    }
    barrier(Stage::eComputeShader, Access::eShaderWrite, as_stage, Access::eShaderRead);
    const VkAccelerationStructureGeometryKHR tlas_geometry{
        .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_GEOMETRY_KHR,
        .geometryType = VK_GEOMETRY_TYPE_INSTANCES_KHR,
        .geometry = {.instances = {
            .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_GEOMETRY_INSTANCES_DATA_KHR,
            .data = {.deviceAddress = tlas_instances.address}}},
    };
    const VkAccelerationStructureBuildGeometryInfoKHR tlas_info{
        .sType = VK_STRUCTURE_TYPE_ACCELERATION_STRUCTURE_BUILD_GEOMETRY_INFO_KHR,
        .type = VK_ACCELERATION_STRUCTURE_TYPE_TOP_LEVEL_KHR,
        .flags = VK_BUILD_ACCELERATION_STRUCTURE_PREFER_FAST_BUILD_BIT_KHR,
        .mode = VK_BUILD_ACCELERATION_STRUCTURE_MODE_BUILD_KHR,
        .dstAccelerationStructure = tlas,
        .geometryCount = 1,
        .pGeometries = &tlas_geometry,
        .scratchData = {.deviceAddress = scratch.address},
    };
    const VkAccelerationStructureBuildRangeInfoKHR tlas_range{.primitiveCount = instances_push.count};
    const VkAccelerationStructureBuildRangeInfoKHR* tlas_ranges = &tlas_range;
    Dispatcher().vkCmdBuildAccelerationStructuresKHR(cmdbuf, 1, &tlas_info, &tlas_ranges);
    if (profiler) {
        profiler->Mark(0xF5B0'0016ull, [] { return std::string{"ray tracing: structure: after top level"}; });
    }
    // The structure, and the coverage counts of step 4, for the check and the effects' rays.
    barrier(as_stage | Stage::eComputeShader,
            Access::eAccelerationStructureWriteKHR | Access::eShaderWrite,
            Stage::eComputeShader | Stage::eFragmentShader,
            Access::eAccelerationStructureReadKHR | Access::eShaderRead | Access::eShaderWrite);
    scene_ready = true;

    sums.frames++;
    sums.instances += instance_items.size(); // triangles, alpha, characters: counted as added

    // 7. The depth check, on some frames: more often while structures are new (their coverage
    // is learned from it).
    const u64 every = frame - last_new_frame < CheckNewFrames ? check_every : u64(check_every) * 4;
    if (check_every && frame % every == 0) {
        if (profiler) {
            profiler->Mark(0xF5B0'0002ull, [] { return std::string{"ray tracing: depth check"}; });
        }
        auto& counters = f.check_counters;
        if (!counters.buffer &&
            !CreateBuffer(counters, 8 * sizeof(u32),
                          vk::BufferUsageFlagBits::eStorageBuffer | vk::BufferUsageFlagBits::eTransferDst,
                          Host::Read)) {
            check_every = 0;
        } else {
            cmdbuf.fillBuffer(counters.buffer, 0, VK_WHOLE_SIZE, 0);
            barrier(Stage::eTransfer, Access::eTransferWrite, Stage::eComputeShader,
                    Access::eShaderRead | Access::eShaderWrite);
            const vk::DescriptorImageInfo depth_info{.imageView = depth_view,
                                                     .imageLayout = vk::ImageLayout::eGeneral};
            const vk::AccelerationStructureKHR tlas_handle = tlas;
            const vk::WriteDescriptorSetAccelerationStructureKHR as_info{
                .accelerationStructureCount = 1,
                .pAccelerationStructures = &tlas_handle,
            };
            const vk::DescriptorBufferInfo counter_info{.buffer = counters.buffer,
                                                        .range = VK_WHOLE_SIZE};
            const std::array<vk::WriteDescriptorSet, 3> writes = {{
                {.dstBinding = 0, .descriptorCount = 1,
                 .descriptorType = vk::DescriptorType::eSampledImage, .pImageInfo = &depth_info},
                {.pNext = &as_info, .dstBinding = 1, .descriptorCount = 1,
                 .descriptorType = vk::DescriptorType::eAccelerationStructureKHR},
                {.dstBinding = 2, .descriptorCount = 1,
                 .descriptorType = vk::DescriptorType::eStorageBuffer, .pBufferInfo = &counter_info},
            }};
            const CheckPush check{{camera.proj[0], camera.proj[1], camera.proj[2], camera.proj[3]},
                                  {float(width), float(height)},
                                  {camera.jitter[0], camera.jitter[1]}, check_mask, 0,
                                  coverage_stats.address};
            cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, *check_pipeline);
            cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *check_pipeline_layout, 0,
                                        writes);
            cmdbuf.pushConstants(*check_pipeline_layout, vk::ShaderStageFlagBits::eCompute, 0,
                                 sizeof(check), &check);
            const u32 sampled_w = (width + 3) / 4, sampled_h = (height + 3) / 4;
            cmdbuf.dispatch((sampled_w + 7) / 8, (sampled_h + 7) / 8, 1);
            f.checked = true;
        }
    }
    // Results (check words, build errors, depth check) to the host.
    barrier(Stage::eComputeShader, Access::eShaderWrite, Stage::eHost | Stage::eComputeShader,
            Access::eHostRead | Access::eShaderRead | Access::eShaderWrite);
    f.tick = scheduler.CurrentTick();
    if (profiler && resume) {
        profiler->Resume(resume);
    }
}

} // namespace Vulkan
