// SPDX-License-Identifier: GPL-2.0-or-later

#include <algorithm>
#include <cstdlib>

#include "video_core/renderer_vulkan/vk_gpu_profiler.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"

namespace Vulkan {

void GpuProfiler::Init(const Instance& instance, Scheduler& scheduler) {
    const char* env = std::getenv("BB_GPU_PROFILE");
    if (!env || env[0] != '1' || instance_ptr) {
        return;
    }
    instance_ptr = new GpuProfiler(instance, scheduler);
}

GpuProfiler::GpuProfiler(const Instance& instance, Scheduler& scheduler_)
    : device{instance.GetDevice()}, scheduler{scheduler_} {
    const vk::QueryPoolCreateInfo info = {
        .queryType = vk::QueryType::eTimestamp,
        .queryCount = NumSlices * SliceQueries,
    };
    pool = Check<"create timestamp query pool">(device.createQueryPoolUnique(info));
    device.resetQueryPool(*pool, 0, NumSlices * SliceQueries);
    period_ns = instance.GetPhysicalDevice().getProperties().limits.timestampPeriod;
    for (auto& k : keys) {
        k.reserve(SliceQueries);
    }
    std::printf("GPU profile: on (timestamp period %.2f ns)\n", period_ns);
}

void GpuProfiler::WriteTimestamp(u64 key) {
    if (used[slice] + 1 >= SliceQueries) {
        return; // the frame's slice is full: the rest of the frame goes to the last label
    }
    // Outside render passes: radv_CmdWriteTimestamp2 crashed inside some. Marks sit where a
    // pass, dispatch or submission ends anyway.
    scheduler.EndRendering();
    const u32 query = slice * SliceQueries + used[slice]++;
    keys[slice].push_back(key);
    current = key;
    scheduler.Record([pool = *pool, query](vk::CommandBuffer cmdbuf) {
        cmdbuf.writeTimestamp2(vk::PipelineStageFlagBits2::eAllCommands, pool, query);
    });
}

void GpuProfiler::BeginFrame() {
    // Close the frame: one more timestamp without a label.
    if (used[slice] > 0 && used[slice] < SliceQueries) {
        scheduler.EndRendering();
        const u32 query = slice * SliceQueries + used[slice]++;
        scheduler.Record([pool = *pool, query](vk::CommandBuffer cmdbuf) {
            cmdbuf.writeTimestamp2(vk::PipelineStageFlagBits2::eAllCommands, pool, query);
        });
        pending[slice] = true;
    }
    slice = (slice + 1) % NumSlices;
    // The oldest slice: its frame was submitted four frames ago.
    if (pending[slice]) {
        Collect(slice);
    }
    if (used[slice]) {
        device.resetQueryPool(*pool, slice * SliceQueries, used[slice]);
    }
    used[slice] = 0;
    keys[slice].clear();
    pending[slice] = false;
    Print();
}

void GpuProfiler::Collect(u32 which) {
    const u32 count = used[which];
    std::vector<u64> stamps(count);
    // Four frames on this is complete unless the GPU lags that far: then wait for it.
    const auto result = device.getQueryPoolResults(
        *pool, which * SliceQueries, count, count * sizeof(u64), stamps.data(), sizeof(u64),
        vk::QueryResultFlagBits::e64 | vk::QueryResultFlagBits::eWait);
    if (result != vk::Result::eSuccess) {
        return;
    }
    double frame_ms = 0;
    frame_segments.clear();
    for (u32 i = 0; i + 1 < count; ++i) {
        const double ms = double(stamps[i + 1] - stamps[i]) * period_ns / 1e6;
        auto& total = totals[keys[which][i]];
        total.ms += ms;
        ++total.segments;
        frame_ms += ms;
        frame_segments.emplace_back(ms, keys[which][i]);
    }
    ++frames;
    ++frame_number;
    // BB_GPU_PROFILE_SLOW_MS (40 by default): a frame that long is printed at once with its
    // largest segments ("between submissions" is the GPU waiting for the CPU).
    static const double slow_ms = [] {
        const char* value = std::getenv("BB_GPU_PROFILE_SLOW_MS");
        const double ms = value ? std::atof(value) : 0.0;
        return ms > 0.0 ? ms : 40.0;
    }();
    if (frame_ms < slow_ms) {
        return;
    }
    const size_t shown = std::min<size_t>(frame_segments.size(), 5);
    std::ranges::partial_sort(frame_segments, frame_segments.begin() + shown,
                              [](const auto& a, const auto& b) { return a.first > b.first; });
    std::printf("GPU profile: slow frame %llu, %.1f ms:", static_cast<unsigned long long>(frame_number),
                frame_ms);
    for (size_t i = 0; i < shown; ++i) {
        std::printf("%s %.2f ms %s", i ? ";" : "", frame_segments[i].first,
                    described[frame_segments[i].second].c_str());
    }
    std::printf("\n");
}

void GpuProfiler::Print() {
    const auto now = std::chrono::steady_clock::now();
    // BB_GPU_PROFILE_SECONDS: a shorter window for scripted tests (5 s by default).
    static const auto window_length = [] {
        const char* value = std::getenv("BB_GPU_PROFILE_SECONDS");
        const int seconds = value ? std::atoi(value) : 0;
        return std::chrono::seconds(seconds >= 1 ? seconds : 5);
    }();
    if (now - window < window_length || frames == 0) {
        return;
    }
    window = now;
    std::vector<std::pair<u64, Total>> sorted(totals.begin(), totals.end());
    std::ranges::sort(sorted, [](const auto& a, const auto& b) { return a.second.ms > b.second.ms; });
    double sum = 0;
    for (const auto& [key, total] : sorted) {
        sum += total.ms;
    }
    std::printf("GPU profile: %.2f ms/frame over %llu frames, %zu labels\n", sum / frames,
                static_cast<unsigned long long>(frames), sorted.size());
    for (size_t i = 0; i < std::min<size_t>(sorted.size(), 40); ++i) {
        const auto& [key, total] = sorted[i];
        std::printf("  %6.3f ms/frame %5.1f/frame  %s\n", total.ms / frames,
                    double(total.segments) / frames, described[key].c_str());
    }
    // Groups over all their labels, also those past the 40 printed.
    std::array<Total, size_t(Group::Count)> group_totals{};
    for (const auto& [key, total] : sorted) {
        if (const auto it = groups.find(key); it != groups.end()) {
            group_totals[size_t(it->second)].ms += total.ms;
            group_totals[size_t(it->second)].segments += total.segments;
        }
    }
    static constexpr std::array<const char*, size_t(Group::Count)> group_names{"", "G-buffer passes"};
    for (size_t g = 1; g < group_totals.size(); ++g) {
        if (group_totals[g].segments) {
            std::printf("  %6.3f ms/frame %5.1f/frame  group: %s\n", group_totals[g].ms / frames,
                        double(group_totals[g].segments) / frames, group_names[g]);
        }
    }
    totals.clear();
    frames = 0;
}

} // namespace Vulkan
