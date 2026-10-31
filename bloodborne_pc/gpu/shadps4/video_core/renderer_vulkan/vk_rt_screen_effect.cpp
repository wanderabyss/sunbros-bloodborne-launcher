// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: a ray-traced screen effect (see vk_rt_screen_effect.h).

#include "video_core/renderer_vulkan/vk_rt_screen_effect.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <memory>

#include "video_core/host_shaders/rt_apply_a_change_comp.h"
#include "video_core/host_shaders/rt_apply_a_comp.h"
#include "video_core/host_shaders/rt_apply_r_change_comp.h"
#include "video_core/host_shaders/rt_apply_r_comp.h"
#include "video_core/host_shaders/rt_apply_reflection_comp.h"
#include "video_core/host_shaders/rt_filter_spatial_comp.h"
#include "video_core/host_shaders/rt_filter_spatial_last_comp.h"
#include "video_core/host_shaders/rt_filter_temporal_comp.h"
#include "video_core/host_shaders/rt_trace_ao_comp.h"
#include "video_core/host_shaders/rt_trace_reflection_comp.h"
#include "video_core/host_shaders/rt_trace_shadow_comp.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/renderer_vulkan/vk_shader_util.h"
#include "bbport_toggles.h"

namespace Vulkan {

namespace {

struct TracePush {
    u64 frame;
    float radius;
    u32 rays;
    u32 mask;
    u32 scale;
    float reach;
    u32 flags; ///< rt_trace.comp TraceClosestAo
    u64 coverage;
};

struct FilterPush {
    u64 frame;
    u64 prev_frame;
    u32 step;
    float max_frames;
    u32 scale;
    float fast_band; ///< rt_filter.comp: the long history's band around the fast one
};

/// BB_RT_TRAIL_CLAMP=1: the long history held within 0.25 of the fast one (RTG-5). Off by
/// default (a band of 2 holds nothing): at Ultra in Central Yharnam it raised the frame-to-frame
/// noise by 15-40% (1-2 rays a pixel make the fast history noisy) and no shorter trail was
/// measured (plans/ray-tracing-visible.md step 6).
float FastBand() {
    static const float band = [] {
        const char* value = std::getenv("BB_RT_TRAIL_CLAMP");
        return value && value[0] == '1' ? 0.25f : 2.0f;
    }();
    return band;
}

struct ApplyPush {
    float strength;
    u32 mode;
    u32 scale;
    u32 up;
    u64 frame;
    float split;
    float direct;
};

} // namespace

RtScreenEffect::RtScreenEffect(const Instance& instance_, Scheduler& scheduler_, Kind kind_)
    : instance{instance_}, scheduler{scheduler_}, device{instance_.GetDevice()}, kind{kind_} {
    using Type = vk::DescriptorType;
    const auto layout = [&](std::initializer_list<Type> types) {
        std::vector<vk::DescriptorSetLayoutBinding> bindings;
        u32 binding = 0;
        for (const Type type : types) {
            bindings.push_back({.binding = binding++, .descriptorType = type,
                                .descriptorCount = 1,
                                .stageFlags = vk::ShaderStageFlagBits::eCompute});
        }
        return Check(device.createDescriptorSetLayoutUnique({
            .flags = vk::DescriptorSetLayoutCreateFlagBits::ePushDescriptorKHR,
            .bindingCount = u32(bindings.size()),
            .pBindings = bindings.data(),
        }));
    };
    trace_layout = layout({Type::eSampledImage, Type::eAccelerationStructureKHR, Type::eStorageImage});
    temporal_layout = layout({Type::eSampledImage, Type::eSampledImage, Type::eStorageImage,
                              Type::eSampledImage});
    spatial_layout = layout({Type::eSampledImage, Type::eStorageImage});
    apply_layout = layout({Type::eSampledImage, Type::eStorageImage, Type::eSampledImage});
    apply_change_layout = layout({Type::eSampledImage, Type::eStorageImage, Type::eSampledImage,
                                  Type::eStorageImage});
    const auto pipeline_layout = [&](vk::DescriptorSetLayout set, u32 push_size) {
        const vk::PushConstantRange range{.stageFlags = vk::ShaderStageFlagBits::eCompute,
                                          .size = push_size};
        return Check(device.createPipelineLayoutUnique({
            .setLayoutCount = 1,
            .pSetLayouts = &set,
            .pushConstantRangeCount = 1,
            .pPushConstantRanges = &range,
        }));
    };
    trace_pipeline_layout = pipeline_layout(*trace_layout, sizeof(TracePush));
    temporal_pipeline_layout = pipeline_layout(*temporal_layout, sizeof(FilterPush));
    spatial_pipeline_layout = pipeline_layout(*spatial_layout, sizeof(FilterPush));
    apply_pipeline_layout = pipeline_layout(*apply_layout, sizeof(ApplyPush));
    apply_change_pipeline_layout = pipeline_layout(*apply_change_layout, sizeof(ApplyPush));
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
    const bool shadow = kind == Kind::Shadow;
    const bool reflection = kind == Kind::Reflection;
    trace_pipeline =
        make(shadow ? std::span<const u32>(RT_TRACE_SHADOW_COMP)
                    : reflection ? std::span<const u32>(RT_TRACE_REFLECTION_COMP)
                                 : std::span<const u32>(RT_TRACE_AO_COMP),
             *trace_pipeline_layout);
    temporal_pipeline = make(RT_FILTER_TEMPORAL_COMP, *temporal_pipeline_layout);
    spatial_pipeline = make(RT_FILTER_SPATIAL_COMP, *spatial_pipeline_layout);
    spatial_last_pipeline = make(RT_FILTER_SPATIAL_LAST_COMP, *spatial_pipeline_layout);
    apply_pipeline =
        make(shadow ? std::span<const u32>(RT_APPLY_A_COMP)
                    : reflection ? std::span<const u32>(RT_APPLY_REFLECTION_COMP)
                                 : std::span<const u32>(RT_APPLY_R_COMP),
             *apply_pipeline_layout);
}

void RtScreenEffect::Apply(vk::CommandBuffer cmdbuf, vk::ImageView result, vk::ImageView target,
                           u32 w, u32 h, float strength, bool multiply, vk::ImageView depth_view,
                           u32 scale, u32 up, u64 frame, float split, vk::ImageView change,
                           float direct) {
    if (change && !apply_change_pipeline) {
        const bool shadow = kind == Kind::Shadow;
        const auto module = CompileSPV(shadow ? std::span<const u32>(RT_APPLY_A_CHANGE_COMP)
                                              : std::span<const u32>(RT_APPLY_R_CHANGE_COMP),
                                       device);
        apply_change_pipeline = Check(device.createComputePipelineUnique(
            {}, vk::ComputePipelineCreateInfo{
                    .stage = {.stage = vk::ShaderStageFlagBits::eCompute,
                              .module = module,
                              .pName = "main"},
                    .layout = *apply_change_pipeline_layout,
                }));
        device.destroyShaderModule(module);
    }
    const bool record_change = change && apply_change_pipeline;
    const vk::DescriptorImageInfo ao_info{.imageView = result,
                                          .imageLayout = vk::ImageLayout::eGeneral};
    const vk::DescriptorImageInfo color_info{.imageView = target,
                                             .imageLayout = vk::ImageLayout::eGeneral};
    const vk::DescriptorImageInfo depth_info{.imageView = depth_view,
                                             .imageLayout = vk::ImageLayout::eGeneral};
    const vk::DescriptorImageInfo change_info{.imageView = change,
                                              .imageLayout = vk::ImageLayout::eGeneral};
    const std::array<vk::WriteDescriptorSet, 4> writes = {{
        {.dstBinding = 0, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eSampledImage,
         .pImageInfo = &ao_info},
        {.dstBinding = 1, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eStorageImage,
         .pImageInfo = &color_info},
        {.dstBinding = 2, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eSampledImage,
         .pImageInfo = &depth_info},
        {.dstBinding = 3, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eStorageImage,
         .pImageInfo = &change_info},
    }};
    // The target's last writer (the game's pass) and the passes above.
    const vk::MemoryBarrier2 before{
        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask = vk::AccessFlagBits2::eMemoryWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eComputeShader,
        .dstAccessMask = vk::AccessFlagBits2::eShaderRead | vk::AccessFlagBits2::eShaderWrite};
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &before});
    const ApplyPush push{strength, multiply ? 1u : 0u, scale, std::max(up, 1u), frame, split,
                         direct};
    const vk::PipelineLayout layout =
        record_change ? *apply_change_pipeline_layout : *apply_pipeline_layout;
    cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute,
                        record_change ? *apply_change_pipeline : *apply_pipeline);
    cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, layout, 0,
                                vk::ArrayProxy<const vk::WriteDescriptorSet>(
                                    record_change ? 4u : 3u, writes.data()));
    cmdbuf.pushConstants(layout, vk::ShaderStageFlagBits::eCompute, 0, sizeof(push), &push);
    cmdbuf.dispatch((w + 7) / 8, (h + 7) / 8, 1);
    const vk::MemoryBarrier2 after{
        .srcStageMask = vk::PipelineStageFlagBits2::eComputeShader,
        .srcAccessMask = vk::AccessFlagBits2::eShaderWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .dstAccessMask = vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite};
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &after});
}

RtScreenEffect::~RtScreenEffect() = default;

bool RtScreenEffect::EnsureTargets(u32 w, u32 h) {
    if (w == width && h == height && result.image) {
        return true;
    }
    // The old targets may be in flight (a resolution change): released once the GPU is past
    // the work recorded so far.
    if (result.image) {
        auto retired = std::make_shared<std::array<Target, 5>>(std::array<Target, 5>{
            std::move(raw), std::move(history[0]), std::move(history[1]), std::move(filtered),
            std::move(result)});
        scheduler.DeferOperation([retired] {});
    }
    const auto make = [&](Target& target, vk::Format format) {
        target.view.reset();
        target.image = VideoCore::UniqueImage(device, instance.GetAllocator());
        if (!target.image.TryCreate(vk::ImageCreateInfo{
                .imageType = vk::ImageType::e2D,
                .format = format,
                .extent = {w, h, 1},
                .mipLevels = 1,
                .arrayLayers = 1,
                .samples = vk::SampleCountFlagBits::e1,
                .tiling = vk::ImageTiling::eOptimal,
                .usage = vk::ImageUsageFlagBits::eStorage | vk::ImageUsageFlagBits::eSampled,
                .initialLayout = vk::ImageLayout::eUndefined,
            })) {
            return false;
        }
        target.view = Check(device.createImageViewUnique({
            .image = vk::Image(target.image),
            .viewType = vk::ImageViewType::e2D,
            .format = format,
            .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
        }));
        return bool(target.view);
    };
    width = height = 0;
    if (!make(raw, vk::Format::eR16G16Sfloat) ||
        !make(history[0], vk::Format::eR16G16B16A16Sfloat) ||
        !make(history[1], vk::Format::eR16G16B16A16Sfloat) ||
        !make(filtered, vk::Format::eR16G16B16A16Sfloat) ||
        !make(result, vk::Format::eR16Sfloat)) { // only .r is applied
        std::printf("Ray tracing: no memory for a %ux%u effect's images\n", w, h);
        return false;
    }
    width = w;
    height = h;
    fresh = true;
    return true;
}

vk::ImageView RtScreenEffect::Record(vk::CommandBuffer cmdbuf, vk::ImageView depth_view,
                                         u32 w, u32 h, u32 scale,
                                         vk::AccelerationStructureKHR scene, u64 frame,
                                         u64 prev_frame, u64 frame_number, u64 coverage,
                                         const Settings& settings) {
    if (!Valid() || !scene || !frame || !EnsureTargets(w, h)) {
        return {};
    }
    using Stage = vk::PipelineStageFlagBits2;
    using Access = vk::AccessFlagBits2;
    // No history after frames this effect skipped (shadows while there is no moon): it would be
    // reprojected with last frame's camera.
    const bool first = fresh || frame_number != last_frame_number + 1;
    const bool new_targets = fresh;
    fresh = false;
    last_frame_number = frame_number;
    // New images go to General once; then they stay there, and these are memory dependencies
    // only (last frame's history is read below).
    std::array<vk::ImageMemoryBarrier2, 5> to_general{};
    const std::array<vk::Image, 5> images = {vk::Image(raw.image), vk::Image(history[current].image),
                                             vk::Image(filtered.image), vk::Image(result.image),
                                             vk::Image(history[current ^ 1].image)};
    for (u32 i = 0; i < images.size(); ++i) {
        to_general[i] = {
            .srcStageMask = Stage::eComputeShader | Stage::eFragmentShader,
            .srcAccessMask = Access::eShaderRead | Access::eShaderWrite,
            .dstStageMask = Stage::eComputeShader,
            .dstAccessMask = Access::eShaderRead | Access::eShaderWrite,
            .oldLayout = new_targets ? vk::ImageLayout::eUndefined : vk::ImageLayout::eGeneral,
            .newLayout = vk::ImageLayout::eGeneral,
            .image = images[i],
            .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
        };
    }
    cmdbuf.pipelineBarrier2({.imageMemoryBarrierCount = u32(to_general.size()),
                             .pImageMemoryBarriers = to_general.data()});
    const auto compute_barrier = [&] {
        const vk::MemoryBarrier2 b{.srcStageMask = Stage::eComputeShader,
                                   .srcAccessMask = Access::eShaderWrite,
                                   .dstStageMask = Stage::eComputeShader,
                                   .dstAccessMask = Access::eShaderRead};
        cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &b});
    };
    const auto image_info = [](vk::ImageView view) {
        return vk::DescriptorImageInfo{.imageView = view, .imageLayout = vk::ImageLayout::eGeneral};
    };
    const u32 groups_x = (w + 7) / 8, groups_y = (h + 7) / 8;

    // 1. Rays.
    {
        const auto depth_info = image_info(depth_view);
        const auto out_info = image_info(*raw.view);
        const vk::WriteDescriptorSetAccelerationStructureKHR as_info{
            .accelerationStructureCount = 1,
            .pAccelerationStructures = &scene,
        };
        const std::array<vk::WriteDescriptorSet, 3> writes = {{
            {.dstBinding = 0, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eSampledImage,
             .pImageInfo = &depth_info},
            {.pNext = &as_info, .dstBinding = 1, .descriptorCount = 1,
             .descriptorType = vk::DescriptorType::eAccelerationStructureKHR},
            {.dstBinding = 2, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eStorageImage,
             .pImageInfo = &out_info},
        }};
        // BB_RT_TRACE_MASK: which instances rays see (vk_ray_tracing.h Scene; research).
        static const u32 trace_mask = [] {
            const char* value = std::getenv("BB_RT_TRACE_MASK");
            return value ? u32(std::strtoul(value, nullptr, 0)) : 0x1Bu; // all but the sky
        }();
        // BB_RT_AO_CLOSEST=1: AO weighs the closest hit (A/B against the random-length rays).
        static const u32 trace_flags = [] {
            const char* value = std::getenv("BB_RT_AO_CLOSEST");
            return value && value[0] == '1' ? 1u : 0u;
        }();
        // rt_trace.comp: 2 TraceCheckerboard, 4 TraceScreenAlpha.
        const u32 flags = trace_flags | (settings.checkerboard ? 2u : 0u) |
                          (BbToggle::Disabled(BbToggle::RtScreenAlpha) ? 0u : 4u);
        const TracePush push{frame, settings.radius, settings.rays, trace_mask,
                             scale, settings.reach,  flags,         coverage};
        cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, *trace_pipeline);
        cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *trace_pipeline_layout, 0, writes);
        cmdbuf.pushConstants(*trace_pipeline_layout, vk::ShaderStageFlagBits::eCompute, 0,
                             sizeof(push), &push);
        cmdbuf.dispatch(groups_x, groups_y, 1);
    }
    compute_barrier();
    // 2. Temporal accumulation.
    {
        const auto raw_info = image_info(*raw.view);
        const auto history_info = image_info(*history[current ^ 1].view);
        const auto out_info = image_info(*history[current].view);
        const auto depth_info = image_info(depth_view);
        const std::array<vk::WriteDescriptorSet, 4> writes = {{
            {.dstBinding = 0, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eSampledImage,
             .pImageInfo = &raw_info},
            {.dstBinding = 1, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eSampledImage,
             .pImageInfo = &history_info},
            {.dstBinding = 2, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eStorageImage,
             .pImageInfo = &out_info},
            {.dstBinding = 3, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eSampledImage,
             .pImageInfo = &depth_info},
        }};
        const FilterPush push{frame, first ? 0 : prev_frame, 1, settings.max_frames, scale,
                              FastBand()};
        cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, *temporal_pipeline);
        cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *temporal_pipeline_layout, 0,
                                    writes);
        cmdbuf.pushConstants(*temporal_pipeline_layout, vk::ShaderStageFlagBits::eCompute, 0,
                             sizeof(push), &push);
        cmdbuf.dispatch(groups_x, groups_y, 1);
    }
    // 3. Two a-trous steps: history -> filtered -> result.
    const auto spatial = [&](vk::ImageView src, vk::ImageView dst, u32 step, bool last) {
        compute_barrier();
        const auto src_info = image_info(src);
        const auto dst_info = image_info(dst);
        const std::array<vk::WriteDescriptorSet, 2> writes = {{
            {.dstBinding = 0, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eSampledImage,
             .pImageInfo = &src_info},
            {.dstBinding = 1, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eStorageImage,
             .pImageInfo = &dst_info},
        }};
        const FilterPush push{frame, 0, step, settings.max_frames, scale, FastBand()};
        cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute,
                            last ? *spatial_last_pipeline : *spatial_pipeline);
        cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *spatial_pipeline_layout, 0,
                                    writes);
        cmdbuf.pushConstants(*spatial_pipeline_layout, vk::ShaderStageFlagBits::eCompute, 0,
                             sizeof(push), &push);
        cmdbuf.dispatch(groups_x, groups_y, 1);
    };
    spatial(*history[current].view, *filtered.view, 1, false);
    spatial(*filtered.view, *result.view, 2, true);
    const vk::MemoryBarrier2 done{.srcStageMask = Stage::eComputeShader,
                                  .srcAccessMask = Access::eShaderWrite,
                                  .dstStageMask = Stage::eComputeShader | Stage::eFragmentShader,
                                  .dstAccessMask = Access::eShaderRead};
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &done});
    current ^= 1;
    return *result.view;
}

} // namespace Vulkan
