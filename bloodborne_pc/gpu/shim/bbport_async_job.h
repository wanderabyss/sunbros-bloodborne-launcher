// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <chrono>
#include <future>
#include <optional>
#include <utility>

// Owner-thread API. One isolated CPU job; polling never waits for completion.
// Destruction joins the outstanding job, so workers cannot outlive their owner.
template<class T> class BbAsyncJob {
public:
    bool Busy() const { return result.valid(); }
    template<class F> bool Start(F&& work) {
        if (Busy()) return false;
        result = std::async(std::launch::async, std::forward<F>(work));
        return true;
    }
    std::optional<T> Poll() {
        if (!Busy() || result.wait_for(std::chrono::seconds(0)) != std::future_status::ready)
            return std::nullopt;
        return result.get();
    }
private:
    std::future<T> result;
};
