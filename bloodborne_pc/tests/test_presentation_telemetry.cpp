// SPDX-License-Identifier: GPL-2.0-or-later
#include "gpu/shadps4/video_core/renderer_vulkan/presentation_telemetry.h"
#include "gpu/shadps4/video_core/renderer_vulkan/frame_recreate.h"
#include <cassert>
#include <cmath>
#include <cstdio>

using Vulkan::PresentationTelemetry;

// Presenter::RecreateFrame (S2): a failed resize keeps the previous image and backs off; fatal
// only without one.
static void TestFrameRecreatePolicy() {
    using Vulkan::FrameRecreatePolicy;
    using Action = FrameRecreatePolicy::Action;
    FrameRecreatePolicy first;
    assert(first.OnFailure(false) == Action::Fatal); // nothing to keep: a real error
    FrameRecreatePolicy policy;
    assert(!policy.ShouldLog() && policy.ShouldRetry());
    assert(policy.OnFailure(true) == Action::KeepOld && policy.ShouldLog());
    assert(policy.ShouldRetry()); // after the 1st: the next frame tries again
    assert(policy.OnFailure(true) == Action::KeepOld && policy.ShouldLog()); // 2nd
    assert(!policy.ShouldRetry() && policy.ShouldRetry()); // 2 frames later
    assert(policy.OnFailure(true) == Action::KeepOld && !policy.ShouldLog()); // 3rd: quiet
    for (int i = 0; i < 3; ++i) {
        assert(!policy.ShouldRetry()); // 4 frames later
    }
    assert(policy.ShouldRetry());
    assert(policy.OnFailure(true) == Action::KeepOld && policy.ShouldLog()); // 4th
    policy.OnSuccess();
    assert(policy.Failures() == 0 && !policy.ShouldLog() && policy.ShouldRetry());
    // With a fallback never fatal; the wait grows to about 2 s at 60 FPS and stays there.
    for (std::uint32_t i = 0; i < 1000; ++i) {
        assert(policy.OnFailure(true) == Action::KeepOld);
    }
    std::uint32_t skipped = 0;
    while (!policy.ShouldRetry()) {
        ++skipped;
    }
    assert(skipped + 1 == FrameRecreatePolicy::MaxBackoffFrames);
    assert(FrameRecreatePolicy::BackoffFrames(1) == 1 && FrameRecreatePolicy::BackoffFrames(4) == 8 &&
           FrameRecreatePolicy::BackoffFrames(8) == FrameRecreatePolicy::MaxBackoffFrames &&
           FrameRecreatePolicy::BackoffFrames(0xFFFFFFFFu) == FrameRecreatePolicy::MaxBackoffFrames);
    policy.OnSuccess();
    assert(policy.OnFailure(true) == Action::KeepOld && policy.Failures() == 1); // reset
    assert(policy.OnFailure(false) == Action::Fatal); // a first image still has no fallback
    // The heap report before the retry once idle follows the same cadence (count + 1).
    assert(!FrameRecreatePolicy::ShouldLogCount(0) && FrameRecreatePolicy::ShouldLogCount(1) &&
           FrameRecreatePolicy::ShouldLogCount(8) && !FrameRecreatePolicy::ShouldLogCount(12));
}

// BB_TEST_FRAME_ALLOC_FAILS=N[@M].
static void TestFrameAllocFailTest() {
    using Vulkan::FrameAllocFailTest;
    const auto parse = FrameAllocFailTest::Parse;
    assert(parse(nullptr).count == 0 && parse(nullptr).after_frames == 0);
    assert(parse("3").count == 3 && parse("3").after_frames == 0); // from boot, as before
    assert(parse("3@600").count == 3 && parse("3@600").after_frames == 600);
    assert(parse("2@0").count == 2 && parse("2@0").after_frames == 0);
    assert(parse("-1@-5").count == 0 && parse("-1@-5").after_frames == 0);
    assert(parse("x").count == 0);
}

int main() {
    TestFrameRecreatePolicy();
    TestFrameAllocFailTest();
    PresentationTelemetry telemetry;
    PresentationTelemetry::Counters counts{};
    assert(!telemetry.Poll(0, counts)); // zero is a valid clock epoch
    counts = {300, 0, 300, 180, 300, 480, 120, 0};
    assert(!telemetry.Poll(4999, counts));
    const auto busy = telemetry.Poll(5000, counts);
    assert(busy && busy->seconds == 5.0);
    assert(busy->delta.generated == 300 && busy->delta.accepted_generated == 180);
    assert(busy->totals.unpresented_generated == 120);
    assert(std::abs(busy->GamePresentFps() - 60.0) < 0.001);
    assert(std::abs(busy->AcceptedImageFps() - 96.0) < 0.001); // not assumed to be 120
    assert(!telemetry.Poll(5000, counts)); // no repeated log at the same timestamp
    assert(!telemetry.Poll(9999, counts));
    const auto idle = telemetry.Poll(10000, counts);
    assert(idle && idle->delta.generated == 0 && idle->GamePresentFps() == 0.0);
    assert(idle->totals.accepted_generated == 180); // idle never erases successful totals

    // A provider change accumulates separate successful-pair totals. Failed
    // presents and unpresented images remain separate from successful
    // evaluations.
    counts.fsr_pairs += 200;
    counts.generated += 200;
    counts.accepted_generated += 100;
    counts.game_images += 150;
    counts.accepted_images += 250;
    counts.unpresented_generated += 100;
    counts.failed_presents += 1;
    const auto fallback = telemetry.Poll(15000, counts);
    assert(fallback && fallback->delta.dlss_pairs == 0 && fallback->delta.fsr_pairs == 200);
    assert(fallback->delta.failed_presents == 1 && fallback->delta.accepted_generated == 100);
    assert(fallback->AcceptedImageFps() == 50.0);

    assert(!telemetry.Poll(1, counts)); // clock regression resets the baseline
    const auto resumed = telemetry.Poll(5001, counts);
    assert(resumed && resumed->delta.accepted_images == 0);
    counts = {}; // counter reset must not underflow unsigned deltas
    assert(!telemetry.Poll(6000, counts));
    assert(telemetry.Poll(11000, counts)->delta.generated == 0);

    PresentationTelemetry between_reports;
    assert(!between_reports.Poll(0, {}));
    counts.generated = 100;
    assert(!between_reports.Poll(1000, counts));
    counts.generated = 10;
    assert(!between_reports.Poll(2000,
                                 counts)); // detect reset before the first report
    assert(!between_reports.Poll(5000, counts));
    counts.generated = 20;
    assert(between_reports.Poll(7000, counts)->delta.generated == 10);

    PresentationTelemetry clock_between_reports;
    assert(!clock_between_reports.Poll(0, {}));
    assert(!clock_between_reports.Poll(4000, {}));
    assert(!clock_between_reports.Poll(3000, {})); // regression inside the report interval
    assert(!clock_between_reports.Poll(5000, {}));
    assert(clock_between_reports.Poll(8000, {})->seconds == 5.0);
    std::puts("presentation telemetry PASS: cadence, independent counters, "
              "rates, idle and resets; frame recreate policy and failure injection");
}
