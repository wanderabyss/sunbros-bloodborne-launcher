#include <cassert>
#include <chrono>
#include <cstdio>
#include <future>
#include <thread>

#include "gpu/shadps4/video_core/renderer_vulkan/frame_admission.h"

using Vulkan::FrameAdmission;
using namespace std::chrono_literals;

int main() {
    FrameAdmission admission;
    const auto now = FrameAdmission::Clock::now();
    const auto first = admission.Publish();
    assert(first == 1);
    assert(admission.Wait(first, false, 0ms) == FrameAdmission::Result::Bypassed);
    assert(admission.Wait(first, true, 0ms) == FrameAdmission::Result::Timeout);
    // Duplicate, stale and out-of-order acknowledgements cannot admit a new frame.
    admission.Consume(0);
    admission.Consume(2);
    assert(admission.Wait(first, true, 0ms) == FrameAdmission::Result::Timeout);
    admission.Consume(first);
    assert(admission.Wait(first, true, 0ms) == FrameAdmission::Result::Consumed);
    const auto second = admission.Publish();
    admission.Consume(first);
    assert(admission.Wait(second, true, 0ms) == FrameAdmission::Result::Timeout);
    admission.Consume(second);
    assert(admission.Wait(second, true, 0ms) == FrameAdmission::Result::Consumed);
    assert(!admission.Poll(now + 1s));
    const auto report = admission.Poll(now + 6s);
    assert(report && report->published == 2 && report->consumed == 2 && report->pending == 0);
    assert(report->peak_pending == 1 && report->gated == 5 && report->bypassed == 1);
    assert(report->timeouts == 3 && report->blocked == 3);
    assert(!admission.Poll(now + 7s));
    const auto reset = admission.Poll(now + 12s);
    assert(reset && reset->gated == 0 && reset->timeouts == 0 && reset->peak_pending == 0);

    // Real condition-variable wait: the current frame is published/visible while the
    // command thread waits. Dequeue releases it without any generated-image completion.
    FrameAdmission pipeline;
    std::promise<uint64_t> published;
    std::promise<void> next_work;
    auto ticket = published.get_future();
    auto started = next_work.get_future();
    std::jthread producer([&] {
        const auto id = pipeline.Publish();
        published.set_value(id);
        assert(pipeline.Wait(id, true, 2s) == FrameAdmission::Result::Consumed);
        next_work.set_value();
    });
    const auto id = ticket.get();
    assert(started.wait_for(20ms) == std::future_status::timeout);
    pipeline.Consume(id);
    assert(started.wait_for(1s) == std::future_status::ready);
    producer.join();

    // Teardown can release a blocked producer even if VideoOut never consumes its ticket.
    FrameAdmission stopping;
    const auto pending = stopping.Publish();
    std::promise<FrameAdmission::Result> stopped;
    auto outcome = stopped.get_future();
    std::jthread waiter([&] { stopped.set_value(stopping.Wait(pending, true, 2s)); });
    stopping.Stop();
    assert(outcome.wait_for(1s) == std::future_status::ready);
    assert(outcome.get() == FrameAdmission::Result::Stopped);
    waiter.join();
    std::puts("frame admission tests passed");
}
