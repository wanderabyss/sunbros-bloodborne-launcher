// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>

namespace Vulkan {

// CPU timestamps transferred with ownership of a frame, never written after
// publication by its producer. These are not GPU completion or physical display
// timestamps.
struct FrameHandoff {
    using Clock = std::chrono::steady_clock;
    using Time = Clock::time_point;
    Time work_started{}, prepared{}, published{}, videoout_dequeued{}, swap_queued{};

    static bool Enabled() {
        static const bool enabled = [] {
            const char *value = std::getenv("BB_FPS_LOG");
            return value && value[0] && value[0] != '0';
        }();
        return enabled;
    }
};

class FrameHandoffTimings {
  public:
    enum Stage { Work, Publish, VideoOut, Dispatch, Swap, ReadyToPresent, StageCount };
    struct Report {
        uint64_t samples{}, work_samples{}, invalid{};
        std::array<double, StageCount> sum{}, maximum{};
        double Mean(Stage stage) const {
            const auto count = stage == Work ? work_samples : samples;
            return count ? sum[stage] / double(count) : 0.0;
        }
    };

    bool Add(const FrameHandoff &frame, FrameHandoff::Time present_start) {
        const auto zero = FrameHandoff::Time{};
        if (frame.prepared == zero) {
            return false; // blank/reused frames do not have a new handoff
        }
        if (frame.published < frame.prepared || frame.videoout_dequeued < frame.published ||
            frame.swap_queued < frame.videoout_dequeued || present_start < frame.swap_queued ||
            (frame.work_started != zero && frame.work_started > frame.prepared)) {
            ++report.invalid;
            return false;
        }
        const auto ms = [](auto duration) {
            return std::chrono::duration<double, std::milli>(duration).count();
        };
        const std::array<double, StageCount> values{
            frame.work_started != zero ? ms(frame.prepared - frame.work_started) : 0.0,
            ms(frame.published - frame.prepared),
            ms(frame.videoout_dequeued - frame.published),
            ms(frame.swap_queued - frame.videoout_dequeued),
            ms(present_start - frame.swap_queued),
            ms(present_start - frame.prepared),
        };
        ++report.samples;
        report.work_samples += frame.work_started != zero;
        for (size_t stage = 0; stage < StageCount; ++stage) {
            report.sum[stage] += values[stage];
            report.maximum[stage] = std::max(report.maximum[stage], values[stage]);
        }
        return true;
    }

    Report Take() {
        const auto result = report;
        report = {};
        return result;
    }

  private:
    Report report{};
};

} // namespace Vulkan
