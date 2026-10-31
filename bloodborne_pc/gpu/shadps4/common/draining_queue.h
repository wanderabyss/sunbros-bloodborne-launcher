// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <condition_variable>
#include <functional>
#include <future>
#include <mutex>
#include <queue>
#include <thread>

namespace Common {
// One writer, FIFO tasks. Stop rejects new work and drains every accepted task.
class DrainingQueue {
public:
    explicit DrainingQueue(std::function<void()> init = {}) : worker{[this, init] {
        if (init) init();
        for (;;) {
            std::packaged_task<void()> task;
            {
                std::unique_lock lock{mutex};
                ready.wait(lock, [this] { return stopping || !tasks.empty(); });
                if (tasks.empty()) return;
                task = std::move(tasks.front()); tasks.pop();
            }
            task(); // packaged_task captures failures; later writes still drain
        }
    }} {}
    ~DrainingQueue() { Stop(); }
    bool Push(std::packaged_task<void()> task) {
        {
            std::scoped_lock lock{mutex};
            if (stopping) return false;
            tasks.push(std::move(task));
        }
        ready.notify_one();
        return true;
    }
    void Stop() {
        { std::scoped_lock lock{mutex}; stopping = true; }
        ready.notify_one();
        if (worker.joinable()) worker.join();
    }
private:
    std::mutex mutex;
    std::condition_variable ready;
    std::queue<std::packaged_task<void()>> tasks;
    bool stopping{};
    std::thread worker;
};
} // namespace Common
