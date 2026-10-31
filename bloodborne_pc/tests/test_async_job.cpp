// SPDX-License-Identifier: GPL-2.0-or-later
#include "gpu/shim/bbport_async_job.h"
#include <cassert>
#include <cstdio>
#include <stdexcept>
#include <thread>

int main() {
    BbAsyncJob<int> job;
    assert(!job.Busy() && !job.Poll());
    std::promise<void> entered, release;
    auto gate = release.get_future();
    assert(job.Start([&] { entered.set_value(); gate.wait(); return 42; }));
    entered.get_future().wait();
    // Poll must return while the worker is blocked; Start must not replace a
    // live future (whose destruction would join and stall the caller).
    assert(job.Busy() && !job.Poll());
    assert(!job.Start([] { return 99; }));
    release.set_value();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    std::optional<int> value;
    while (!(value = job.Poll()) && std::chrono::steady_clock::now() < deadline)
        std::this_thread::yield();
    assert(value && *value == 42 && !job.Busy());
    assert(job.Start([]() -> int { throw std::runtime_error("load failed"); }));
    bool failed = false;
    while (!failed && std::chrono::steady_clock::now() < deadline) {
        try { job.Poll(); } catch (const std::runtime_error&) { failed = true; }
        std::this_thread::yield();
    }
    assert(failed && !job.Busy());
    assert(job.Start([] { return 7; }));
    while (!(value = job.Poll()) && std::chrono::steady_clock::now() < deadline)
        std::this_thread::yield();
    assert(value && *value == 7);
    std::puts("Async job: PASS (nonblocking poll, single worker, exception/reuse)");
}
