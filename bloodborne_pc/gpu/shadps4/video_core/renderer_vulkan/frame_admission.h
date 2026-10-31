// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <optional>

namespace Vulkan {

// Backpressure applies AFTER publication. The VideoOut consumer must acknowledge before
// doing presentation/GPU work, so admission never waits for generated images to finish.
class FrameAdmission {
  public:
    using Clock = std::chrono::steady_clock;
    enum class Result { Consumed, Bypassed, Timeout, Stopped };
    struct Report {
        uint64_t published{}, consumed{}, pending{}, peak_pending{};
        uint64_t gated{}, bypassed{}, blocked{}, timeouts{}, stopped{};
        double wait_ms{}, max_wait_ms{};
    };

    uint64_t Publish() {
        std::scoped_lock lock{mutex};
        ++published;
        report.peak_pending = std::max(report.peak_pending, published - consumed);
        return published;
    }

    void Consume(uint64_t ticket) {
        {
            std::scoped_lock lock{mutex};
            // The driver consumes FIFO tickets. Ignore stale/invalid acknowledgements.
            if (ticket != consumed + 1 || ticket > published) {
                return;
            }
            consumed = ticket;
        }
        cv.notify_all();
    }

    Result Wait(uint64_t ticket, bool enabled,
                Clock::duration timeout = std::chrono::milliseconds(100)) {
        std::unique_lock lock{mutex};
        if (!enabled) {
            ++report.bypassed;
            return Result::Bypassed;
        }
        ++report.gated;
        const auto start = Clock::now();
        if (consumed < ticket && !stopping) {
            ++report.blocked;
            cv.wait_for(lock, timeout, [&] { return consumed >= ticket || stopping; });
        }
        const double ms = std::chrono::duration<double, std::milli>(Clock::now() - start).count();
        report.wait_ms += ms;
        report.max_wait_ms = std::max(report.max_wait_ms, ms);
        if (stopping) {
            ++report.stopped;
            return Result::Stopped;
        }
        if (consumed < ticket) {
            ++report.timeouts;
            return Result::Timeout;
        }
        return Result::Consumed;
    }

    void Stop() {
        {
            std::scoped_lock lock{mutex};
            stopping = true;
        }
        cv.notify_all();
    }

    std::optional<Report> Poll(Clock::time_point now = Clock::now()) {
        std::scoped_lock lock{mutex};
        if (now < last_report) {
            last_report = now;
            return {};
        }
        if (now - last_report < std::chrono::seconds(5)) {
            return {};
        }
        auto result = report;
        result.published = published;
        result.consumed = consumed;
        result.pending = published - consumed;
        report = {};
        report.peak_pending = result.pending;
        last_report = now;
        return result;
    }

  private:
    std::mutex mutex;
    std::condition_variable cv;
    uint64_t published{}, consumed{};
    bool stopping = false;
    Report report{};
    Clock::time_point last_report = Clock::now();
};

} // namespace Vulkan
