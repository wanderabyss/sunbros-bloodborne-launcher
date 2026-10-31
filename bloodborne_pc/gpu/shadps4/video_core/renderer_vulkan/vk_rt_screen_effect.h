// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: a ray-traced screen effect on RayTracing's scene (plans\ray-tracing.md phases 1 and 2):
// ambient occlusion (at the size of the game's SSAO target, half the render size) or the moon's
// shadow (at the size of its shadow mask, the render size). Compute only: rt_trace.comp traces
// `rays` rays a pixel (normals from the depth), rt_filter.comp accumulates them over frames
// (camera reprojection, depth-checked) and runs two edge-aware a-trous steps; rt_apply.comp
// writes the result into the game's target, one channel (vk_rt_effects.h).

#pragma once

#include <array>

#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"
#include "video_core/texture_cache/image.h"

namespace Vulkan {

class Instance;
class Scheduler;

class RtScreenEffect {
public:
    /// AO: rays over the hemisphere, into the target's R. Shadow: rays towards the moon, into A.
    /// Reflection: hybrid planar/ray-traced reflections for water and wet surfaces.
    enum class Kind { AmbientOcclusion, Shadow, Reflection };
    RtScreenEffect(const Instance& instance, Scheduler& scheduler, Kind kind);
    ~RtScreenEffect();

    struct Settings {
        float radius = 1.0f; ///< AO: reach in metres; shadow: cone tangent (soft edges)
        u32 rays = 1;        ///< a pixel and frame
        float max_frames = 24.0f;
        float reach = 0.0f;  ///< shadow: ray length in metres
        /// Rays for half the pixels a frame, in a checkerboard that alternates; the temporal
        /// pass keeps the others' history (or their neighbours' rays where there is none).
        bool checkerboard = false;
    };

    /// Records the passes at `width` x `height`, `scale` depth pixels per pixel each way;
    /// returns the result's view (General layout, r16f: the unoccluded / lit fraction), or
    /// null. `frame` / `prev_frame`: RayTracing's FrameConstants addresses (prev 0: none);
    /// `frame_number`: its FrameNumber (history only after a frame this effect ran in);
    /// `coverage`: its CoverageStatsAddress.
    vk::ImageView Record(vk::CommandBuffer cmdbuf, vk::ImageView depth_view, u32 width,
                         u32 height, u32 scale, vk::AccelerationStructureKHR scene, u64 frame,
                         u64 prev_frame, u64 frame_number, u64 coverage,
                         const Settings& settings);

    /// The result into `target` (the game's RGBA8 target, storage, General layout, `width` x
    /// `height`, `scale` depth pixels per pixel): replaced (`multiply` false) or multiplied with
    /// the game's. `up` > 1: Record's result is 1/up of the target's size, upsampled by depth
    /// (`frame`: RayTracing's FrameConstants address). `split` > 0: the target's left share of
    /// its width keeps the game's value (the compare view). `change` (rgba8, storage, General,
    /// render size) or null: where to record how much the value changed (the change view).
    /// `strength` above 1 raises the result to that power. `direct` > 0 (AO into the shadow
    /// mask's R): that share of it also multiplies the moon's light (A).
    void Apply(vk::CommandBuffer cmdbuf, vk::ImageView result, vk::ImageView target, u32 width,
               u32 height, float strength, bool multiply, vk::ImageView depth_view, u32 scale,
               u32 up, u64 frame, float split = 0.0f, vk::ImageView change = {},
               float direct = 0.0f);

    [[nodiscard]] bool Valid() const noexcept {
        return trace_pipeline && temporal_pipeline && spatial_pipeline && spatial_last_pipeline &&
               apply_pipeline;
    }

private:
    struct Target {
        VideoCore::UniqueImage image;
        vk::UniqueImageView view;
    };
    bool EnsureTargets(u32 width, u32 height);

    const Instance& instance;
    Scheduler& scheduler;
    vk::Device device;
    Kind kind;
    vk::UniqueDescriptorSetLayout trace_layout, temporal_layout, spatial_layout, apply_layout,
        apply_change_layout;
    vk::UniquePipelineLayout trace_pipeline_layout, temporal_pipeline_layout,
        spatial_pipeline_layout, apply_pipeline_layout, apply_change_pipeline_layout;
    vk::UniquePipeline trace_pipeline, temporal_pipeline, spatial_pipeline, spatial_last_pipeline,
        apply_pipeline;
    /// The apply that also records its change: made the first time the change view is on.
    vk::UniquePipeline apply_change_pipeline;

    u32 width = 0, height = 0;
    bool fresh = true; ///< targets new: no history yet
    u64 last_frame_number = 0; ///< RayTracing::FrameNumber of the last Record
    Target raw;
    std::array<Target, 2> history; ///< this frame's and last frame's, swapped each frame
    Target filtered;               ///< between the two a-trous steps
    Target result;
    u32 current = 0;
};

} // namespace Vulkan
