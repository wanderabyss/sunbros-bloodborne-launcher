// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: NVIDIA Reflex Low Latency through the Vulkan extension VK_NV_low_latency2 (with
// VK_KHR_present_id). No NVIDIA code: the driver does the work; other GPUs never enable it.
//
// A guest frame here: the GPU command thread translates the game's work for it, Presenter::
// PrepareFrame submits it at the game's flip, and the present thread shows it. Reflex sleeps on
// the command thread after submission and publication to VideoOut (after BB_FRAMES_AHEAD), so the
// next frame's work starts as late as the GPU allows; the guest's vblank and flip timing, which
// the game's speed follows, are untouched (no minimum interval: the port's limiter paces).
// Markers per frame id: after the sleep SIMULATION_START/END (empty: the guest's simulation is
// not visible here) and RENDERSUBMIT_START - the command thread submits the frame's GPU work
// until the flip - then RENDERSUBMIT_END after the flip's submission, PRESENT_START/END around
// the game's own present (with its present id). Generated frames are left out.

#pragma once

#include <chrono>
#include <mutex>

#include "common/types.h"
#include "video_core/renderer_vulkan/frame_handoff.h"
#include "video_core/renderer_vulkan/vk_common.h"

namespace Vulkan {

class Reflex {
public:
    static Reflex& Get();

    /// After device creation; `supported`: VK_NV_low_latency2 and present ids were enabled.
    void Init(vk::Device device, bool supported);
    [[nodiscard]] bool Supported() const noexcept {
        return supported;
    }
    /// The swapchain create info chains VkSwapchainLatencyCreateInfoNV when this is true.
    [[nodiscard]] bool WantsLatencySwapchain() const noexcept {
        return supported;
    }
    void OnSwapchainCreated(vk::SwapchainKHR swapchain);
    void OnSwapchainDestroyed(vk::SwapchainKHR swapchain);

    /// Command thread, at the game's flip: returns the current work span's id (0 while off).
    u64 OnFlip();
    struct Submission {
        u64 id{};
        FrameHandoff::Time started{};
    };
    /// End submission before publication; does not request or wait for a driver sleep.
    Submission OnSubmitted(u64 id);
    /// After the current frame was queued and its consumer notified: pace the next frame.
    /// The caller must copy id before publication and not read the published Frame again.
    void OnFrameQueued(u64 id);
    /// Present thread, around the game's own present of frame `id` (0: nothing).
    void OnPresentStart(u64 id);
    void OnPresentEnd(u64 id);

private:
    Reflex() = default;
    void ApplyModeLocked(int mode);
    void StartFrameLocked();
    void MarkLocked(u64 id, vk::LatencyMarkerNV marker);
    void ReportLocked();
    size_t ReportSleepLocked(char* text, size_t capacity);

    std::mutex mutex;
    vk::Device device{};
    bool supported = false;
    vk::SwapchainKHR swapchain{};
    vk::Semaphore sleep_semaphore{}; ///< timeline, signalled by the driver when a sleep ends
    u64 sleep_value = 0;
    int applied_mode = -1; ///< BbSettings reflex mode applied to `swapchain`, -1 none
    u64 next_id = 1;
    u64 current_id = 0; ///< the frame being simulated, 0 before the first
    u64 pending_pace_id = 0; ///< submitted, not yet consumed by OnFrameQueued
    FrameHandoff::Time work_started{};
    struct SleepStats {
        u64 frames{}, calls{}, waits{}, timeouts{}, errors{};
        double api_ms{}, wait_ms{}, max_wait_ms{};
    } sleep_stats;
    FrameHandoff::Time sleep_report_start{};
    std::chrono::steady_clock::time_point last_report{};
};

} // namespace Vulkan
