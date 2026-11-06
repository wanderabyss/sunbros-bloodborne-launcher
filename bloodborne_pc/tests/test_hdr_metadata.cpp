// bbport: VK_EXT_hdr_metadata's values and when they're sent (hdr_metadata.h).
#include <cassert>

#include "shadps4/video_core/renderer_vulkan/hdr_metadata.h"

using Vulkan::HdrMetadata::ForPeak;
using Vulkan::HdrMetadata::MinSecondsBetweenChanges;
using Vulkan::HdrMetadata::ShouldSend;

int main() {
    // BT.2020, D65, and the peak as both luminance and content light level.
    const auto v = ForPeak(1000.0f);
    assert(v.red_x == 0.708f && v.red_y == 0.292f);
    assert(v.green_x == 0.170f && v.green_y == 0.797f);
    assert(v.blue_x == 0.131f && v.blue_y == 0.046f);
    assert(v.white_x == 0.3127f && v.white_y == 0.3290f);
    assert(v.max_luminance == 1000.0f && v.min_luminance == 0.0f);
    assert(v.max_content_light_level == 1000.0f);
    assert(v.max_frame_average_light_level == 0.0f);
    assert(ForPeak(460.0f).max_luminance == 460.0f);

    constexpr double later = MinSecondsBetweenChanges;

    // First send on a swapchain, including right after a send to the one it replaced.
    assert(ShouldSend(true, true, 1000.0f, 0.0f, 0.0));
    // Not on an SDR swapchain, without the extension, or without a peak.
    assert(!ShouldSend(false, true, 1000.0f, 0.0f, later));
    assert(!ShouldSend(true, false, 1000.0f, 0.0f, later));
    assert(!ShouldSend(true, true, 0.0f, 0.0f, later));
    // The same peak isn't sent again.
    assert(!ShouldSend(true, true, 1000.0f, 1000.0f, later * 100.0));
    // A changed peak waits, then goes out: the frame after a drag ends sends the last value.
    assert(!ShouldSend(true, true, 1100.0f, 1000.0f, 0.0));
    assert(!ShouldSend(true, true, 1100.0f, 1000.0f, later * 0.5));
    assert(ShouldSend(true, true, 1100.0f, 1000.0f, later));

    // Simulated: a 60-frame drag at 60 fps, from 1000 to 1059, then still.
    float sent = 0.0f;
    double since = 0.0;
    int sends = 0;
    for (int frame = 0; frame < 120; ++frame) {
        const float peak = 1000.0f + float(frame < 60 ? frame : 59);
        if (ShouldSend(true, true, peak, sent, since)) {
            sent = peak;
            since = 0.0;
            ++sends;
        }
        since += 1.0 / 60.0;
    }
    assert(sent == 1059.0f);
    assert(sends <= 6);
    return 0;
}
