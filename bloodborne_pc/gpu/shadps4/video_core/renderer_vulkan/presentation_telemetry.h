// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <cstdint>
#include <optional>

namespace Vulkan {

// Present-thread owned. A snapshot of independently published generation totals
// is not a coherent cross-thread transaction; evaluation and accepted
// presentation are distinct.
class PresentationTelemetry {
public:
    static constexpr int64_t IntervalMs = 5000;
    struct Counters {
        uint64_t dlss_pairs{}, fsr_pairs{}, generated{}, accepted_generated{};
        uint64_t game_images{}, accepted_images{}, unpresented_generated{}, failed_presents{};
    };
    struct Report {
        double seconds;
        Counters totals, delta;
        double GamePresentFps() const { return delta.game_images / seconds; }
        double AcceptedImageFps() const { return delta.accepted_images / seconds; }
    };

    std::optional<Report> Poll(int64_t now_ms, const Counters& current) {
        if (!started || now_ms < last_seen_ms || Regressed(current, last_seen)) {
            started = true;
            last_ms = now_ms;
            last_seen_ms = now_ms;
            previous = current;
            last_seen = current;
            return std::nullopt;
        }
        last_seen = current;
        last_seen_ms = now_ms;
        if (now_ms - last_ms < IntervalMs) {
            return std::nullopt;
        }
        const Counters delta{
            current.dlss_pairs - previous.dlss_pairs,
            current.fsr_pairs - previous.fsr_pairs,
            current.generated - previous.generated,
            current.accepted_generated - previous.accepted_generated,
            current.game_images - previous.game_images,
            current.accepted_images - previous.accepted_images,
            current.unpresented_generated - previous.unpresented_generated,
            current.failed_presents - previous.failed_presents,
        };
        const Report report{double(now_ms - last_ms) / 1000.0, current, delta};
        last_ms = now_ms;
        previous = current;
        return report;
    }

private:
    static bool Regressed(const Counters& c, const Counters& last) {
        return c.dlss_pairs < last.dlss_pairs || c.fsr_pairs < last.fsr_pairs ||
               c.generated < last.generated || c.accepted_generated < last.accepted_generated ||
               c.game_images < last.game_images || c.accepted_images < last.accepted_images ||
               c.unpresented_generated < last.unpresented_generated ||
               c.failed_presents < last.failed_presents;
    }
    bool started{};
    int64_t last_ms{}, last_seen_ms{};
    Counters previous{}, last_seen{};
};

} // namespace Vulkan
