// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: what Presenter::RecreateFrame does when a presentation image cannot be allocated.
// Seen in 3.3.3 testing (ErrorInitializationFailed in the minute ReShade's installer
// registered its Vulkan layer) and in a 3.4.0 15-minute run, where the retry once idle failed
// too: the presenter asserted and the game exited.
// Now a failed allocation keeps the frame's previous image (the caller renders at the old size)
// or goes on without an optional one (HUD-free copy, HDR scratch). With such a fallback it is
// never fatal: the caller tries again after 1, 2, 4, 8... frames (ShouldRetry), at most
// MaxBackoffFrames apart, so a lasting error costs one attempt every ~2 s instead of one per
// frame. It stays fatal only when the caller has no fallback (a first presentation image,
// after a few retries). Each caller passes its own policy: a policy is used by one thread.
#pragma once

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>

namespace Vulkan {

class FrameRecreatePolicy {
public:
    enum class Action { KeepOld, Fatal };
    /// The longest wait between two attempts: about two seconds of frames at 60 FPS.
    static constexpr std::uint32_t MaxBackoffFrames = 120;

    /// After a failed allocation. `has_fallback`: the caller can go on without the new image
    /// (the frame keeps its previous one, or the image is optional).
    Action OnFailure(bool has_fallback) noexcept {
        ++failures;
        if (!has_fallback) {
            return Action::Fatal;
        }
        skip = BackoffFrames(failures) - 1;
        return Action::KeepOld;
    }
    void OnSuccess() noexcept {
        failures = 0;
        skip = 0;
    }
    /// Once per frame that wants the image: false while backing off (the caller keeps the
    /// old or optional image and does not attempt, nor wait for the GPU).
    [[nodiscard]] bool ShouldRetry() noexcept {
        if (skip == 0) {
            return true;
        }
        --skip;
        return false;
    }
    /// After the `count`th failure in a row, the next attempt is this many frames later
    /// (1, 2, 4, 8..., at most MaxBackoffFrames).
    [[nodiscard]] static constexpr std::uint32_t BackoffFrames(std::uint32_t count) noexcept {
        return count <= 1 ? 1u
                          : std::min<std::uint32_t>(1u << std::min<std::uint32_t>(count - 1, 16u),
                                                    MaxBackoffFrames);
    }
    /// Log the 1st, 2nd, 4th, 8th... failure in a row, not every attempt.
    [[nodiscard]] bool ShouldLog() const noexcept { return ShouldLogCount(failures); }
    /// Whether the `count`th failure in a row is logged (1, 2, 4, 8...).
    [[nodiscard]] static constexpr bool ShouldLogCount(std::uint32_t count) noexcept {
        return count != 0 && (count & (count - 1)) == 0;
    }
    [[nodiscard]] std::uint32_t Failures() const noexcept { return failures; }

private:
    std::uint32_t failures = 0;
    std::uint32_t skip = 0; ///< frames left before the next attempt
};

/// BB_TEST_FRAME_ALLOC_FAILS=N[@M]: N presentation image allocations fail, starting with the
/// first one after M presented game frames (no @M or M=0: from the start of the process,
/// where only first images are made). With M past boot, a resize, the HUD-free copy (frame
/// generation on) or the HDR scratch (HDR on) then exercises the keep-old / optional paths.
struct FrameAllocFailTest {
    int count = 0;
    std::uint64_t after_frames = 0;

    [[nodiscard]] static FrameAllocFailTest Parse(const char* text) noexcept {
        FrameAllocFailTest test{};
        if (!text) {
            return test;
        }
        test.count = std::max(0, std::atoi(text));
        if (const char* at = std::strchr(text, '@')) {
            test.after_frames = std::uint64_t(std::max(0LL, std::atoll(at + 1)));
        }
        return test;
    }
};

} // namespace Vulkan
