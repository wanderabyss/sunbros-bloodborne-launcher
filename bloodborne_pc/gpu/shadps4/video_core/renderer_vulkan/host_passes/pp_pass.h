//  SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
//  SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"

namespace Vulkan {
class Frame;
}

namespace Vulkan::HostPasses {

class PostProcessingPass {
public:
    struct Settings {
        float gamma = 1.0f;
        u32 hdr = 0;
        u32 srgb_input = 0;
        u32 sdr_on_hdr = 0; // bbport: SDR swapchain on a display Windows runs in HDR
        // bbport: HDR brightness (BbSettings::HdrLevels; post_process.frag).
        float white_nits = 120.0f;
        float peak_nits = 1000.0f;
        float boost = 1.0f;
        u32 native = 0; // bbport: native HDR: 0 off, 1 gain in alpha, 2 no gain (post_process.frag)
        float native_color = 0.25f; // bbport: BbSettings hdr_native_color
        float native_start = 2.0f;  // bbport: BbSettings hdr_native_start
        float native_end = 4.55f;   // bbport: BbSettings hdr_native_end
        float native_boost = 2.5f;  // bbport: BbSettings hdr_native_boost
    };

    void Create(vk::Device device, vk::Format surface_format);

    void Render(vk::CommandBuffer cmdbuf, vk::ImageView input, vk::Extent2D input_size,
                Frame& output, Settings settings);

private:
    vk::UniquePipeline pipeline{};
    vk::UniquePipelineLayout pipeline_layout{};
    vk::UniqueDescriptorSetLayout desc_set_layout{};
    vk::UniqueSampler sampler{};
};

} // namespace Vulkan::HostPasses
