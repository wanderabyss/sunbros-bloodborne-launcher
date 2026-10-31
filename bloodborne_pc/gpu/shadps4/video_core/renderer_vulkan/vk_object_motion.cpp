// SPDX-License-Identifier: GPL-2.0-or-later
#include "video_core/renderer_vulkan/vk_object_motion.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include <vk_mem_alloc.h>
#include "bbport_settings.h"
#include "bbport_toggles.h"
#include "shader_recompiler/runtime_info.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/motion_capture_budget.h"
#include "video_core/renderer_vulkan/vk_ray_tracing.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"

namespace Vulkan {

namespace {

bool CreateBuffer(const Instance& instance, vk::DeviceSize size, bool host, vk::Buffer& buffer,
                  VmaAllocation& allocation, void** mapped, u64& address) {
    const VkBufferCreateInfo buffer_ci{
        .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .size = size,
        .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT,
    };
    VmaAllocationCreateInfo alloc_ci{
        .usage = VMA_MEMORY_USAGE_AUTO,
    };
    if (host) {
        alloc_ci.requiredFlags = VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
        alloc_ci.flags = VMA_ALLOCATION_CREATE_MAPPED_BIT |
                         VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT;
    } else {
        alloc_ci.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE;
    }
    VkBuffer raw{};
    VmaAllocationInfo info{};
    if (vmaCreateBuffer(instance.GetAllocator(), &buffer_ci, &alloc_ci, &raw, &allocation, &info) !=
        VK_SUCCESS) {
        return false;
    }
    buffer = raw;
    if (mapped) {
        *mapped = info.pMappedData;
    }
    address = instance.GetDevice().getBufferAddress({.buffer = buffer});
    return address != 0;
}

} // namespace

ObjectMotion::ObjectMotion(const Instance& instance_, Scheduler& scheduler_)
    : instance{instance_}, scheduler{scheduler_} {
    // Pipeline selection limits the extra attachment and vertex stores to likely
    // animated draws. A setting or environment override can still disable the path.
    if (!BbSettings::Get().object_motion ||
        BbSettings::Get().upscaler == BbSettings::UpscalerOff) {
        std::puts("Object motion: off (enable in menu or BB_OBJECT_MOTION=1)");
        return;
    }
    const auto& features = instance.GetPhysicalDevice().getFeatures();
    if (!features.vertexPipelineStoresAndAtomics) {
        std::printf("Object motion: vertexPipelineStoresAndAtomics unsupported, off\n");
        return;
    }
    // AMD before RDNA3 (RX 6000 and older, device ids below 0x7440): the GPU is lost at the first
    // frame of the world with object motion on (RX 6600, 6650 XT, 6700 XT, 6900 XT), also with
    // its stores made plain. Off there unless BB_OBJECT_MOTION=1 asks for it; the upscalers work
    // without it, with motion from the camera only.
    const auto props = instance.GetPhysicalDevice().getProperties();
    const char* forced = std::getenv("BB_OBJECT_MOTION");
    if (props.vendorID == 0x1002 && props.deviceID < 0x7440 && !(forced && forced[0] == '1')) {
        std::printf("Object motion: off on this AMD GPU (RX 6000 and older lose the device with it; "
                    "BB_OBJECT_MOTION=1 turns it on)\n");
        return;
    }
    void* mapped = nullptr;
    u64 params_address = 0;
    if (!CreateBuffer(instance, HeaderOffset + 32, true, params_buffer, params_allocation, &mapped,
                      params_address)) {
        std::printf("Object motion: buffer creation failed, off\n");
        return;
    }
    params_mapped = static_cast<u32*>(mapped);
    std::memset(params_mapped, 0, 32);
    const bool rt_active = RayTracing::WantedAtStart() && RayTracing::Allowed() &&
                           instance.IsRayTracingSupported();
    if (!CreatePositions(rt_active ? rt_budget : base_budget)) {
        std::printf("Object motion: buffer creation failed, off\n");
        return;
    }
    history.SetReserve(Motion::CaptureBudget::Reserve(positions_per_frame, rt_active));
    Shader::MotionVectors::params_address = params_address;
    Shader::MotionVectors::positions_header = params_address + HeaderOffset;
    enabled = true;
    std::printf("Object motion: on (%u vertices per frame, %u MiB; %u with ray tracing)\n",
                positions_per_frame, u32((1 + 2 * u64(positions_per_frame)) * 16 >> 20),
                rt_budget);
    std::printf("Object motion: capture capacity %u, %u character-reserved, %.2f MiB positions "
                "(BB_RT_CAPTURE_BUDGET: RT-only Mi-vertices, 1..64; base floor %u)\n",
                positions_per_frame, history.Reserved(),
                double(Motion::CaptureBudget::Bytes(positions_per_frame)) / (1u << 20), base_budget);
}

ObjectMotion::~ObjectMotion() {
    scheduler.Finish();
    const auto allocator = instance.GetAllocator();
    if (params_buffer) {
        vmaDestroyBuffer(allocator, params_buffer, params_allocation);
    }
    if (positions_buffer) {
        vmaDestroyBuffer(allocator, positions_buffer, positions_allocation);
    }
}

void ObjectMotion::OnFrameStart() {
    if (!enabled) {
        return;
    }
    if (BbStats::enabled && (frame % 600) == 0 && history.stats.draws) {
        const auto& s = history.stats;
        std::printf("Object motion: %llu draws, %llu stored, %llu with history, %llu unmatched, "
                    "%llu stored only (ray tracing), %llu capacity skips, %llu invalid, %llu still (600 frames); last frame %u/%u vertices; "
                    "index ranges %llu reused, %llu scanned (%llu found changed), %zu cached\n",
                    (unsigned long long)s.draws, (unsigned long long)s.stored,
                    (unsigned long long)s.loaded, (unsigned long long)s.unmatched,
                    (unsigned long long)s.store_only, (unsigned long long)s.exhausted, (unsigned long long)s.invalid,
                    (unsigned long long)s.still,
                    history.Used(), positions_per_frame, (unsigned long long)index_ranges.stats.hits,
                    (unsigned long long)index_ranges.stats.scans,
                    (unsigned long long)index_ranges.stats.stale, index_ranges.Size());
        index_ranges.stats = {};
        history.stats = {};
    }
    // Ray tracing's larger array while it is wanted; the small one again once it released its
    // structures (it keeps them a while after it is switched off). Last frame's decision: ray
    // tracing makes this frame's after this.
    if (rt_budget > base_budget) {
        const RayTracing* rt = RayTracing::Get();
        const bool wanted = rt && rt->Wanted();
        if (wanted && positions_per_frame < rt_budget && !rt_budget_failed) {
            if (!CreatePositions(rt_budget)) {
                rt_budget_failed = true;
                std::printf("Object motion: no memory for ray tracing's %u vertices a frame\n",
                            rt_budget);
            }
        } else if (!wanted && positions_per_frame > base_budget && rt && !rt->Holding()) {
            CreatePositions(base_budget);
        }
    }
    // Reserve follows RT activity, not whether two configured sizes differ.
    // Also protect characters when growth failed and RT uses the smaller buffer.
    const RayTracing* rt = RayTracing::Get();
    const bool rt_active = rt && (rt->Wanted() || rt->Holding());
    const u32 reserve = Motion::CaptureBudget::Reserve(positions_per_frame, rt_active);
    if (history.Reserved() != reserve) {
        history.SetReserve(reserve);
        std::printf("Object motion: capture capacity %u, %u character-reserved, %.2f MiB positions (RT %s)\n",
                    positions_per_frame, reserve,
                    double(Motion::CaptureBudget::Bytes(positions_per_frame)) / (1u << 20),
                    rt_active ? "active/held" : "off");
    }
    history.NextFrame();
    ++frame;
    if (frame % Motion::IndexRangeCache::Unused == 0) {
        index_ranges.Trim(frame);
    }
    const u32 slot = u32(frame % FrameSlots);
    // Do not overwrite host parameters still referenced by queued GPU work.
    if (params_ticks[slot]) {
        scheduler.Wait(params_ticks[slot]);
        params_ticks[slot] = 0;
    }
    params_used = 0;
    for (auto& target : targets) {
        target.written = false;
    }
    scheduler.EndRendering();
    // Last frame's stores must be visible to this frame's loads. Also finish old reads
    // before the ping-pong half they reference is reused for writes.
    scheduler.Record([](vk::CommandBuffer cmd) {
        const vk::MemoryBarrier2 barrier{
            .srcStageMask = vk::PipelineStageFlagBits2::eVertexShader,
            .srcAccessMask = vk::AccessFlagBits2::eShaderRead | vk::AccessFlagBits2::eShaderWrite,
            .dstStageMask = vk::PipelineStageFlagBits2::eVertexShader,
            .dstAccessMask = vk::AccessFlagBits2::eShaderRead | vk::AccessFlagBits2::eShaderWrite,
        };
        cmd.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &barrier});
    });
}

u64 ObjectMotion::PositionsAddress() const noexcept {
    return enabled ? positions_address : 0;
}

namespace {
/// BB_MOTION_BUDGET: vertices a frame, in millions (1..64), or 0.
u32 BudgetOverride() {
    if (const char* value = std::getenv("BB_MOTION_BUDGET")) {
        const unsigned long millions = std::strtoul(value, nullptr, 10);
        if (millions >= 1 && millions <= 64) {
            return u32(millions << 20);
        }
    }
    return 0;
}
} // namespace

u32 ObjectMotion::BaseBudget() {
    const u32 budget = BudgetOverride();
    return budget ? budget : 4u << 20;
}

u32 ObjectMotion::ChooseRtBudget(const Instance& instance) {
    return Motion::CaptureBudget::Choose(BudgetOverride(), std::getenv("BB_RT_CAPTURE_BUDGET"),
                                         RayTracing::Allowed() && instance.IsRayTracingSupported()).rt;
}

bool ObjectMotion::CreatePositions(u32 per_frame) {
    vk::Buffer buffer{};
    VmaAllocation allocation{};
    u64 address = 0;
    if (!CreateBuffer(instance, vk::DeviceSize(1 + 2 * u64(per_frame)) * 16, false, buffer,
                      allocation, nullptr, address)) {
        if (buffer) {
            vmaDestroyBuffer(instance.GetAllocator(), buffer, allocation);
        }
        return false;
    }
    if (positions_buffer) {
        // Submitted frames use the old array, and the header names it: replaced when the GPU is
        // idle (ray tracing switched on or released: rare).
        scheduler.Finish();
        vmaDestroyBuffer(instance.GetAllocator(), positions_buffer, positions_allocation);
        std::printf("Object motion: %u vertices per frame now, %u MiB\n", per_frame,
                    u32((1 + 2 * u64(per_frame)) * 16 >> 20));
    }
    positions_buffer = buffer;
    positions_allocation = allocation;
    positions_address = address;
    std::memcpy(reinterpret_cast<u8*>(params_mapped) + HeaderOffset, &address, sizeof(address));
    Shader::MotionVectors::positions_address = address;
    positions_per_frame = per_frame;
    // Activity, including equal-size transitions, sets the reserve at the frame boundary.
    history = Motion::History(per_frame);
    return true;
}

u32 ObjectMotion::PrepareDraw(const DrawInfo& draw, bool priority, bool load) {
    last_allocation = {};
    if (!enabled || BbToggle::Disabled(1u << 29)) {
        return 0;
    }
    if (params_used >= ParamsPerFrame) {
        ++dropped_draws;
        ++capture_report.parameter_drops;
        return 0;
    }
    const u64 exhausted = history.stats.exhausted;
    const u64 capacity_drops = history.stats.exhausted_capacity;
    const u64 reserve_drops = history.stats.exhausted_reserve;
    const auto allocation = history.Prepare(draw, priority, load);
    dropped_draws += history.stats.exhausted - exhausted;
    capture_report.capacity_drops += history.stats.exhausted_capacity - capacity_drops;
    capture_report.reserve_drops += history.stats.exhausted_reserve - reserve_drops;
    capture_report.peak_vertices = std::max(capture_report.peak_vertices, history.Used());
    if (history.stats.exhausted != exhausted) {
        capture_report.largest_rejected_vertices =
            std::max(capture_report.largest_rejected_vertices,
                     u64(draw.vertices.count) * draw.instances);
    }
    last_allocation = allocation;
    u32 flags = (allocation.store ? Shader::MotionVectors::FlagStore : 0) |
                (allocation.load ? Shader::MotionVectors::FlagLoad : 0);
    if (!flags) {
        return 0;
    }
    const u32 slot = u32(frame % FrameSlots);
    const u32 index = 1 + slot * ParamsPerFrame + params_used++;
    capture_report.peak_parameters = std::max(capture_report.peak_parameters, params_used);
    u32* param = params_mapped + index * 8;
    param[0] = allocation.store;
    param[1] = allocation.load;
    param[2] = allocation.vertices;
    param[3] = flags;
    param[4] = allocation.first_vertex;
    param[5] = allocation.first_instance;
    param[6] = allocation.instances;
    param[7] = 0;
    params_ticks[slot] = scheduler.CurrentTick();
    return index;
}

ObjectMotion::Target& ObjectMotion::GetTarget(u32 width, u32 height) {
    for (auto& target : targets) {
        if (target.image && target.width == width && target.height == height) {
            target.used_frame = frame;
            return target;
        }
    }
    // A free slot, else the image used longest ago (not the one being read).
    Target* slot = nullptr;
    for (auto& target : targets) {
        if (!target.image) {
            slot = &target;
            break;
        }
        if (&target != read_target && (!slot || target.used_frame < slot->used_frame)) {
            slot = &target;
        }
    }
    if (slot->image) {
        // Destroyed once the GPU is past the work recorded so far (it may still use it).
        scheduler.DeferOperation([image = std::move(slot->image),
                                  view = std::move(slot->view)]() mutable {
            view.reset();
            image.Destroy();
        });
    }
    static u32 reports = 0;
    if (BbStats::enabled && reports < 16) {
        ++reports;
        std::printf("Object motion: motion image %ux%u%s\n", width, height,
                    slot->width ? " (replacing one)" : "");
    }
    const auto device = instance.GetDevice();
    slot->image = VideoCore::UniqueImage(device, instance.GetAllocator());
    slot->image.Create(vk::ImageCreateInfo{
        .imageType = vk::ImageType::e2D,
        .format = vk::Format::eR32G32B32A32Sfloat,
        .extent = {width, height, 1},
        .mipLevels = 1,
        .arrayLayers = 1,
        .samples = vk::SampleCountFlagBits::e1,
        .tiling = vk::ImageTiling::eOptimal,
        .usage = vk::ImageUsageFlagBits::eColorAttachment | vk::ImageUsageFlagBits::eSampled |
                 vk::ImageUsageFlagBits::eTransferSrc,
        .initialLayout = vk::ImageLayout::eUndefined,
    });
    slot->view = Check(device.createImageViewUnique({
        .image = vk::Image(slot->image),
        .viewType = vk::ImageViewType::e2D,
        .format = vk::Format::eR32G32B32A32Sfloat,
        .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
    }));
    slot->width = width;
    slot->height = height;
    slot->written = false;
    slot->layout = vk::ImageLayout::eUndefined;
    slot->used_frame = frame;
    return *slot;
}

void ObjectMotion::Attach(RenderState& state, u32 width, u32 height) {
    constexpr u32 slot = Shader::MotionVectors::Output;
    Target& target = GetTarget(width, height);
    auto& attachment = state.color_attachments[slot];
    attachment = {};
    attachment.image_view = *target.view;
    attachment.image_layout = vk::ImageLayout::eColorAttachmentOptimal;
    if (!target.written || target.layout != vk::ImageLayout::eColorAttachmentOptimal) {
        // Clear once per frame; later reads must not erase the validity of this history.
        scheduler.EndRendering();
        const vk::ImageMemoryBarrier2 barrier{
            .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
            .srcAccessMask = vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
            .dstStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
            .dstAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite |
                             vk::AccessFlagBits2::eColorAttachmentRead,
            .oldLayout = target.layout,
            .newLayout = vk::ImageLayout::eColorAttachmentOptimal,
            .image = vk::Image(target.image),
            .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
        };
        // Recorded in order on the recording thread: CommandBuffer() here switched the rest of
        // the submission (most of the G-buffer) to direct recording on the GPU thread.
        scheduler.Record([barrier](vk::CommandBuffer cmd) {
            cmd.pipelineBarrier2({.imageMemoryBarrierCount = 1, .pImageMemoryBarriers = &barrier});
        });
        target.layout = vk::ImageLayout::eColorAttachmentOptimal;
        attachment.is_clear = !target.written;
        target.written = true;
    }
    state.num_color_attachments = std::max<u16>(state.num_color_attachments, slot + 1);
}

vk::ImageView ObjectMotion::PrepareRead(vk::CommandBuffer cmdbuf, u32 width, u32 height,
                                        bool& valid) {
    // The image of this size; otherwise any image (the pass binds one, its vectors unused).
    Target* target = const_cast<Target*>(Find(width, height));
    if (!target) {
        for (auto& candidate : targets) {
            if (candidate.image && (!target || candidate.used_frame > target->used_frame)) {
                target = &candidate;
            }
        }
    }
    if (!target) {
        target = &GetTarget(1, 1);
    }
    valid = target->written && width == target->width && height == target->height;
    const vk::ImageMemoryBarrier2 barrier{
        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask = vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eComputeShader,
        .dstAccessMask = vk::AccessFlagBits2::eShaderRead,
        .oldLayout = target->layout,
        .newLayout = vk::ImageLayout::eGeneral,
        .image = vk::Image(target->image),
        .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
    };
    cmdbuf.pipelineBarrier2({.imageMemoryBarrierCount = 1, .pImageMemoryBarriers = &barrier});
    target->layout = vk::ImageLayout::eGeneral;
    read_target = target;
    return *target->view;
}

} // namespace Vulkan
