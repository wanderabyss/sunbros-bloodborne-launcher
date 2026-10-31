// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include <algorithm>
#include <atomic>
#include <cstdio>
#include "video_core/renderer_vulkan/liverpool_to_vk.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/texture_cache/sampler.h"
#include "bbport_settings.h"

namespace VideoCore {

Sampler::Sampler(const Vulkan::Instance& instance, const AmdGpu::Sampler& sampler,
                 const AmdGpu::BorderColorBuffer border_color_base, const bool is_depth, float extra_lod_bias) {
    using namespace Vulkan;
    const bool game_aniso = AmdGpu::IsAnisoFilter(sampler.xy_mag_filter) ||
                            AmdGpu::IsAnisoFilter(sampler.xy_min_filter);
    // bbport: anisotropic filtering forced on the game's mipmapped, filtered textures
    // (anisotropic_filtering in bbport.ini, read at start; 0 keeps the game's own). Depth and
    // compare samplers, point-filtered ones and those without mips (UI, fonts, lookup tables)
    // keep the game's filtering. The setting is fixed for the session, so the sampler cache needs
    // no key for it.
    const int forced = BbSettings::Get().startup_anisotropy;
    const bool force = forced > 1 && !is_depth && sampler.xy_min_filter != AmdGpu::Filter::Point &&
                       sampler.mip_filter != AmdGpu::MipFilter::None && sampler.MaxLod() > 0.0f;
    const bool anisotropy_enable = instance.IsAnisotropicFilteringSupported() && (game_aniso || force);
    const float wanted = std::max(game_aniso ? sampler.MaxAniso() : 1.0f, force ? float(forced) : 1.0f);
    const float max_anisotropy =
        anisotropy_enable ? std::clamp(wanted, 1.0f, instance.MaxSamplerAnisotropy()) : 1.0f;
    {
        // What the setting reaches, logged at 16, 32 and 64 samplers (the game makes ~20-30):
        // the game's own anisotropic samplers (4x on world surfaces at Cathedral Ward), the
        // trilinear ones forced, and the rest (render targets, no mips, point filtered, depth).
        static std::atomic<u32> total, own, forced_count;
        const u32 n = ++total;
        own += game_aniso;
        forced_count += force && !game_aniso;
        if (n == 16 || n == 32 || n == 64) {
            std::printf("Anisotropy (%s): %u samplers: %u anisotropic in the game, %u trilinear raised, %u kept\n",
                        forced > 1 ? (forced == 16 ? "16x" : forced == 8 ? "8x" : forced == 4 ? "4x" : "2x") : "game's own",
                        n, own.load(), forced_count.load(), n - own.load() - forced_count.load());
            std::fflush(stdout);
        }
    }
    auto border_color = LiverpoolToVK::BorderColor(sampler.border_color_type);
    if (border_color == vk::BorderColor::eFloatCustomEXT &&
        !instance.IsCustomBorderColorSupported()) {
        LOG_WARNING(Render_Vulkan, "Custom border color is not supported, falling back to black");
        border_color = vk::BorderColor::eFloatOpaqueBlack;
    }

    const auto custom_color = [&]() -> std::optional<vk::SamplerCustomBorderColorCreateInfoEXT> {
        if (border_color == vk::BorderColor::eFloatCustomEXT) {
            const auto border_color_index = sampler.border_color_ptr.Value();
            const auto border_color_buffer = border_color_base.Address<std::array<float, 4>*>();
            const auto custom_border_color_array = border_color_buffer[border_color_index];

            const vk::SamplerCustomBorderColorCreateInfoEXT ret{
                .customBorderColor =
                    vk::ClearColorValue{
                        .float32 = custom_border_color_array,
                    },
                .format = vk::Format::eR32G32B32A32Sfloat,
            };
            return ret;
        } else {
            return std::nullopt;
        }
    }();

    const vk::SamplerCreateInfo sampler_ci = {
        .pNext = custom_color ? &*custom_color : nullptr,
        .magFilter = LiverpoolToVK::Filter(sampler.xy_mag_filter),
        .minFilter = LiverpoolToVK::Filter(sampler.xy_min_filter),
        .mipmapMode = LiverpoolToVK::MipFilter(sampler.mip_filter),
        .addressModeU = LiverpoolToVK::ClampMode(sampler.clamp_x),
        .addressModeV = LiverpoolToVK::ClampMode(sampler.clamp_y),
        .addressModeW = LiverpoolToVK::ClampMode(sampler.clamp_z),
        .mipLodBias = std::clamp(sampler.LodBias() + extra_lod_bias, -instance.MaxSamplerLodBias(),
                                 instance.MaxSamplerLodBias()),
        .anisotropyEnable = anisotropy_enable,
        .maxAnisotropy = max_anisotropy,
        // GCN compares per instruction; a plain read of a compare sampler is undefined in Vulkan.
        .compareEnable = is_depth,
        .compareOp = LiverpoolToVK::DepthCompare(sampler.depth_compare_func),
        .minLod = sampler.MinLod(),
        .maxLod = sampler.MaxLod(),
        .borderColor = border_color,
        .unnormalizedCoordinates = false, // Handled in shader due to Vulkan limitations.
    };
    auto [sampler_result, smplr] = instance.GetDevice().createSamplerUnique(sampler_ci);
    ASSERT_MSG(sampler_result == vk::Result::eSuccess, "Failed to create sampler: {}",
               vk::to_string(sampler_result));
    handle = std::move(smplr);
}

Sampler::~Sampler() = default;

} // namespace VideoCore
