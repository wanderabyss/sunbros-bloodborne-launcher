#include <cassert>
#include <cmath>
#include <cstdio>

#include "gpu/shadps4/video_core/renderer_vulkan/frame_handoff.h"

int main() {
    using namespace std::chrono;
    using Vulkan::FrameHandoff;
    using T = Vulkan::FrameHandoffTimings;
    const auto at = [](int ms) { return FrameHandoff::Time{} + milliseconds(ms); };
    FrameHandoff frame{at(1), at(11), at(12), at(16), at(18)};
    T timings;
    assert(timings.Add(frame, at(21)));
    frame.work_started = {};
    assert(timings.Add(frame, at(23)));
    auto report = timings.Take();
    assert(report.samples == 2 && report.work_samples == 1 && report.invalid == 0);
    assert(report.Mean(T::Work) == 10.0);
    assert(report.Mean(T::Publish) == 1.0);
    assert(report.Mean(T::VideoOut) == 4.0);
    assert(report.Mean(T::Dispatch) == 2.0);
    assert(report.Mean(T::Swap) == 4.0 && report.maximum[T::Swap] == 5.0);
    assert(report.Mean(T::ReadyToPresent) == 11.0);
    assert(report.Mean(T::Publish) + report.Mean(T::VideoOut) + report.Mean(T::Dispatch) +
               report.Mean(T::Swap) ==
           report.Mean(T::ReadyToPresent));
    assert(timings.Take().samples == 0);
    assert(!timings.Add({}, at(23))); // Blank frame is not an invalid game sample.
    for (int stage = 0; stage < 5; ++stage) {
        auto bad = frame;
        switch (stage) {
        case 0:
            bad.work_started = at(12);
            break;
        case 1:
            bad.published = at(10);
            break;
        case 2:
            bad.videoout_dequeued = at(11);
            break;
        case 3:
            bad.swap_queued = at(15);
            break;
        case 4:
            bad.swap_queued = at(24);
            break;
        }
        assert(!timings.Add(bad, at(23)));
    }
    report = timings.Take();
    assert(report.invalid == 5 && report.samples == 0);
    assert(report.Mean(T::Work) == 0.0 && report.Mean(T::ReadyToPresent) == 0.0);
    std::puts("frame handoff tests passed");
}
