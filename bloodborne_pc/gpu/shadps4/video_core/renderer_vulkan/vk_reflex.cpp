// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: NVIDIA Reflex Low Latency through VK_NV_low_latency2 (see vk_reflex.h).

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <vector>

#include "bbport_settings.h"
#include "video_core/renderer_vulkan/vk_reflex.h"

namespace Vulkan {

namespace {

// A sleep the driver never ends (swapchain gone, driver trouble) must not stop the game.
constexpr u64 kSleepTimeoutNs = 100'000'000; // 100 ms
constexpr auto kReportInterval = std::chrono::seconds(30);

int WantedMode() {
    auto& s = BbSettings::Get();
    const int requested = std::clamp(s.reflex.load(), 0, BbSettings::ReflexModeCount - 1);
    const int fg = s.frame_gen.load();
    return BbSettings::EffectiveReflexMode(requested, fg);
}

// BB_REFLEX_MEASURE=1: with Reflex off, the markers and the latency report still run (no sleep,
// low latency mode off), for comparing off with on.
bool MeasureOnly() {
    static const bool measure = [] {
        const char* env = std::getenv("BB_REFLEX_MEASURE");
        return env && env[0] == '1';
    }();
    return measure;
}

} // namespace

Reflex& Reflex::Get() {
    static Reflex reflex;
    return reflex;
}

void Reflex::Init(vk::Device device_, bool supported_) {
    std::scoped_lock lock{mutex};
    device = device_;
    supported = supported_ && VULKAN_HPP_DEFAULT_DISPATCHER.vkLatencySleepNV &&
                VULKAN_HPP_DEFAULT_DISPATCHER.vkSetLatencySleepModeNV &&
                VULKAN_HPP_DEFAULT_DISPATCHER.vkSetLatencyMarkerNV &&
                VULKAN_HPP_DEFAULT_DISPATCHER.vkGetLatencyTimingsNV;
    if (supported) {
        const vk::SemaphoreTypeCreateInfo type{
            .semaphoreType = vk::SemaphoreType::eTimeline,
            .initialValue = 0,
        };
        const auto [result, semaphore] = device.createSemaphore({.pNext = &type});
        if (result == vk::Result::eSuccess) {
            sleep_semaphore = semaphore;
        } else {
            supported = false;
        }
    }
    BbSettings::Get().reflex_supported = supported;
    std::printf("Reflex: %s\n", supported ? "available (VK_NV_low_latency2)"
                                          : "unavailable (needs an NVIDIA GPU and driver with "
                                            "VK_NV_low_latency2)");
}

void Reflex::OnSwapchainCreated(vk::SwapchainKHR swapchain_) {
    std::scoped_lock lock{mutex};
    if (!supported) {
        return;
    }
    swapchain = swapchain_;
    current_id = pending_pace_id = 0;
    work_started = {};
    applied_mode = -1; // a new swapchain starts with Reflex off: apply the setting again
    ApplyModeLocked(WantedMode());
}

void Reflex::OnSwapchainDestroyed(vk::SwapchainKHR swapchain_) {
    std::scoped_lock lock{mutex};
    if (swapchain == swapchain_) {
        swapchain = vk::SwapchainKHR{};
        applied_mode = -1;
        current_id = pending_pace_id = 0;
        work_started = {};
    }
}

void Reflex::ApplyModeLocked(int mode) {
    if (!swapchain || mode == applied_mode) {
        return;
    }
    // No minimum interval: the port's frame limiter keeps pacing the game's flips.
    const VkLatencySleepModeInfoNV info{
        .sType = VK_STRUCTURE_TYPE_LATENCY_SLEEP_MODE_INFO_NV,
        .lowLatencyMode = mode != BbSettings::ReflexOff,
        .lowLatencyBoost = mode == BbSettings::ReflexBoost,
        .minimumIntervalUs = 0,
    };
    const VkResult result = VULKAN_HPP_DEFAULT_DISPATCHER.vkSetLatencySleepModeNV(
        static_cast<VkDevice>(device), static_cast<VkSwapchainKHR>(swapchain), &info);
    if (result != VK_SUCCESS) {
        std::printf("Reflex: the driver refused mode %s (%d)\n", BbSettings::ReflexName(mode),
                    int(result));
        applied_mode = mode; // not asked again for every frame
        return;
    }
    if (applied_mode != -1 || mode != BbSettings::ReflexOff) {
        std::printf("Reflex: %s\n", mode == BbSettings::ReflexBoost ? "on, boost"
                                    : mode == BbSettings::ReflexOn  ? "on"
                                                                     : "off");
    }
    applied_mode = mode;
    auto& settings = BbSettings::Get();
    settings.status.effective_reflex.store(mode, std::memory_order_relaxed);
    const bool forced = (mode != settings.reflex.load() &&
                         settings.frame_gen.load() == BbSettings::FrameGenDlss);
    settings.status.reflex_forced_by_fg.store(forced, std::memory_order_relaxed);
}

void Reflex::MarkLocked(u64 id, vk::LatencyMarkerNV marker) {
    if (!swapchain || id == 0) {
        return;
    }
    const VkSetLatencyMarkerInfoNV info{
        .sType = VK_STRUCTURE_TYPE_SET_LATENCY_MARKER_INFO_NV,
        .presentID = id,
        .marker = static_cast<VkLatencyMarkerNV>(marker),
    };
    VULKAN_HPP_DEFAULT_DISPATCHER.vkSetLatencyMarkerNV(
        static_cast<VkDevice>(device), static_cast<VkSwapchainKHR>(swapchain), &info);
}

u64 Reflex::OnFlip() {
    std::scoped_lock lock{mutex};
    if (!supported) {
        return 0;
    }
    ApplyModeLocked(WantedMode());
    if ((applied_mode <= BbSettings::ReflexOff && !MeasureOnly()) || !swapchain) {
        current_id = 0;
        pending_pace_id = 0;
        work_started = {};
        return 0;
    }
    if (current_id == 0) {
        StartFrameLocked(); // the first frame after Reflex came on: it started before we knew
    }
    return current_id;
}

void Reflex::StartFrameLocked() {
    // The command thread translates and submits the game's GPU work all through a frame, so
    // its whole frame, up to the flip, is the render submission; the guest's own simulation is
    // not visible here (it is marked as an empty span at the start). Marking only the flip's
    // short submission as render submit made Reflex sleep the GPU dry: 72 -> 61 FPS and twice
    // the latency in GPU-bound play (2026-10-25, 4K DLAA + frame generation).
    current_id = next_id++;
    work_started = FrameHandoff::Enabled() ? FrameHandoff::Clock::now() : FrameHandoff::Time{};
    MarkLocked(current_id, vk::LatencyMarkerNV::eSimulationStart);
    MarkLocked(current_id, vk::LatencyMarkerNV::eSimulationEnd);
    MarkLocked(current_id, vk::LatencyMarkerNV::eRendersubmitStart);
}

Reflex::Submission Reflex::OnSubmitted(u64 id) {
    std::scoped_lock lock{mutex};
    if (!id || !swapchain || id != current_id || pending_pace_id == id) {
        return {};
    }
    MarkLocked(id, vk::LatencyMarkerNV::eRendersubmitEnd);
    pending_pace_id = id;
    return {id, work_started};
}

void Reflex::OnFrameQueued(u64 id) {
    VkSemaphore semaphore = VK_NULL_HANDLE;
    u64 value = 0;
    const bool timing = FrameHandoff::Enabled();
    double api_ms = 0.0, wait_ms = 0.0;
    bool called = false;
    VkResult api_result = VK_SUCCESS;
    {
        std::scoped_lock lock{mutex};
        if (!id || !swapchain || id != current_id || id != pending_pace_id) {
            return;
        }
        pending_pace_id = 0; // consume once, including failures and mode changes
        if (applied_mode > BbSettings::ReflexOff) {
            const VkLatencySleepInfoNV sleep{
                .sType = VK_STRUCTURE_TYPE_LATENCY_SLEEP_INFO_NV,
                .signalSemaphore = static_cast<VkSemaphore>(sleep_semaphore),
                .value = sleep_value + 1,
            };
            const auto begin = timing ? FrameHandoff::Clock::now() : FrameHandoff::Time{};
            called = true;
            api_result = VULKAN_HPP_DEFAULT_DISPATCHER.vkLatencySleepNV(
                static_cast<VkDevice>(device), static_cast<VkSwapchainKHR>(swapchain), &sleep);
            if (timing) {
                api_ms =
                    std::chrono::duration<double, std::milli>(FrameHandoff::Clock::now() - begin)
                        .count();
            }
            if (api_result == VK_SUCCESS) {
                semaphore = sleep.signalSemaphore;
                value = ++sleep_value;
            }
        }
    }
    vk::Result wait_result = vk::Result::eSuccess;
    // The wait itself is outside the lock: the present thread may recreate the
    // swapchain.
    if (semaphore != VK_NULL_HANDLE) {
        const vk::SemaphoreWaitInfo wait{
            .semaphoreCount = 1,
            .pSemaphores = reinterpret_cast<const vk::Semaphore *>(&semaphore),
            .pValues = &value,
        };
        const auto begin = timing ? FrameHandoff::Clock::now() : FrameHandoff::Time{};
        wait_result = device.waitSemaphores(wait, kSleepTimeoutNs);
        if (timing) {
            wait_ms = std::chrono::duration<double, std::milli>(FrameHandoff::Clock::now() - begin)
                          .count();
        }
    }
    char text[512];
    size_t length = 0;
    {
        std::scoped_lock lock{mutex};
        if (timing) {
            ++sleep_stats.frames;
            sleep_stats.calls += called;
            sleep_stats.waits += semaphore != VK_NULL_HANDLE;
            sleep_stats.timeouts += wait_result == vk::Result::eTimeout;
            sleep_stats.errors +=
                api_result != VK_SUCCESS ||
                (wait_result != vk::Result::eSuccess && wait_result != vk::Result::eTimeout);
            sleep_stats.api_ms += api_ms;
            sleep_stats.wait_ms += wait_ms;
            sleep_stats.max_wait_ms = std::max(sleep_stats.max_wait_ms, wait_ms);
            length = ReportSleepLocked(text, sizeof(text));
        }
        if (current_id != id) {
            // Swapchain recreation invalidated the work span while the lock was
            // released.
        } else if (!swapchain || (applied_mode <= BbSettings::ReflexOff && !MeasureOnly())) {
            current_id = 0;
            work_started = {};
        } else {
            StartFrameLocked();
        }
    }
    if (length) {
        std::fwrite(text, 1, length, stdout);
    }
}

size_t Reflex::ReportSleepLocked(char *text, size_t capacity) {
    const auto now = FrameHandoff::Clock::now();
    if (sleep_report_start == FrameHandoff::Time{}) {
        sleep_report_start = now;
        return 0;
    }
    if (now - sleep_report_start < std::chrono::seconds(5)) {
        return 0;
    }
    const auto &s = sleep_stats;
    const int length =
        std::snprintf(text, capacity,
                      "Reflex pacing CPU: %llu frames, %llu sleep calls, API %.3f ms/call, "
                      "semaphore wait %.3f ms/wait (max %.3f), %llu timeouts, %llu errors; "
                      "current frame published before next-frame sleep\n",
                      (unsigned long long)s.frames, (unsigned long long)s.calls,
                      s.calls ? s.api_ms / s.calls : 0.0, s.waits ? s.wait_ms / s.waits : 0.0,
                      s.max_wait_ms, (unsigned long long)s.timeouts, (unsigned long long)s.errors);
    sleep_stats = {};
    sleep_report_start = now;
    return length > 0 ? std::min(size_t(length), capacity - 1) : 0;
}
void Reflex::OnPresentStart(u64 id) {
    if (id == 0) {
        return; // no Reflex frame (off, a generated image, a frame shown again): no lock
    }
    std::scoped_lock lock{mutex};
    MarkLocked(id, vk::LatencyMarkerNV::ePresentStart);
}

void Reflex::OnPresentEnd(u64 id) {
    if (id == 0) {
        return;
    }
    std::scoped_lock lock{mutex};
    MarkLocked(id, vk::LatencyMarkerNV::ePresentEnd);
    ReportLocked();
}

void Reflex::ReportLocked() {
    const auto now = std::chrono::steady_clock::now();
    if (last_report == std::chrono::steady_clock::time_point{}) {
        last_report = now;
        return;
    }
    if (now - last_report < kReportInterval || !swapchain) {
        return;
    }
    last_report = now;
    VkGetLatencyMarkerInfoNV info{.sType = VK_STRUCTURE_TYPE_GET_LATENCY_MARKER_INFO_NV};
    const auto get = VULKAN_HPP_DEFAULT_DISPATCHER.vkGetLatencyTimingsNV;
    get(static_cast<VkDevice>(device), static_cast<VkSwapchainKHR>(swapchain), &info);
    if (info.timingCount == 0) {
        return;
    }
    std::vector<VkLatencyTimingsFrameReportNV> frames(
        info.timingCount, {.sType = VK_STRUCTURE_TYPE_LATENCY_TIMINGS_FRAME_REPORT_NV});
    info.pTimings = frames.data();
    get(static_cast<VkDevice>(device), static_cast<VkSwapchainKHR>(swapchain), &info);
    // From the start of a frame's work to the end of its present: what Reflex shortens.
    double total_ms = 0.0;
    u32 count = 0;
    for (u32 i = 0; i < info.timingCount; ++i) {
        const auto& f = frames[i];
        if (f.simStartTimeUs != 0 && f.presentEndTimeUs > f.simStartTimeUs) {
            total_ms += double(f.presentEndTimeUs - f.simStartTimeUs) / 1000.0;
            ++count;
        }
    }
    if (count != 0) {
        const float avg_ms = float(total_ms / count);
        BbSettings::Get().status.reflex_latency_ms.store(avg_ms, std::memory_order_relaxed);
        std::printf("Reflex: %s, frame start to present %.1f ms (average of the last %u frames)\n",
                    BbSettings::ReflexName(applied_mode), double(avg_ms), count);
    }
}

} // namespace Vulkan
