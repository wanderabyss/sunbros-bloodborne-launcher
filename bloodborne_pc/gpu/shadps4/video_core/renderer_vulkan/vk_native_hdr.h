// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: native HDR (hdr_native, off by default). The game's chain after its tone mapper (FXAA, the
// grading LUT, DLSS, the UI, frame generation) is 8-bit SDR and clips anything above 1, so the frame
// stays SDR and carries what the tone mapper compressed beside it:
//   1. The tone mapper also writes a gain to an R16F image at render size (native_hdr_gain.h).
//   2. After the upscaler the frame is copied (Snapshot). When the game's UI is finished,
//      native_hdr_stamp.comp writes the gain into the alpha, encoded so that alpha 1 is no gain, and
//      no gain where the UI changed the picture: the HUD stays at paper white. The UI's own alpha
//      can't do this: it blends alpha with its color factors, so translucent pixels lower it.
//   3. Generated frames get theirs from the game frames around them (NativeHdrCarry).
//   4. The presenter reads the picture with alpha forced to 1, so it's copied to the frame itself
//      (NativeHdrCarry::CopyAlpha).
//   5. post_process.frag multiplies linear SDR by the gain, then rolls off toward the display's peak.
// With the setting off none of this runs: no extra attachment, no pipelines, the same present path.
#pragma once

#include <span>

#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"
#include "video_core/texture_cache/image.h"

namespace Vulkan {

class Instance;
class Scheduler;
struct RenderState;

class NativeHdr {
public:
    /// GraphicsPipelineKey::motion_vectors of a tone mapper that writes the gain. Non-zero, so it
    /// is never preloaded (LoadGraphicsPipeline): its fragment module only exists in this session.
    static constexpr u32 KeyFlag = 2;

    /// hdr_native with HDR on.
    static bool Wanted();

    /// Keeps a tone mapper's SPIR-V by the module made from it.
    static void Remember(vk::ShaderModule module, u64 pgm_hash, std::span<const u32> spv);
    /// The module that also writes the gain, null when this shader cannot.
    static vk::ShaderModule GainModule(vk::Device device, vk::ShaderModule module);

    NativeHdr(const Instance& instance, Scheduler& scheduler);
    ~NativeHdr();

    /// The tone mapper's pass: adds the gain image as its attachment.
    void Attach(RenderState& state);
    /// Before recording the upscaler: the snapshot image of the output's size. May wait for the GPU.
    void EnsureSnapshot(u32 width, u32 height);
    /// The upscaled frame before the UI (`frame`: layout General).
    void Snapshot(vk::CommandBuffer cmdbuf, vk::Image frame, u32 scene_width, u32 scene_height);
    /// The UI is finished: writes the gain into `frame`'s alpha (layout General). False without
    /// a gain and a snapshot for this frame.
    bool Stamp(vk::ImageView frame);

private:
    void EnsureImage(u32 width, u32 height);
    void EnsurePipeline();

    const Instance& instance;
    Scheduler& scheduler;
    VideoCore::UniqueImage image;
    vk::UniqueImageView view;
    VideoCore::UniqueImage snapshot;
    vk::UniqueImageView snapshot_view;
    vk::UniqueSampler sampler;
    vk::UniqueDescriptorSetLayout set_layout;
    vk::UniquePipelineLayout pipeline_layout;
    vk::UniquePipeline pipeline;
    u32 image_width = 0, image_height = 0;
    vk::ImageLayout layout = vk::ImageLayout::eUndefined;
    bool written = false;
    bool snapshot_taken = false;
    u32 snapshot_width = 0, snapshot_height = 0;
    u32 scene_w = 0, scene_h = 0;
};

/// The presenter's side: frame generation interpolates the picture but not the alpha holding the
/// gain, so each generated frame gets it from the game frames around it (native_hdr_generated.comp).
class NativeHdrCarry {
public:
    explicit NativeHdrCarry(const Instance& instance);
    ~NativeHdrCarry();

    /// The gain from the finished picture (layout ShaderReadOnlyOptimal) into the frame made from
    /// it (layout General, storage usage), sampled because their sizes can differ.
    void CopyAlpha(vk::CommandBuffer cmdbuf, Scheduler& scheduler, vk::Image source,
                   vk::Format source_format, vk::ImageView frame_view, u32 width, u32 height);

    /// After frame generation. `frame` (layout General) is the game frame the `generated` views
    /// (layout General) come before; `stamped`: its alpha holds the gain. Keeps a copy for the next.
    void Run(vk::CommandBuffer cmdbuf, Scheduler& scheduler, vk::Image frame, vk::ImageView frame_view,
             std::span<const vk::ImageView> generated, u32 width, u32 height, bool stamped);

private:
    void EnsureHistory(Scheduler& scheduler, u32 width, u32 height);
    void EnsurePipeline();

    const Instance& instance;
    VideoCore::UniqueImage history;
    vk::UniqueImageView history_view;
    vk::UniqueDescriptorSetLayout set_layout;
    vk::UniquePipelineLayout pipeline_layout;
    vk::UniquePipeline pipeline;
    vk::UniqueSampler alpha_sampler;
    vk::UniqueDescriptorSetLayout alpha_set_layout;
    vk::UniquePipelineLayout alpha_pipeline_layout;
    vk::UniquePipeline alpha_pipeline;
    u32 history_width = 0, history_height = 0;
    bool history_stamped = false;
};

} // namespace Vulkan
