// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: object motion vectors for temporal upscaling (docs/history/ROADMAP_2026-09.ru.md, step 1).
//
// G-buffer shaders preserve clip positions for the exact indexed range of each draw.
// Matching includes vertex streams, index contents and base offsets. A missing match falls
// back to camera motion. See motion_history.h for CPU bookkeeping and its regression test.

#pragma once

#include <array>
#include "video_core/renderer_vulkan/motion_history.h"

#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"
#include "video_core/texture_cache/image.h"

namespace Vulkan {

class Instance;
class Scheduler;
struct RenderState;

class ObjectMotion {
public:
    ObjectMotion(const Instance& instance, Scheduler& scheduler);
    ~ObjectMotion();

    [[nodiscard]] bool Enabled() const noexcept {
        return enabled;
    }

    using DrawInfo = Motion::Draw;
    /// `priority`: a character, which may use the capacity kept back from the rest. `load`
    /// false: positions stored (for ray tracing), last frame's not read.
    u32 PrepareDraw(const DrawInfo& draw, bool priority = false, bool load = true);
    /// Draws that found no room since the start (capacity or parameter slots): they have no
    /// positions, so neither motion vectors of their own nor a place in ray tracing's scene.
    [[nodiscard]] u64 DroppedDraws() const noexcept {
        return dropped_draws;
    }
    struct CaptureReport {
        u64 parameter_drops{}, capacity_drops{}, reserve_drops{}, largest_rejected_vertices{};
        u32 peak_parameters{}, peak_vertices{}, vertex_capacity{}, reserved_vertices{};
        static constexpr u32 ParameterCapacity = 8192;
    };
    /// Render-thread report window, independent of optional/resettable history statistics.
    [[nodiscard]] CaptureReport TakeCaptureReport() noexcept {
        auto report = capture_report;
        report.vertex_capacity = positions_per_frame;
        report.reserved_vertices = history.Reserved();
        capture_report = {};
        return report;
    }
    /// bbport (ray tracing): the history allocation of the last PrepareDraw (store 0: none).
    [[nodiscard]] const Motion::History::Allocation& LastAllocation() const noexcept {
        return last_allocation;
    }
    /// Device address of the positions (vec4 clip positions, element `store + slot`).
    [[nodiscard]] u64 PositionsAddress() const noexcept;
    /// Elements in the positions buffer.
    [[nodiscard]] u32 PositionsElements() const noexcept {
        return 1 + 2 * positions_per_frame;
    }
    /// Vertices a frame the positions hold while ray tracing is on.
    [[nodiscard]] u32 RayTracingBudget() const noexcept {
        return rt_budget;
    }
    /// Small skeletons: whether the bone palette changed (Motion::History::Moving).
    bool Moving(const Motion::History::GateKey& key, u64 palette) {
        return history.Moving(key, palette);
    }
    /// Index range and topology hash of an indexed draw, reused across frames (verified
    /// again every `revalidate` frames).
    template <class Scan>
    Motion::IndexRangeCache::Result IndexRange(
        const Motion::IndexRangeCache::Key& key, Scan&& scan,
        u64 revalidate = Motion::IndexRangeCache::Revalidate) {
        return index_ranges.Get(key, frame, scan, revalidate);
    }

    /// Rendering of a motion pipeline: the motion attachment (render-target size).
    void Attach(RenderState& state, u32 width, u32 height);

    /// Start of a frame (display pass).
    void OnFrameStart();
    void InvalidateHistory() { history.NextFrame(); history.NextFrame(); }

    /// The motion image for the compose pass (layout General after this call) and whether it
    /// holds this frame's vectors at `width` x `height`.
    vk::ImageView PrepareRead(vk::CommandBuffer cmdbuf, u32 width, u32 height, bool& valid);
    /// The image of the last PrepareRead (layout General), or null.
    [[nodiscard]] vk::ImageView View() const noexcept {
        return read_target && read_target->view ? *read_target->view : vk::ImageView{};
    }
    [[nodiscard]] vk::Image Image(u32 width, u32 height) const noexcept {
        const Target* target = Find(width, height);
        return target && target->written ? vk::Image(target->image) : vk::Image{};
    }

private:
    /// bbport: a motion image per render-target size. Scenes with G-buffer passes at two sizes
    /// (a reduced proxy and the full target) shared one image: every switch recreated it after
    /// a full GPU wait (Scheduler::Finish), twice a frame — ~70% of the draw recording thread's
    /// time and an idle GPU — and threw this frame's vectors away.
    struct Target {
        VideoCore::UniqueImage image;
        vk::UniqueImageView view;
        u32 width = 0, height = 0;
        bool written = false; ///< this frame's vectors are in the image
        vk::ImageLayout layout = vk::ImageLayout::eUndefined;
        u64 used_frame = 0;
    };
    static constexpr u32 MaxTargets = 4;

    [[nodiscard]] const Target* Find(u32 width, u32 height) const noexcept {
        for (const auto& target : targets) {
            if (target.image && target.width == width && target.height == height) {
                return &target;
            }
        }
        return nullptr;
    }
    /// The image of this size, created when missing (replacing the one used longest ago; it is
    /// destroyed once the GPU is done with it, without waiting).
    Target& GetTarget(u32 width, u32 height);

    const Instance& instance;
    Scheduler& scheduler;
    bool enabled = false;

    // Parameter ring (host visible): FrameSlots frames of ParamsPerFrame entries (two u32x4),
    // element 0 all zero (motion off); after them the header, the positions' address
    // (Shader::MotionVectors::positions_header).
    static constexpr u32 FrameSlots = 4;
    static constexpr u32 ParamsPerFrame = CaptureReport::ParameterCapacity;
    static constexpr u64 HeaderOffset = u64(1 + FrameSlots * ParamsPerFrame) * 32;
    // Positions (device local): two halves (current/previous frame) of vec4; element 0 is reserved.
    // A half holds 4M vertices. With ray tracing every G-buffer draw is stored (most areas need
    // more than 4M): 12M where it can run, allocated while it is wanted and released once it
    // released its structures (256 MiB more), 15% of it kept for characters (its static world
    // would crowd them out), even when the sizes match. BB_MOTION_BUDGET sets both;
    // BB_RT_CAPTURE_BUDGET overrides RT only (1..64 Mi-vertices, at least the base).
    static u32 BaseBudget();
    static u32 ChooseRtBudget(const Instance& instance);
    /// Positions for `per_frame` vertices a frame, replacing the current ones once the GPU is
    /// idle; the history starts over. False (the old ones kept) without the memory.
    bool CreatePositions(u32 per_frame);
    u32 base_budget = BaseBudget();
    u32 rt_budget = ChooseRtBudget(instance);
    u32 positions_per_frame = 0;
    bool rt_budget_failed = false; ///< no memory for ray tracing's size: not tried again
    Motion::History history{0};
    u64 dropped_draws = 0;
    CaptureReport capture_report{};
    Motion::IndexRangeCache index_ranges;
    std::array<u64, FrameSlots> params_ticks{};
    vk::Buffer params_buffer{};
    VmaAllocation params_allocation{};
    u32* params_mapped{};
    vk::Buffer positions_buffer{};
    VmaAllocation positions_allocation{};
    u64 positions_address = 0;

    u64 frame = 0;
    u32 params_used = 0;
    Motion::History::Allocation last_allocation{};
    std::array<Target, MaxTargets> targets;
    const Target* read_target = nullptr; ///< of the last PrepareRead
};

} // namespace Vulkan
