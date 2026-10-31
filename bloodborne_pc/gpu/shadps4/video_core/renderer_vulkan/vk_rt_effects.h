// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: ray-traced effects in Bloodborne's frame (plans\ray-tracing.md, R2/R4). The game
// (CUSA03173 v01.09) draws, after its G-buffer:
//   SSAO          ps cbbca5dc  half-size RGBA8 target from the half-size depth, the G-buffer
//                              normals and a 64x64 noise texture (gone with the SSAO patch: the
//                              passes below read a 1x1 white texture instead)
//   moon shadow   ps f55643de  full-size RGBA8 mask from the linear depth and the 4096x4096 shadow
//                 ps 11ffdfb5  map (cascades in the scene constants), then blurred twice
//   AO combine    ps a291c498  the SSAO into that mask
//   lighting      ps 3fe9e964  (sun/moon and ambient) and the light volumes read mask and SSAO
// At the AO combine's first draw the scene structure is built (RayTracing::Record: every G-buffer
// draw is in); ray-traced AO replaces the SSAO target's R (the AO; G/B hold depth, A the sky),
// and ray-traced moon shadows go into the shadow mask's A (the moon's light; R/G hold depth). The
// game then lights the frame as with its own. Compute only.
//
// Many areas have no SSAO pass (the Hunter's Dream, Forbidden Woods, Yahar'gul, the Nightmare,
// the Research Hall, ...): the combine still runs and leaves the AO term in the mask's R, which
// the lighting reads. There the AO is traced at half size all the same and multiplied into the
// mask's R at the first draw after the combine, upsampled by depth. The same path takes the AO
// where the SSAO is: when it is traced at the render size (rt_ao_full; the SSAO target is half
// size) or also darkens the moon's light (rt_ao_direct, the mask's A), replacing the combine's
// AO term or multiplied with it (rt_ao_combine).
//
// The moon's shadow map holds characters and moving objects only (the world's shadows are baked
// into its lighting): the ray-traced shadow multiplies the game's by default, so characters keep
// their shadow-map shadows (hair and cloth included) and the world gets the moon's shadows of
// everything opaque the structure has.
//
// Debug views (menu: Ray tracing and Debug views; bbport_settings.h DebugRt*, rt_compare), for
// seeing what ray tracing changes. They cost nothing while off:
// - Compare: the left half of each target keeps the game's own value (rt_apply.comp `split`).
// - AO / moon shadow: the shadow mask as the lighting reads it, kept after the combine
//   (rt_view_capture.comp) and drawn in grey over the upscaled frame (rt_view_draw.comp).
// - What ray tracing changed: the applies also record how far they moved each value.
// - Scene: a camera ray per pixel against the scene, coloured by what it hits
//   (rt_view_scene.comp).

#pragma once

#include <array>
#include <memory>

#include "bbport_settings.h"
#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"
#include "video_core/texture_cache/image.h"
#include "video_core/texture_cache/types.h"

namespace VideoCore {
class Image;
class TextureCache;
} // namespace VideoCore

namespace Vulkan {

class Instance;
class Scheduler;
class Runtime;
class CameraMotion;
class GraphicsPipeline;
class RtScreenEffect;

class RtEffects {
public:
    RtEffects(const Instance& instance, Scheduler& scheduler, VideoCore::TextureCache& texture_cache,
              Runtime& runtime, CameraMotion& camera_motion);
    ~RtEffects();

    /// Whether a ray-traced effect is on this frame (the hooks below are then needed): the
    /// setting (bbport.ini ray_tracing) turns it on and ray tracing is active.
    [[nodiscard]] bool Active() const noexcept {
        return want_ao || want_shadow || want_reflections;
    }
    /// Every draw (after PrepareRenderState): the pass's pixel shader and first color target.
    void OnDraw(u64 ps_hash, VideoCore::ImageId color);
    /// A G-buffer draw's color targets (for BB_RT_DUMP_TRIGGER's dumps; research).
    void OnGBuffer(const std::array<VideoCore::ImageId, 6>& targets) {
        gbuffer = targets;
    }
    /// Start of a frame (display pass), after RayTracing's: what is on this frame. An effect is
    /// set up the first frame it is on and released ReleaseFrames after it was switched off.
    void OnFrameStart();
    /// The debug view chosen in the menu, over the upscaled frame: `out` is the output-size UI
    /// image (an RGBA8 storage view, General layout, `ow` x `oh`; `hdr`: the native preset's
    /// RGBA16F scene color), the scene the top-left `w` x `h` of the render-size images.
    /// Records nothing unless a view is on and this frame made one.
    void DrawDebugView(vk::CommandBuffer cmdbuf, vk::ImageView out, u32 ow, u32 oh, u32 w, u32 h,
                       bool hdr = false);
    /// BB_LIGHT_RESEARCH=1 (plans/ray-tracing-visible.md step 4b): on three frames, the draws
    /// from the game's lighting pass on, their pixel shaders and the start of their constant
    /// buffers, with the camera, into <BB_DUMP_DIR>/light_research.txt (where are the lamps'
    /// positions and radii). Whether the draw now binding its buffers is in that window.
    [[nodiscard]] bool LightResearch() const noexcept {
        return light_research_left > 0;
    }
    /// One constant buffer of such a draw (`stage` 'V' or 'F', the shader's hash).
    void LogLightBuffer(char stage, u64 hash, u32 index, const float* data, u64 size);
    /// The rasterizer's, for the upscaler's DrawDebugView (null before it exists).
    static RtEffects* Get() noexcept {
        return current;
    }

private:
    static constexpr u64 ReleaseFrames = 600;
    /// Sets up `effect` when it is wanted, releases it once unused for ReleaseFrames.
    void Keep(std::unique_ptr<RtScreenEffect>& effect, bool want, bool& failed, u64& off_frames,
              int kind, const char* name);
    void Run();
    /// After the combine: pending_ao into the shadow mask's R (and the research dumps).
    void ApplyMaskAo();
    vk::ImageView View(const VideoCore::Image& image, vk::Format format, vk::ImageAspectFlags aspect);
    /// The debug views' render-size images and pipelines, made the first frame a view is on.
    bool EnsureViewImages(u32 w, u32 h);
    void ReleaseViewImages();
    /// The shadow mask as the lighting will read it, into view_image (the AO and moon views).
    void CaptureView(vk::CommandBuffer cmdbuf, const VideoCore::Image& mask);
    /// The scene view's camera rays into view_image.
    void RecordSceneView(vk::CommandBuffer cmdbuf, vk::ImageView depth_view, u32 w, u32 h);

    static inline RtEffects* current = nullptr;
    /// BB_LIGHT_RESEARCH: draws left in this frame's window, windows taken, the file.
    u32 light_research_left = 0, light_research_windows = 0, light_research_draw = 0;
    FILE* light_research_file = nullptr;
    void Dump(vk::CommandBuffer cmdbuf, const VideoCore::Image& image, const char* name);

    const Instance& instance;
    Scheduler& scheduler;
    VideoCore::TextureCache& texture_cache;
    Runtime& runtime;
    CameraMotion& camera_motion;
    std::unique_ptr<RtScreenEffect> ao, shadow, reflections;
    bool want_ao = false, want_shadow = false, want_reflections = false; ///< on this frame
    bool ao_failed = false, shadow_failed = false, reflections_failed = false; ///< setup failed: not tried again
    u64 ao_off_frames = 0, shadow_off_frames = 0, reflections_off_frames = 0;
    BbSettings::RayTracingEffect effect{};            ///< this frame's

    VideoCore::ImageId ssao_target{}, shadow_mask{};
    vk::ImageView pending_ao{}; ///< traced for the mask after the combine (see the top)
    u32 pending_up = 2;         ///< its target pixels per traced pixel (1: full size)
    bool pending_multiply = true; ///< multiplied with the combine's AO term (else replaces it)
    std::array<VideoCore::ImageId, 6> gbuffer{};
    bool done = false;
    bool dump_after_combine = false; ///< BB_RT_DUMP_TRIGGER: the mask again after the combine
    bool warned = false;
    u64 frames_applied = 0, mask_ao_frames = 0, shadow_frames = 0, reflections_frames = 0, frame = 0;
    bool warned_shadow = false, warned_reflections = false;

    // Debug views (see the top).
    int view_mode = 0;          ///< this frame's: 0 none, else bbport_settings.h DebugRt*
    float view_split = 0.0f;    ///< the compare split this frame (0: off)
    bool view_ready = false;    ///< view_image (or change_image) holds this frame's
    bool capture_pending = false; ///< the mask is to be kept after the combine
    u64 view_file_frames = 0;   ///< BB_RT_VIEW_FILE polling
    u32 view_width = 0, view_height = 0;
    bool view_fresh = true;     ///< new images: still in Undefined layout
    VideoCore::UniqueImage view_image, change_image;
    vk::UniqueImageView view_view, change_view;
    vk::UniqueDescriptorSetLayout capture_layout, scene_layout, draw_layout;
    vk::UniquePipelineLayout capture_pipeline_layout, scene_pipeline_layout, draw_pipeline_layout;
    vk::UniquePipeline capture_pipeline, scene_pipeline, draw_pipeline, draw_hdr_pipeline;

    struct ViewEntry {
        vk::Image image{};
        u64 uid = 0;
        vk::Format format{};
        vk::ImageAspectFlags aspect{};
        vk::ImageView view{};
        u64 last_use = 0;
    };
    std::array<ViewEntry, 8> views{};
    u64 view_uses = 0;
};

} // namespace Vulkan
