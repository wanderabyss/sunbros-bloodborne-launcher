// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: whether the swap thread can present to the window this frame (vk_presenter.cpp).
//
// A minimized window on Windows keeps its SDL size (SDL sends no resize to 0x0), but its
// Vulkan surface reports a current extent of 0x0. A present that fails while minimized makes
// the swapchain again at that 0x0 extent; the window still matched the swapchain's requested
// size, so it was never made again and every later frame blitted into a 0x0 target: the HDR /
// SDR-on-HDR scratch image was "resized" (a scheduler Finish() and a skipped 0x0 allocation)
// on every frame, so presenting took the whole game frame, frame generation's present budget
// dropped to 0 generated frames and stayed there, and Reflex latency rose by a frame
// (2026-10-29: the reflex=boost frame generation run at 4K, minimized mid-run).
#pragma once

#include <cstdint>
#include <limits>

namespace Vulkan {

enum class PresentTarget {
    Present,  ///< the swapchain is usable as it is
    Recreate, ///< make the swapchain again first (resized, frame generation switched, restored)
    Skip,     ///< nothing to present into (minimized): free the frame without presenting
};

struct PresentExtent {
    std::uint32_t width = 0, height = 0;
    [[nodiscard]] constexpr bool Empty() const noexcept { return width == 0 || height == 0; }
};

/// `surface_extent` is queried only while the swapchain has no area (a Vulkan call per frame
/// then, none otherwise); UINT32_MAX means the platform lets the swapchain choose its size.
template <typename SurfaceExtentFn>
[[nodiscard]] PresentTarget ChoosePresentTarget(PresentExtent window, PresentExtent requested,
                                                PresentExtent swapchain_extent,
                                                bool frame_gen_changed,
                                                SurfaceExtentFn&& surface_extent) {
    if (window.Empty()) {
        return PresentTarget::Skip;
    }
    if (swapchain_extent.Empty()) {
        // Made while minimized: again once the surface has an area, until then nothing.
        const PresentExtent surface = surface_extent();
        return surface.Empty() ? PresentTarget::Skip : PresentTarget::Recreate;
    }
    if (window.width != requested.width || window.height != requested.height ||
        frame_gen_changed) {
        return PresentTarget::Recreate;
    }
    return PresentTarget::Present;
}

} // namespace Vulkan
