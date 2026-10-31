// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: DLSS 5 neural rendering through NVIDIA's own interface (route B, plans/final-plan.md
// step 13). It runs through the DLSS bridge (ABI 3, Dlss::*NeuralRender*), which reports it
// unsupported until NVIDIA ships DLSS 5 for RTX 40 with a runtime usable from Vulkan; Get() is
// then null and nothing runs. The community bridge (route A) needs nothing here: it hooks the
// DLSS calls themselves.
#pragma once

#include <cstdio>
#include <optional>

#include "bbport_settings.h"
#include "video_core/renderer_vulkan/vk_dlss.h"

namespace Vulkan {

class Dlss5 {
public:
    /// What it repaints with: super resolution's inputs, the camera, and optional guides. The
    /// port has no normal or albedo images (ray tracing rebuilds normals from depth) and no
    /// mask yet: those stay null until something produces them.
    struct Inputs {
        Dlss::Resource color;  ///< the upscaled frame: storage, General; repainted in place
        Dlss::Resource depth;  ///< render size
        Dlss::Resource motion; ///< render size, current to previous
        Dlss::Resource normals{}, albedo{}, mask{};
        float jitter_x = 0.0f, jitter_y = 0.0f;
        float camera_near = 0.1f, camera_far = 10000.0f, camera_fov = 1.0f;
        bool depth_inverted = false;
        bool has_matrices = false;
        std::array<float, 16> view_to_clip{}, clip_to_prev_clip{}, prev_clip_to_clip{};
        bool hdr = false; ///< linear colour (DLSS's input is tonemapped today: false)
        bool reset = false;
        /// The look (decision D6), 0..1: Structure Intensity (fine detail) and Tone Intensity
        /// (lighting and colour; 0 keeps Bloodborne's grading). They default to the settings
        /// (bbport.ini dlss5_detail / dlss5_tone, default 0.5 / 0), read when Inputs is built,
        /// so a menu change applies at the next frame.
        float detail = BbSettings::Get().dlss5_detail.load();
        float tone = BbSettings::Get().dlss5_tone.load();
    };

    /// The backend, or null while the bridge has none (nothing is allocated until it has).
    static Dlss5* Get() {
        Dlss* dlss = Dlss::Get();
        if (!dlss || !dlss->NeuralRenderAvailable()) {
            return nullptr;
        }
        static Dlss5 instance;
        instance.dlss = dlss;
        return &instance;
    }

    /// Repaints `in.color` after DLSS super resolution and before sharpening, the game's
    /// post-processing and the UI; frame generation then interpolates the repainted frames.
    /// `wait_idle` waits for submitted GPU work before a feature is replaced. False when it
    /// could not (the frame stays super resolution's).
    template <typename WaitIdle>
    bool Record(vk::CommandBuffer cmdbuf, const Inputs& in, WaitIdle&& wait_idle) {
        const Dlss::NeuralRenderDesc desc{in.color.width, in.color.height, in.color.format,
                                          in.depth.width, in.depth.height, in.hdr};
        if (!dlss->HasNeuralRender(desc)) {
            // A description that failed once is not retried: each try waits for the GPU.
            if (failed && *failed == desc) {
                return false;
            }
            wait_idle();
            dlss->ReleaseNeuralRender();
            if (!dlss->CreateNeuralRender(cmdbuf, desc)) {
                failed = desc;
                std::printf("DLSS 5: the neural rendering feature could not be created for "
                            "%ux%u; the frame stays super resolution's\n",
                            desc.width, desc.height);
                return false;
            }
            failed.reset();
        }
        // Decision 6: the defaults (tone 0 keeps Bloodborne's grading, detail at half) come
        // from the settings through Inputs.
        return dlss->EvaluateNeuralRender(
            cmdbuf, {.color = in.color,
                     .depth = in.depth,
                     .motion = in.motion,
                     .normals = in.normals,
                     .albedo = in.albedo,
                     .mask = in.mask,
                     .jitter_x = in.jitter_x,
                     .jitter_y = in.jitter_y,
                     .camera_near = in.camera_near,
                     .camera_far = in.camera_far,
                     .camera_fov = in.camera_fov,
                     .exposure = 1.0f,
                     .structure_intensity = in.detail,
                     .tone_intensity = in.tone,
                     .depth_inverted = in.depth_inverted,
                     .reset = in.reset,
                     .has_matrices = in.has_matrices,
                     .view_to_clip = in.view_to_clip,
                     .clip_to_prev_clip = in.clip_to_prev_clip,
                     .prev_clip_to_clip = in.prev_clip_to_clip});
    }

private:
    Dlss* dlss{};
    std::optional<Dlss::NeuralRenderDesc> failed; ///< the description creation last failed for
};

} // namespace Vulkan
