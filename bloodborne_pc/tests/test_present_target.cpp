// present_target.h: a swapchain made while the window was minimized (0x0 surface) is made
// again once the surface has an area, and nothing is presented into it until then
// (2026-10-29: frame generation stayed at 0 generated frames after a minimize).
#include <cassert>
#include <cstdio>
#include <limits>

#include "gpu/shadps4/video_core/renderer_vulkan/present_target.h"

using Vulkan::ChoosePresentTarget;
using Vulkan::PresentExtent;
using Vulkan::PresentTarget;

int main() {
    constexpr PresentExtent k4k{3840, 2160};
    constexpr PresentExtent kWindowed{3682, 2071};
    constexpr PresentExtent kNone{0, 0};
    int queries = 0;
    const auto surface = [&](PresentExtent extent) {
        return [&queries, extent] {
            ++queries;
            return extent;
        };
    };

    // Normal frames: present, without asking the surface.
    assert(ChoosePresentTarget(k4k, k4k, k4k, false, surface(k4k)) == PresentTarget::Present);
    assert(queries == 0);
    // Resized, or frame generation switched: made again.
    assert(ChoosePresentTarget(kWindowed, k4k, k4k, false, surface(kWindowed)) ==
           PresentTarget::Recreate);
    assert(ChoosePresentTarget(k4k, k4k, k4k, true, surface(k4k)) == PresentTarget::Recreate);
    assert(queries == 0);

    // The bug: minimized, a failed present made the swapchain at the surface's 0x0 while it was
    // still asked for the window's (unchanged) size. Before, the size check matched and every
    // frame presented into 0x0. Now it is skipped while the surface has no area ...
    assert(ChoosePresentTarget(kWindowed, kWindowed, kNone, false, surface(kNone)) ==
           PresentTarget::Skip);
    assert(queries == 1);
    // ... and made again once restored, at the same window size.
    assert(ChoosePresentTarget(kWindowed, kWindowed, kNone, false, surface(kWindowed)) ==
           PresentTarget::Recreate);
    assert(queries == 2);
    // A platform that lets the swapchain choose (UINT32_MAX) has an area.
    constexpr auto kAny = std::numeric_limits<std::uint32_t>::max();
    assert(ChoosePresentTarget(k4k, k4k, kNone, false, surface({kAny, kAny})) ==
           PresentTarget::Recreate);
    // One side 0 is no area either.
    assert(ChoosePresentTarget(k4k, k4k, {3840, 0}, false, surface({0, 2160})) ==
           PresentTarget::Skip);

    // A 0x0 window (SDL reported it) is skipped without a surface query.
    queries = 0;
    assert(ChoosePresentTarget(kNone, k4k, k4k, false, surface(k4k)) == PresentTarget::Skip);
    assert(queries == 0);

    std::puts("present target: ok");
    return 0;
}
