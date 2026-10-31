// Exercises the production Reflex state machine without a GPU or NVIDIA driver.
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <vector>

#include "bbport_settings.h"
#include "video_core/renderer_vulkan/vk_reflex.h"

VULKAN_HPP_DEFAULT_DISPATCH_LOADER_DYNAMIC_STORAGE

namespace {
using Vulkan::Reflex;
struct Marker {
    uint64_t id;
    VkLatencyMarkerNV kind;
};
std::vector<Marker> markers;
bool published = false, recreate_during_wait = false;
unsigned sleeps = 0, waits = 0;
uint64_t presenting_id = 0;
VkResult sleep_result = VK_SUCCESS, wait_result = VK_SUCCESS;
const auto swapchain = reinterpret_cast<VkSwapchainKHR>(uintptr_t(2));

VKAPI_ATTR VkResult VKAPI_CALL CreateSemaphore(VkDevice, const VkSemaphoreCreateInfo *,
                                               const VkAllocationCallbacks *, VkSemaphore *out) {
    *out = reinterpret_cast<VkSemaphore>(uintptr_t(3));
    return VK_SUCCESS;
}
VKAPI_ATTR VkResult VKAPI_CALL SetMode(VkDevice, VkSwapchainKHR, const VkLatencySleepModeInfoNV *) {
    return VK_SUCCESS;
}
VKAPI_ATTR void VKAPI_CALL SetMarker(VkDevice, VkSwapchainKHR,
                                     const VkSetLatencyMarkerInfoNV *info) {
    markers.push_back({info->presentID, info->marker});
}
VKAPI_ATTR void VKAPI_CALL GetTimings(VkDevice, VkSwapchainKHR, VkGetLatencyMarkerInfoNV *info) {
    info->timingCount = 0;
}
VKAPI_ATTR VkResult VKAPI_CALL Sleep(VkDevice, VkSwapchainKHR, const VkLatencySleepInfoNV *) {
    assert(published); // Current frame must be available to the consumer before
                       // pacing.
    assert(!markers.empty() && markers.back().kind == VK_LATENCY_MARKER_RENDERSUBMIT_END_NV);
    ++sleeps;
    return sleep_result;
}
VKAPI_ATTR VkResult VKAPI_CALL Wait(VkDevice, const VkSemaphoreWaitInfo *, uint64_t timeout) {
    assert(timeout == 100'000'000);
    ++waits;
    // These acquire the Reflex mutex: the wait must not block the present
    // thread's markers.
    Reflex::Get().OnPresentStart(presenting_id);
    Reflex::Get().OnPresentEnd(presenting_id);
    if (recreate_during_wait) {
        Reflex::Get().OnSwapchainDestroyed(swapchain);
        Reflex::Get().OnSwapchainCreated(swapchain);
    }
    return wait_result;
}
Reflex::Submission Submit() {
    published = false;
    presenting_id = Reflex::Get().OnFlip();
    assert(presenting_id);
    const auto before = sleeps;
    auto submission = Reflex::Get().OnSubmitted(presenting_id);
    assert(submission.id == presenting_id && sleeps == before);
    assert(submission.started != Vulkan::FrameHandoff::Time{});
    assert(!Reflex::Get().OnSubmitted(presenting_id).id); // Duplicate cannot mark/end again.
    published = true;
    return submission;
}
} // namespace

int main() {
#ifdef _WIN32
    _putenv_s("BB_FPS_LOG", "1");
    _putenv_s("BB_REFLEX_MEASURE", "1");
#else
    setenv("BB_FPS_LOG", "1", 1);
    setenv("BB_REFLEX_MEASURE", "1", 1);
#endif
    auto &dispatcher = VULKAN_HPP_DEFAULT_DISPATCHER;
    dispatcher.vkCreateSemaphore = CreateSemaphore;
    dispatcher.vkSetLatencySleepModeNV = SetMode;
    dispatcher.vkSetLatencyMarkerNV = SetMarker;
    dispatcher.vkGetLatencyTimingsNV = GetTimings;
    dispatcher.vkLatencySleepNV = Sleep;
    dispatcher.vkWaitSemaphores = Wait;
    auto &settings = BbSettings::Get();
    settings.frame_gen = BbSettings::FrameGenOff;
    settings.reflex = BbSettings::ReflexBoost;
    auto &reflex = Reflex::Get();
    reflex.Init(reinterpret_cast<VkDevice>(uintptr_t(1)), true);
    reflex.OnSwapchainCreated(swapchain);
    const auto first = Submit();
    reflex.OnFrameQueued(first.id);
    assert(sleeps == 1 && waits == 1);
    // Present end happens while waiting; the next work span begins only after
    // that wait.
    assert(markers[markers.size() - 4].kind == VK_LATENCY_MARKER_PRESENT_END_NV);
    assert(markers[markers.size() - 3].kind == VK_LATENCY_MARKER_SIMULATION_START_NV);
    assert(markers[markers.size() - 3].id != first.id);
    reflex.OnFrameQueued(first.id);
    reflex.OnFrameQueued(0);
    assert(sleeps == 1 && waits == 1);

    auto submission = Submit();
    reflex.OnSwapchainDestroyed(swapchain);
    reflex.OnSwapchainCreated(swapchain);
    reflex.OnFrameQueued(submission.id);
    assert(sleeps == 1); // Recreation invalidates an unpublished pacing ticket.

    submission = Submit();
    sleep_result = VK_ERROR_DEVICE_LOST;
    reflex.OnFrameQueued(submission.id);
    assert(sleeps == 2 && waits == 1); // Sleep failure cannot wait on an unsignalled semaphore.
    sleep_result = VK_SUCCESS;
    wait_result = VK_TIMEOUT;
    submission = Submit();
    reflex.OnFrameQueued(submission.id);
    assert(sleeps == 3 && waits == 2);
    assert(reflex.OnFlip() != submission.id); // Timeout remains bounded and advances work.

    wait_result = VK_SUCCESS;
    recreate_during_wait = true;
    submission = Submit();
    reflex.OnFrameQueued(submission.id);
    assert(markers.back().kind == VK_LATENCY_MARKER_PRESENT_END_NV);
    recreate_during_wait = false;
    const auto new_id = reflex.OnFlip();
    assert(new_id && new_id != submission.id);

    settings.reflex = BbSettings::ReflexOff;
    submission = Submit();
    const auto before = sleeps;
    reflex.OnFrameQueued(submission.id);
    assert(sleeps == before && reflex.OnFlip() != submission.id); // Measurement only.
    reflex.OnSwapchainDestroyed(swapchain);
    assert(!reflex.OnSubmitted(reflex.OnFlip()).id);
    std::puts("Reflex handoff tests passed");
}
