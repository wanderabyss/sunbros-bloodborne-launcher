// SPDX-License-Identifier: GPL-2.0-or-later
// BB_FRAME_TIMES=<file> (benchmarks): one line per event, so a
// script can take 1% and 0.1% lows from single frames, which the five-second "Frame pacing" lines
// cannot give. Lines: "g <ms>" a game flip and the time since the one before (driver.cpp), "p <ms>"
// an accepted present, generated frames included (vk_presenter.cpp), "m <text>" a test mark
// (vk_ray_tracing.cpp). Off (one getenv) without the variable.
#pragma once

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <mutex>

namespace BbFrameTimes {

inline std::FILE* File() {
    static std::FILE* file = [] {
        const char* path = std::getenv("BB_FRAME_TIMES");
        return path && *path ? std::fopen(path, "w") : nullptr;
    }();
    return file;
}

inline void Line(char kind, const char* text) {
    std::FILE* file = File();
    if (!file) {
        return;
    }
    static std::mutex mutex;
    static unsigned lines;
    std::scoped_lock lock{mutex};
    std::fprintf(file, "%c %s\n", kind, text);
    // Benchmarks end the game from outside: flush often enough that little is lost.
    if (kind == 'm' || ++lines % 120 == 0) {
        std::fflush(file);
    }
}

/// The time since the previous call with the same `last`, as "<kind> <ms>".
inline void Interval(char kind, std::chrono::steady_clock::time_point& last) {
    if (!File()) {
        return;
    }
    const auto now = std::chrono::steady_clock::now();
    if (last.time_since_epoch().count() != 0) {
        char text[32];
        std::snprintf(text, sizeof(text), "%.3f",
                      std::chrono::duration<double, std::milli>(now - last).count());
        Line(kind, text);
    }
    last = now;
}

} // namespace BbFrameTimes
