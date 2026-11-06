// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: VK_EXT_hdr_metadata's values and when to send them (Swapchain::SetHdrMetadata).
// Header only and free of Vulkan, so that test_hdr_metadata.cpp can run it on its own.
#pragma once

namespace Vulkan::HdrMetadata {

struct Values {
    float red_x, red_y;
    float green_x, green_y;
    float blue_x, blue_y;
    float white_x, white_y;
    float max_luminance, min_luminance;
    float max_content_light_level;
    float max_frame_average_light_level; // 0: unknown
};

/// BT.2020 primaries and D65, the HDR10 swapchain's; the light levels are the resolved peak.
constexpr Values ForPeak(float peak) {
    return {
        .red_x = 0.708f,
        .red_y = 0.292f,
        .green_x = 0.170f,
        .green_y = 0.797f,
        .blue_x = 0.131f,
        .blue_y = 0.046f,
        .white_x = 0.3127f,
        .white_y = 0.3290f,
        .max_luminance = peak,
        .min_luminance = 0.0f,
        .max_content_light_level = peak,
        .max_frame_average_light_level = 0.0f,
    };
}

/// The overlay's peak slider stores a new value on every frame of a drag and the call's cost is up
/// to the driver, so a changed peak waits this long after the last send. The value the drag ends on
/// goes out once this has passed: the check runs on every frame.
inline constexpr double MinSecondsBetweenChanges = 0.25;

/// `sent_peak` is 0 for a swapchain nothing was sent to yet, which never waits.
constexpr bool ShouldSend(bool hdr_swapchain, bool extension, float peak, float sent_peak,
                          double seconds_since_send) {
    if (!hdr_swapchain || !extension || !(peak > 0.0f) || peak == sent_peak) {
        return false;
    }
    return sent_peak == 0.0f || seconds_since_send >= MinSecondsBetweenChanges;
}

} // namespace Vulkan::HdrMetadata
