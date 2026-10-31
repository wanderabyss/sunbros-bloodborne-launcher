// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: ray-traced effects in Bloodborne's frame (see vk_rt_effects.h).

// First: it sets up Vulkan (beta extensions) before vk_mem_alloc.h pulls in the C headers.
#include "video_core/renderer_vulkan/vk_ray_tracing.h"

#include "video_core/renderer_vulkan/vk_rt_effects.h"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <span>
#include <string>
#include <vector>

#include <vk_mem_alloc.h>

#include "bbport_settings.h"
#include "video_core/host_shaders/rt_view_capture_comp.h"
#include "video_core/host_shaders/rt_view_draw_comp.h"
#include "video_core/host_shaders/rt_view_draw_hdr_comp.h"
#include "video_core/host_shaders/rt_view_scene_comp.h"
#include "video_core/renderer_vulkan/vk_camera_motion.h"
#include "video_core/renderer_vulkan/vk_gpu_profiler.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_rt_screen_effect.h"
#include "video_core/renderer_vulkan/vk_runtime.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/renderer_vulkan/vk_shader_util.h"
#include "video_core/texture_cache/texture_cache.h"

namespace Vulkan {

namespace {

// The game's passes (CUSA03173 v01.09), by pixel shader.
constexpr u64 SsaoPs = 0xcbbca5dc;
constexpr u64 ShadowMaskPs = 0xf55643de;
constexpr u64 AoCombinePs = 0xa291c498;
constexpr u64 LightingPs = 0x3fe9e964; // the moon and ambient light; the light volumes follow
constexpr u32 LightResearchDraws = 400;

bool EnvOn(const char* name) {
    const char* value = std::getenv(name);
    return value && value[0] == '1';
}

} // namespace

RtEffects::RtEffects(const Instance& instance_, Scheduler& scheduler_,
                     VideoCore::TextureCache& texture_cache_, Runtime& runtime_,
                     CameraMotion& camera_motion_)
    : instance{instance_}, scheduler{scheduler_}, texture_cache{texture_cache_},
      runtime{runtime_}, camera_motion{camera_motion_} {
    current = this;
}

RtEffects::~RtEffects() {
    if (current == this) {
        current = nullptr;
    }
    if (light_research_file) {
        std::fclose(light_research_file);
    }
    const auto device = instance.GetDevice();
    for (auto& entry : views) {
        if (entry.view) {
            device.destroyImageView(entry.view);
        }
    }
}

void RtEffects::Keep(std::unique_ptr<RtScreenEffect>& e, bool want, bool& failed,
                     u64& off_frames, int kind, const char* name) {
    if (want) {
        off_frames = 0;
        if (!e && !failed) {
            e = std::make_unique<RtScreenEffect>(instance, scheduler, RtScreenEffect::Kind(kind));
            if (!e->Valid()) {
                e.reset();
                failed = true;
                std::printf("%s: setup failed, off\n", name);
            } else {
                std::printf("%s: on\n", name);
            }
        }
    } else if (e && ++off_frames >= ReleaseFrames) {
        // Its images may still be in use: released once the GPU is past the work so far.
        scheduler.DeferOperation([retired = std::shared_ptr<RtScreenEffect>(std::move(e))] {});
        std::printf("%s: off, released\n", name);
    }
}

void RtEffects::OnFrameStart() {
    const auto* rt = RayTracing::Get();
    const bool on = rt && rt->Active();
    static const bool env_ao = EnvOn("BB_RT_AO"), env_shadows = EnvOn("BB_RT_SHADOWS"), env_reflections = EnvOn("BB_RT_REFLECTIONS");
    effect = BbSettings::RayTracingEffective();
    Keep(ao, on && (effect.ao || env_ao), ao_failed, ao_off_frames,
         int(RtScreenEffect::Kind::AmbientOcclusion), "Ray-traced AO");
    Keep(shadow, on && (effect.shadows || env_shadows), shadow_failed, shadow_off_frames,
         int(RtScreenEffect::Kind::Shadow), "Ray-traced moon shadows");
    // The prototype adds a scalar hit-distance term to shadow_mask RGB. It has neither
    // reflected radiance nor a water/material mask, so never dispatch it into game buffers.
    // Retain the serialized request for compatibility until a scene-color path exists.
    static bool reflection_warning = false;
    if (on && (effect.reflections || env_reflections) && !reflection_warning) {
        std::printf("Ray-traced reflections unavailable: prototype disabled (no scene-color/material input)\n");
        reflection_warning = true;
    }
    Keep(reflections, false, reflections_failed, reflections_off_frames,
         int(RtScreenEffect::Kind::Reflection), "Ray-traced water reflections");
    want_ao = on && (effect.ao || env_ao) && ao;
    want_shadow = on && (effect.shadows || env_shadows) && shadow;
    want_reflections = false;
    // BB_RT_VIEW_FILE=<file> holding a debug view (bbport_settings.h DebugView) and, optionally,
    // 1 for the compare split, read about once a second: sets both as the menu does (scripted
    // sessions, scripts\ab-check.ps1).
    auto& settings = BbSettings::Get();
    static const char* view_file = std::getenv("BB_RT_VIEW_FILE");
    if (view_file && ++view_file_frames % 64 == 0) {
        if (FILE* file = std::fopen(view_file, "r")) {
            int view = -1, compare = 0;
            const int read = std::fscanf(file, "%d %d", &view, &compare);
            if (read >= 1 && view >= 0 && view < BbSettings::DebugViewCount) {
                settings.debug_view = view;
                settings.rt_compare = read == 2 && compare != 0;
            }
            std::fclose(file);
        }
    }
    const int debug_view = settings.debug_view.load(std::memory_order_relaxed);
    view_mode = Active() && BbSettings::IsRtView(debug_view) ? debug_view : 0;
    view_split = Active() && settings.rt_compare.load(std::memory_order_relaxed) ? 0.5f : 0.0f;
    view_ready = capture_pending = false;
    if (!view_mode && view_image) {
        ReleaseViewImages();
    }
    if (!Active()) {
        return;
    }
    ++frame;
    if (frame % 600 == 0) {
        // One write (stdout is unbuffered: printf wrote piece by piece, slow on this thread).
        char text[256];
        int used = 0;
        if (want_ao) {
            used += std::snprintf(text + used, sizeof(text) - used,
                                  "Ray-traced AO: %llu of the last 600 frames (%llu after the AO "
                                  "combine, in the shadow mask)\n",
                                  (unsigned long long)(frames_applied + mask_ao_frames),
                                  (unsigned long long)mask_ao_frames);
        }
        if (want_shadow && used >= 0 && used < int(sizeof(text))) {
            used += std::snprintf(text + used, sizeof(text) - used,
                                  "Ray-traced moon shadows: %llu of the last 600 frames%s\n",
                                  (unsigned long long)shadow_frames,
                                  shadow_frames ? "" : " (no moon, or no shadow mask pass)");
        }
        if (want_reflections && used >= 0 && used < int(sizeof(text))) {
            used += std::snprintf(text + used, sizeof(text) - used,
                                  "Ray-traced water reflections: %llu of the last 600 frames\n",
                                  (unsigned long long)reflections_frames);
        }
        std::fwrite(text, 1, std::clamp(used, 0, int(sizeof(text)) - 1), stdout);
        frames_applied = mask_ao_frames = shadow_frames = reflections_frames = 0;
    }
    ssao_target = shadow_mask = {};
    pending_ao = vk::ImageView{};
    done = false;
}

void RtEffects::OnDraw(u64 ps_hash, VideoCore::ImageId color) {
    if (!Active()) {
        return;
    }
    // BB_LIGHT_RESEARCH=1: a window of draws from the lighting pass on, on frames 300, 900 and
    // 1500 of ray tracing (research; one file).
    static const bool light_research = EnvOn("BB_LIGHT_RESEARCH");
    if (light_research_left > 0) {
        --light_research_left;
        std::fprintf(light_research_file, "draw %u ps %016llx color %u\n", ++light_research_draw,
                     (unsigned long long)ps_hash, u32(color.index));
        if (light_research_left == 0) {
            std::fflush(light_research_file);
        }
    } else if (light_research && ps_hash == LightingPs && light_research_windows < 3 &&
               frame >= 300 + 600ull * light_research_windows) {
        if (!light_research_file) {
            const char* dir = std::getenv("BB_DUMP_DIR");
            const std::string path = std::string{dir && *dir ? dir : "out/dump"} +
                                     "/light_research.txt";
            light_research_file = std::fopen(path.c_str(), "w");
        }
        if (light_research_file) {
            ++light_research_windows;
            light_research_left = LightResearchDraws;
            light_research_draw = 1;
            const auto& inv = camera_motion.CurrentInvView();
            std::fprintf(light_research_file,
                         "window %u frame %llu camera %.3f %.3f %.3f (view to world rows %.4f %.4f "
                         "%.4f %.3f | %.4f %.4f %.4f %.3f | %.4f %.4f %.4f %.3f)\n"
                         "draw 1 ps %016llx color %u\n",
                         light_research_windows, (unsigned long long)frame, inv[3], inv[7],
                         inv[11], inv[0], inv[1], inv[2], inv[3], inv[4], inv[5], inv[6], inv[7],
                         inv[8], inv[9], inv[10], inv[11], (unsigned long long)ps_hash,
                         u32(color.index));
        }
    }
    switch (ps_hash) {
    case SsaoPs:
        ssao_target = color;
        break;
    case ShadowMaskPs:
        shadow_mask = color;
        break;
    case AoCombinePs:
        if (!done) {
            done = true;
            Run();
        }
        break;
    default:
        // The first draw after the combine (the lighting; its shader differs between areas
        // with and without SSAO): the combine has written the mask.
        if (done && shadow_mask && (pending_ao || dump_after_combine || capture_pending)) {
            ApplyMaskAo();
        }
        break;
    }
}

void RtEffects::ApplyMaskAo() {
    // The AO combine is done: its AO term is in the mask's R. BB_RT_DUMP_TRIGGER: the mask
    // before and after.
    const bool dump = dump_after_combine;
    dump_after_combine = false;
    const auto* rt = RayTracing::Get();
    const VideoCore::ImageId depth_id = camera_motion.Depth();
    scheduler.EndRendering();
    auto& mask = texture_cache.GetImage(shadow_mask);
    const auto rw = vk::AccessFlagBits2::eShaderRead | vk::AccessFlagBits2::eShaderWrite |
                    vk::AccessFlagBits2::eTransferRead;
    const auto stages = vk::PipelineStageFlagBits2::eComputeShader |
                        vk::PipelineStageFlagBits2::eTransfer;
    runtime.Transit(&mask, vk::ImageLayout::eGeneral, stages, rw);
    VideoCore::Image* depth = depth_id ? &texture_cache.GetImage(depth_id) : nullptr;
    if (depth) {
        runtime.Transit(depth, vk::ImageLayout::eGeneral, vk::PipelineStageFlagBits2::eComputeShader,
                        vk::AccessFlagBits2::eShaderRead);
    }
    runtime.FlushBarriers();
    const auto cmdbuf = scheduler.CommandBuffer();
    if (dump) {
        Dump(cmdbuf, mask, "game_mask_after_combine");
    }
    if (pending_ao && depth && rt && rt->FrameConstantsAddress()) {
        const vk::ImageView depth_view =
            View(*depth, depth->info.pixel_format, vk::ImageAspectFlagBits::eDepth);
        ao->Apply(cmdbuf, pending_ao,
                  View(mask, vk::Format::eR8G8B8A8Unorm, vk::ImageAspectFlagBits::eColor),
                  mask.info.size.width, mask.info.size.height, effect.ao_strength,
                  pending_multiply, depth_view, 1, pending_up, rt->FrameConstantsAddress(),
                  view_split,
                  view_mode == BbSettings::DebugRtChange ? *change_view : vk::ImageView{},
                  effect.ao_direct);
        ++mask_ao_frames;
        if (dump) {
            Dump(cmdbuf, mask, "rt_mask_with_ao");
        }
    }
    pending_ao = vk::ImageView{};
    if (capture_pending) {
        capture_pending = false;
        CaptureView(cmdbuf, mask);
        view_ready = true;
    }
}

void RtEffects::LogLightBuffer(char stage, u64 hash, u32 index, const float* data, u64 size) {
    if (!light_research_file || !data) {
        return;
    }
    // The first 32 floats (light volumes keep a few vec4s: position, radius, colour).
    std::fprintf(light_research_file, "  %c %016llx buf %u size %llu:", stage,
                 (unsigned long long)hash, index, (unsigned long long)size);
    const u64 count = std::min<u64>(size / 4, 32);
    for (u64 i = 0; i < count; ++i) {
        std::fprintf(light_research_file, " %.4g", data[i]);
    }
    std::fputc('\n', light_research_file);
}

bool RtEffects::EnsureViewImages(u32 w, u32 h) {
    const auto device = instance.GetDevice();
    if (!draw_pipeline) {
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
        const auto pipeline_layout = [&](vk::DescriptorSetLayout set, u32 push_size) {
            const vk::PushConstantRange range{.stageFlags = vk::ShaderStageFlagBits::eCompute,
                                              .size = push_size};
            return Check(device.createPipelineLayoutUnique({
                .setLayoutCount = 1,
                .pSetLayouts = &set,
                .pushConstantRangeCount = push_size ? 1u : 0u,
                .pPushConstantRanges = push_size ? &range : nullptr,
            }));
        };
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
        capture_layout = layout({Type::eStorageImage, Type::eStorageImage});
        scene_layout = layout({Type::eSampledImage, Type::eAccelerationStructureKHR,
                               Type::eStorageImage});
        draw_layout = layout({Type::eSampledImage, Type::eSampledImage, Type::eStorageImage});
        capture_pipeline_layout = pipeline_layout(*capture_layout, 0);
        scene_pipeline_layout = pipeline_layout(*scene_layout, 2 * sizeof(u64));
        draw_pipeline_layout = pipeline_layout(*draw_layout, 4 * sizeof(u32));
        capture_pipeline = make(RT_VIEW_CAPTURE_COMP, *capture_pipeline_layout);
        scene_pipeline = make(RT_VIEW_SCENE_COMP, *scene_pipeline_layout);
        draw_pipeline = make(RT_VIEW_DRAW_COMP, *draw_pipeline_layout);
        draw_hdr_pipeline = make(RT_VIEW_DRAW_HDR_COMP, *draw_pipeline_layout);
    }
    if (view_image && w == view_width && h == view_height) {
        return true;
    }
    ReleaseViewImages();
    const auto make_image = [&](VideoCore::UniqueImage& image, vk::UniqueImageView& view,
                                vk::ImageUsageFlags usage) {
        image = VideoCore::UniqueImage(device, instance.GetAllocator());
        if (!image.TryCreate(vk::ImageCreateInfo{
                .imageType = vk::ImageType::e2D,
                .format = vk::Format::eR8G8B8A8Unorm,
                .extent = {w, h, 1},
                .mipLevels = 1,
                .arrayLayers = 1,
                .samples = vk::SampleCountFlagBits::e1,
                .tiling = vk::ImageTiling::eOptimal,
                .usage = vk::ImageUsageFlagBits::eStorage | vk::ImageUsageFlagBits::eSampled | usage,
                .initialLayout = vk::ImageLayout::eUndefined,
            })) {
            return false;
        }
        view = Check(device.createImageViewUnique({
            .image = vk::Image(image),
            .viewType = vk::ImageViewType::e2D,
            .format = vk::Format::eR8G8B8A8Unorm,
            .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
        }));
        return bool(view);
    };
    if (!make_image(view_image, view_view, {}) ||
        !make_image(change_image, change_view, vk::ImageUsageFlagBits::eTransferDst)) {
        std::printf("Ray tracing: no memory for the %ux%u debug view\n", w, h);
        ReleaseViewImages();
        return false;
    }
    view_width = w;
    view_height = h;
    view_fresh = true;
    return true;
}

void RtEffects::ReleaseViewImages() {
    if (view_image || change_image) {
        // The upscaler may still read them in submitted work: released once the GPU is past it.
        struct Retired {
            std::array<VideoCore::UniqueImage, 2> images;
            std::array<vk::UniqueImageView, 2> views; // destroyed first
        };
        auto retired = std::make_shared<Retired>();
        retired->images = {std::move(view_image), std::move(change_image)};
        retired->views = {std::move(view_view), std::move(change_view)};
        scheduler.DeferOperation([retired] {});
    }
    view_image = VideoCore::UniqueImage{};
    change_image = VideoCore::UniqueImage{};
    view_view.reset();
    change_view.reset();
    view_width = view_height = 0;
}

void RtEffects::CaptureView(vk::CommandBuffer cmdbuf, const VideoCore::Image& mask) {
    const vk::DescriptorImageInfo mask_info{
        .imageView = View(mask, vk::Format::eR8G8B8A8Unorm, vk::ImageAspectFlagBits::eColor),
        .imageLayout = vk::ImageLayout::eGeneral};
    const vk::DescriptorImageInfo out_info{.imageView = *view_view,
                                           .imageLayout = vk::ImageLayout::eGeneral};
    const std::array<vk::WriteDescriptorSet, 2> writes = {{
        {.dstBinding = 0, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eStorageImage,
         .pImageInfo = &mask_info},
        {.dstBinding = 1, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eStorageImage,
         .pImageInfo = &out_info},
    }};
    const vk::MemoryBarrier2 before{
        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask = vk::AccessFlagBits2::eMemoryWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eComputeShader,
        .dstAccessMask = vk::AccessFlagBits2::eShaderRead | vk::AccessFlagBits2::eShaderWrite};
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &before});
    cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, *capture_pipeline);
    cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *capture_pipeline_layout, 0,
                                writes);
    cmdbuf.dispatch((view_width + 7) / 8, (view_height + 7) / 8, 1);
    const vk::MemoryBarrier2 after{
        .srcStageMask = vk::PipelineStageFlagBits2::eComputeShader,
        .srcAccessMask = vk::AccessFlagBits2::eShaderWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .dstAccessMask = vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite};
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &after});
}

void RtEffects::RecordSceneView(vk::CommandBuffer cmdbuf, vk::ImageView depth_view, u32 w,
                                u32 h) {
    const auto* rt = RayTracing::Get();
    const vk::AccelerationStructureKHR scene = rt ? rt->Scene() : vk::AccelerationStructureKHR{};
    if (!scene || !rt->FrameConstantsAddress()) {
        return;
    }
    const vk::DescriptorImageInfo depth_info{.imageView = depth_view,
                                             .imageLayout = vk::ImageLayout::eGeneral};
    const vk::DescriptorImageInfo out_info{.imageView = *view_view,
                                           .imageLayout = vk::ImageLayout::eGeneral};
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
    const std::array<u64, 2> push = {rt->FrameConstantsAddress(), rt->CoverageStatsAddress()};
    cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, *scene_pipeline);
    cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *scene_pipeline_layout, 0, writes);
    cmdbuf.pushConstants(*scene_pipeline_layout, vk::ShaderStageFlagBits::eCompute, 0,
                         sizeof(push), push.data());
    cmdbuf.dispatch((w + 7) / 8, (h + 7) / 8, 1);
    const vk::MemoryBarrier2 after{
        .srcStageMask = vk::PipelineStageFlagBits2::eComputeShader,
        .srcAccessMask = vk::AccessFlagBits2::eShaderWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .dstAccessMask = vk::AccessFlagBits2::eMemoryRead};
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &after});
}

void RtEffects::DrawDebugView(vk::CommandBuffer cmdbuf, vk::ImageView out, u32 ow, u32 oh, u32 w,
                              u32 h, bool hdr) {
    if (!view_mode || !view_ready || !view_image || !draw_pipeline || !out || !w || !h) {
        return;
    }
    const vk::DescriptorImageInfo view_info{.imageView = *view_view,
                                            .imageLayout = vk::ImageLayout::eGeneral};
    const vk::DescriptorImageInfo change_info{.imageView = *change_view,
                                              .imageLayout = vk::ImageLayout::eGeneral};
    const vk::DescriptorImageInfo out_info{.imageView = out,
                                           .imageLayout = vk::ImageLayout::eGeneral};
    const std::array<vk::WriteDescriptorSet, 3> writes = {{
        {.dstBinding = 0, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eSampledImage,
         .pImageInfo = &view_info},
        {.dstBinding = 1, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eSampledImage,
         .pImageInfo = &change_info},
        {.dstBinding = 2, .descriptorCount = 1, .descriptorType = vk::DescriptorType::eStorageImage,
         .pImageInfo = &out_info},
    }};
    // rt_view_draw.comp's modes: 1 AO, 2 moon shadow, 3 change, 4 scene. The game's 8-bit frame
    // holds blue in R (the views it reads it through swap them back); its HDR scene color does not.
    const std::array<u32, 4> push = {u32(view_mode - BbSettings::DebugRtAo + 1), hdr ? 0u : 1u,
                                     std::min(w, view_width), std::min(h, view_height)};
    const vk::MemoryBarrier2 before{
        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask = vk::AccessFlagBits2::eMemoryWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eComputeShader,
        .dstAccessMask = vk::AccessFlagBits2::eShaderRead | vk::AccessFlagBits2::eShaderWrite};
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &before});
    cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, hdr ? *draw_hdr_pipeline : *draw_pipeline);
    cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *draw_pipeline_layout, 0, writes);
    cmdbuf.pushConstants(*draw_pipeline_layout, vk::ShaderStageFlagBits::eCompute, 0,
                         sizeof(push), push.data());
    cmdbuf.dispatch((ow + 7) / 8, (oh + 7) / 8, 1);
    const vk::MemoryBarrier2 after{
        .srcStageMask = vk::PipelineStageFlagBits2::eComputeShader,
        .srcAccessMask = vk::AccessFlagBits2::eShaderWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .dstAccessMask = vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite};
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &after});
}

vk::ImageView RtEffects::View(const VideoCore::Image& image, vk::Format format,
                              vk::ImageAspectFlags aspect) {
    const vk::Image handle = image.GetImage();
    ViewEntry* oldest = &views[0];
    for (auto& entry : views) {
        if (entry.view && entry.image == handle && entry.uid == image.image_uid &&
            entry.format == format && entry.aspect == aspect) {
            entry.last_use = ++view_uses;
            return entry.view;
        }
        if (entry.last_use < oldest->last_use) {
            oldest = &entry;
        }
    }
    const auto device = instance.GetDevice();
    if (oldest->view) {
        scheduler.DeferOperation([device, view = oldest->view] { device.destroyImageView(view); });
    }
    *oldest = {
        .image = handle,
        .uid = image.image_uid,
        .format = format,
        .aspect = aspect,
        .view = Check(device.createImageView({
            .image = handle,
            .viewType = vk::ImageViewType::e2D,
            .format = format,
            .subresourceRange = {aspect, 0, 1, 0, 1},
        })),
        .last_use = ++view_uses,
    };
    return oldest->view;
}

void RtEffects::Dump(vk::CommandBuffer cmdbuf, const VideoCore::Image& image, const char* name) {
    // BB_RT_DUMP_TRIGGER: raw RGBA8 copies of the targets, as BB_FRAME_DUMP_TRIGGER's
    // (scripts\raw2png.py), into BB_DUMP_DIR.
    const u32 w = image.info.size.width, h = image.info.size.height;
    const VkBufferCreateInfo buffer_ci{.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
                                       .size = VkDeviceSize(w) * h * 4,
                                       .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT};
    const VmaAllocationCreateInfo alloc_ci{
        .flags = VMA_ALLOCATION_CREATE_MAPPED_BIT | VMA_ALLOCATION_CREATE_HOST_ACCESS_RANDOM_BIT,
        .usage = VMA_MEMORY_USAGE_AUTO_PREFER_HOST};
    VkBuffer buffer{};
    VmaAllocation allocation{};
    VmaAllocationInfo info{};
    if (vmaCreateBuffer(instance.GetAllocator(), &buffer_ci, &alloc_ci, &buffer, &allocation,
                        &info) != VK_SUCCESS) {
        return;
    }
    const vk::MemoryBarrier2 before{.srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
                                    .srcAccessMask = vk::AccessFlagBits2::eMemoryWrite,
                                    .dstStageMask = vk::PipelineStageFlagBits2::eTransfer,
                                    .dstAccessMask = vk::AccessFlagBits2::eTransferRead};
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &before});
    cmdbuf.copyImageToBuffer(image.GetImage(), vk::ImageLayout::eGeneral, buffer,
                             vk::BufferImageCopy{.imageSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
                                                 .imageExtent = {w, h, 1}});
    const char* dir = std::getenv("BB_DUMP_DIR");
    char path[512];
    std::snprintf(path, sizeof(path), "%s/rt_%s_%ux%u.raw", dir && *dir ? dir : "out/dump", name, w,
                  h);
    scheduler.DeferPriorityOperation([allocator = instance.GetAllocator(), buffer, allocation, info,
                                      size = buffer_ci.size, file = std::string{path}] {
        vmaInvalidateAllocation(allocator, allocation, 0, VK_WHOLE_SIZE);
        if (FILE* f = std::fopen(file.c_str(), "wb")) {
            std::fwrite(info.pMappedData, 1, size, f);
            std::fclose(f);
        }
        vmaDestroyBuffer(allocator, buffer, allocation);
    });
    std::printf("Ray tracing: dumped %s\n", path);
}

void RtEffects::Run() {
    auto* rt = RayTracing::Get();
    const VideoCore::ImageId depth_id = camera_motion.Depth();
    if (!rt || !depth_id || camera_motion.CurrentProjection()[0] == 0.0f) {
        return;
    }
    auto& depth = texture_cache.GetImage(depth_id);
    const u32 dw = depth.info.size.width, dh = depth.info.size.height;
    const auto depth_format = depth.info.pixel_format;
    if (depth_format != vk::Format::eD32Sfloat && depth_format != vk::Format::eD32SfloatS8Uint) {
        return;
    }
    // A target this effect can write: the game's RGBA8 storage image, `scale` depth pixels per
    // pixel each way. In some areas (Iosefka's Clinic, Central Yharnam) the SSAO's memory is an
    // image the texture cache made R32 for an earlier pass; the SSAO is drawn into it through an
    // RGBA8 view (mutable format), and written the same way here.
    const auto usable = [&](VideoCore::ImageId id, u32 scale, bool& warned_once, const char* what) {
        if (!id) {
            return false;
        }
        const auto& target = texture_cache.GetImage(id);
        const u32 tw = target.info.size.width, th = target.info.size.height;
        const auto format = target.info.pixel_format;
        if ((format == vk::Format::eR8G8B8A8Unorm || format == vk::Format::eR32Sfloat ||
             format == vk::Format::eR32Uint) &&
            (target.usage_flags & vk::ImageUsageFlagBits::eStorage) && tw * scale == dw &&
            th * scale == dh) {
            return true;
        }
        if (!warned_once) {
            warned_once = true;
            std::printf("Ray tracing: the %s is %s %ux%u with a %ux%u depth: skipped\n", what,
                        vk::to_string(target.info.pixel_format).c_str(), tw, th, dw, dh);
        }
        return false;
    };
    // No SSAO pass this frame, AO at the render size, or AO on the moon's light: the AO goes
    // into the shadow mask after the combine.
    const bool mask_wanted = !ssao_target || effect.ao_full || effect.ao_direct > 0.0f;
    const bool mask_ao = want_ao && mask_wanted &&
                         usable(shadow_mask, 1, warned_shadow, "shadow mask");
    const bool do_ao = want_ao && !mask_ao && usable(ssao_target, 2, warned, "SSAO target");
    const auto& light = camera_motion.CurrentLight();
    const bool moon = light[0] != 0.0f || light[1] != 0.0f || light[2] != 0.0f;
    const bool do_shadow = want_shadow && moon && usable(shadow_mask, 1, warned_shadow, "shadow mask");
    const bool do_reflections = want_reflections && usable(shadow_mask, 1, warned_reflections, "reflections target");
    static const char* dump_trigger = std::getenv("BB_RT_DUMP_TRIGGER");
    const bool dump = dump_trigger && std::remove(dump_trigger) == 0;
    auto* profiler = GpuProfiler::Get();
    const u64 resume = profiler ? profiler->Current() : 0;

    scheduler.EndRendering();
    runtime.Transit(&depth, vk::ImageLayout::eGeneral, vk::PipelineStageFlagBits2::eComputeShader,
                    vk::AccessFlagBits2::eShaderRead);
    const auto rw = vk::AccessFlagBits2::eShaderRead | vk::AccessFlagBits2::eShaderWrite |
                    vk::AccessFlagBits2::eTransferRead;
    const auto stages = vk::PipelineStageFlagBits2::eComputeShader |
                        vk::PipelineStageFlagBits2::eTransfer;
    if (do_ao || (dump && ssao_target)) {
        runtime.Transit(&texture_cache.GetImage(ssao_target), vk::ImageLayout::eGeneral, stages, rw);
    }
    if (do_shadow || do_reflections || (dump && shadow_mask)) {
        runtime.Transit(&texture_cache.GetImage(shadow_mask), vk::ImageLayout::eGeneral, stages, rw);
    }
    runtime.FlushBarriers();
    const auto cmdbuf = scheduler.CommandBuffer();
    const vk::ImageView depth_view = View(depth, depth_format, vk::ImageAspectFlagBits::eDepth);
    const auto& camera = camera_motion;
    rt->Record(cmdbuf, depth_view, dw, dh,
               {camera.CurrentView(), camera.CurrentInvView(), camera.CurrentProjection(),
                camera.CurrentJitter(), camera.CurrentLight()});
    // Debug views: the change image cleared for the applies below, the scene view traced, or the
    // mask kept after the combine (ApplyMaskAo).
    vk::ImageView change{};
    if (view_mode && EnsureViewImages(dw, dh)) {
        if (view_fresh) {
            view_fresh = false;
            std::array<vk::ImageMemoryBarrier2, 2> to_general{};
            for (u32 i = 0; i < 2; ++i) {
                to_general[i] = {
                    .srcStageMask = vk::PipelineStageFlagBits2::eNone,
                    .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
                    .dstAccessMask =
                        vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
                    .oldLayout = vk::ImageLayout::eUndefined,
                    .newLayout = vk::ImageLayout::eGeneral,
                    .image = i == 0 ? vk::Image(view_image) : vk::Image(change_image),
                    .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
                };
            }
            cmdbuf.pipelineBarrier2({.imageMemoryBarrierCount = 2,
                                     .pImageMemoryBarriers = to_general.data()});
        }
        if (view_mode == BbSettings::DebugRtChange) {
            const vk::MemoryBarrier2 to_clear{
                .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
                .srcAccessMask =
                    vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
                .dstStageMask = vk::PipelineStageFlagBits2::eClear,
                .dstAccessMask = vk::AccessFlagBits2::eTransferWrite};
            cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &to_clear});
            cmdbuf.clearColorImage(vk::Image(change_image), vk::ImageLayout::eGeneral,
                                   vk::ClearColorValue{std::array<float, 4>{0.0f, 0.0f, 0.0f, 0.0f}},
                                   vk::ImageSubresourceRange{vk::ImageAspectFlagBits::eColor, 0, 1,
                                                             0, 1});
            const vk::MemoryBarrier2 cleared{
                .srcStageMask = vk::PipelineStageFlagBits2::eClear,
                .srcAccessMask = vk::AccessFlagBits2::eTransferWrite,
                .dstStageMask = vk::PipelineStageFlagBits2::eComputeShader,
                .dstAccessMask =
                    vk::AccessFlagBits2::eShaderRead | vk::AccessFlagBits2::eShaderWrite};
            cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &cleared});
            change = *change_view;
            view_ready = true;
        } else if (view_mode == BbSettings::DebugRtScene) {
            RecordSceneView(cmdbuf, depth_view, dw, dh);
            view_ready = true;
        } else {
            capture_pending = bool(shadow_mask);
        }
    }
    // The effects' own CPU time (Record counts its own), for the ray tracing report.
    const auto effects_start = std::chrono::steady_clock::now();
    if (dump) {
        dump_after_combine = true;
        if (ssao_target) {
            Dump(cmdbuf, texture_cache.GetImage(ssao_target), "game_ssao");
        }
        if (shadow_mask) {
            Dump(cmdbuf, texture_cache.GetImage(shadow_mask), "game_shadow_mask");
        }
        // The G-buffer (R1): its 32-bit targets as they are.
        for (u32 i = 0; i < gbuffer.size(); ++i) {
            if (!gbuffer[i]) {
                continue;
            }
            auto& image = texture_cache.GetImage(gbuffer[i]);
            const auto format = image.info.pixel_format;
            if (format == vk::Format::eR8G8B8A8Unorm || format == vk::Format::eR8G8B8A8Srgb ||
                format == vk::Format::eB10G11R11UfloatPack32) {
                runtime.Transit(&image, vk::ImageLayout::eGeneral,
                                vk::PipelineStageFlagBits2::eTransfer,
                                vk::AccessFlagBits2::eTransferRead);
                runtime.FlushBarriers();
                const std::string name = "gbuffer" + std::to_string(i);
                Dump(scheduler.CommandBuffer(), image, name.c_str());
            }
        }
    }
    // `scale`: depth pixels per target pixel; `up`: target pixels per traced pixel (2: traced
    // at half size, upsampled by depth into the target).
    const auto run = [&](RtScreenEffect& e, VideoCore::ImageId id, u32 scale, u32 up,
                         const RtScreenEffect::Settings& settings, float strength, bool multiply) {
        auto& target = texture_cache.GetImage(id);
        const u32 tw = target.info.size.width, th = target.info.size.height;
        const vk::ImageView result =
            e.Record(cmdbuf, depth_view, (tw + up - 1) / up, (th + up - 1) / up, scale * up,
                     rt->Scene(), rt->FrameConstantsAddress(), rt->PreviousFrameConstantsAddress(),
                     rt->FrameNumber(), rt->CoverageStatsAddress(), settings);
        if (!result) {
            return false;
        }
        e.Apply(cmdbuf, result,
                View(target, vk::Format::eR8G8B8A8Unorm, vk::ImageAspectFlagBits::eColor), tw, th,
                strength, multiply, depth_view, scale, up, rt->FrameConstantsAddress(), view_split,
                change);
        return true;
    };
    if (do_ao) {
        if (profiler) {
            profiler->Mark(0xF5B0'0003ull, [] { return std::string{"ray tracing: AO"}; });
        }
        const RtScreenEffect::Settings settings{
            .radius = effect.ao_radius,
            .rays = u32(effect.ao_rays),
        };
        static const bool env_multiply = EnvOn("BB_RT_AO_MULTIPLY");
        const bool multiply = env_multiply || effect.ao_combine;
        if (run(*ao, ssao_target, 2, 1, settings, effect.ao_strength, multiply)) {
            ++frames_applied;
            if (dump) {
                Dump(cmdbuf, texture_cache.GetImage(ssao_target), "rt_ao");
            }
        }
    }
    if (mask_ao) {
        if (profiler) {
            profiler->Mark(0xF5B0'0003ull, [] { return std::string{"ray tracing: AO"}; });
        }
        const RtScreenEffect::Settings settings{
            .radius = effect.ao_radius,
            .rays = u32(effect.ao_rays),
        };
        // Without an SSAO pass the combine's AO term is the game's baseline: multiplied.
        pending_up = effect.ao_full ? 1 : 2;
        pending_multiply = !ssao_target || effect.ao_combine;
        pending_ao = ao->Record(cmdbuf, depth_view, (dw + pending_up - 1) / pending_up,
                                (dh + pending_up - 1) / pending_up, pending_up, rt->Scene(),
                                rt->FrameConstantsAddress(), rt->PreviousFrameConstantsAddress(),
                                rt->FrameNumber(), rt->CoverageStatsAddress(), settings);
    }
    if (do_shadow) {
        if (profiler) {
            profiler->Mark(0xF5B0'0004ull, [] { return std::string{"ray tracing: moon shadows"}; });
        }
        // A soft edge a few times the moon's own (its disc is about 0.26 degrees across): the
        // filter averages the rays over frames.
        // Full-size shadows (Ultra; Custom High) trace a checkerboard a frame: they cost about
        // four times the half-size ones. BB_RT_SHADOW_FULL=1: every pixel every frame (A/B).
        static const bool every_pixel = EnvOn("BB_RT_SHADOW_FULL");
        const RtScreenEffect::Settings settings{.radius = 0.012f,
                                                .rays = u32(effect.shadow_rays),
                                                .max_frames = 16.0f,
                                                .reach = effect.shadow_reach,
                                                .checkerboard = !effect.shadow_half && !every_pixel};
        static const bool env_replace = EnvOn("BB_RT_SHADOWS_REPLACE");
        const bool replace = env_replace || effect.shadow_replace;
        if (run(*shadow, shadow_mask, 1, effect.shadow_half ? 2 : 1, settings, 1.0f, !replace)) {
            ++shadow_frames;
            if (dump) {
                Dump(cmdbuf, texture_cache.GetImage(shadow_mask), "rt_shadow_mask");
            }
        }
    }
    if (do_reflections) {
        if (profiler) {
            profiler->Mark(0xF5B0'0005ull, [] { return std::string{"ray tracing: water reflections"}; });
        }
        const RtScreenEffect::Settings settings{
            .radius = 0.05f,
            .rays = 1,
            .max_frames = 16.0f,
            .reach = 50.0f,
            .checkerboard = true,
        };
        if (run(*reflections, shadow_mask, 1, 1, settings, 0.75f, false)) {
            ++reflections_frames;
            if (dump) {
                Dump(cmdbuf, texture_cache.GetImage(shadow_mask), "rt_reflections");
            }
        }
    }
    if (profiler && resume) {
        profiler->Resume(resume);
    }
    rt->NoteEffectsCpu(std::chrono::duration<double, std::micro>(
                           std::chrono::steady_clock::now() - effects_start)
                           .count());
}

} // namespace Vulkan
