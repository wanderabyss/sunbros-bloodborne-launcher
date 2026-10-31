// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <array>
#include <atomic>
#include <chrono>
#include <deque>
#include <memory>

#include <condition_variable>

#include "core/libraries/videoout/buffer.h"
#include "video_core/renderer_vulkan/host_passes/fsr_pass.h"
#include "video_core/renderer_vulkan/frame_handoff.h"
#include "video_core/renderer_vulkan/frame_recreate.h"
#include "video_core/renderer_vulkan/host_passes/pp_pass.h"
#include "video_core/renderer_vulkan/presentation_telemetry.h"
#include "video_core/renderer_vulkan/vk_frame_generation.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_runtime.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/renderer_vulkan/vk_swapchain.h"
#include "video_core/texture_cache/texture_cache.h"

namespace Frontend {
class WindowSDL;
}

namespace AmdGpu {
struct Liverpool;
}

namespace Vulkan {

struct Frame {
    u32 width;
    u32 height;
    VmaAllocation allocation;
    vk::Image image;
    vk::ImageView image_view;
    vk::Fence present_done;
    vk::Semaphore ready_semaphore;
    u64 ready_tick;
    u8 id{};
    /// bbport: Reflex frame id (vk_reflex.h; 0 while Reflex is off, and for blank frames).
    u64 reflex_id{};
    FrameHandoff handoff{};

    /// bbport: frame generation: frames between the previous game frame and this one,
    /// presented before it (FrameGenerator), the first `generated_count` of them.
    struct Generated {
        VmaAllocation allocation{};
        vk::Image image{};
        vk::ImageView view{};
    };
    std::array<Generated, FrameGenerator::MaxGenerated> generated{};
    u32 generated_count{};
    /// bbport: GetRenderFrame could not resize it (frame_recreate.h): it has the old size.
    bool kept_old_size{};
};

enum SchedulerType {
    Draw,
    Present,
    CpuFlip,
};

class Rasterizer;

class Presenter {
public:
    Presenter(Frontend::WindowSDL& window, AmdGpu::Liverpool* liverpool);
    ~Presenter();

    HostPasses::PostProcessingPass::Settings& GetPPSettingsRef() {
        return pp_settings;
    }

    HostPasses::FsrPass::Settings& GetFsrSettingsRef() {
        return fsr_settings;
    }

    Frontend::WindowSDL& GetWindow() const {
        return window;
    }

    Rasterizer& GetRasterizer() const {
        return *rasterizer.get();
    }

    bool IsHDRSupported() const {
        return swapchain.HasHDR();
    }

    void SetHDR(bool enable) {
        if (!IsHDRSupported()) {
            return;
        }
        swapchain.SetHDR(enable);
    }

    VideoCore::Image& RegisterVideoOutSurface(
        const Libraries::VideoOut::BufferAttributeGroup& attribute, VAddr cpu_address) {
        vo_buffers_addr.emplace_back(cpu_address);
        auto desc = VideoCore::TextureCache::ImageDesc{attribute, cpu_address};
        const auto image_id = texture_cache.FindImage(desc);
        auto& image = texture_cache.GetImage(image_id);
        image.usage.vo_surface = 1u;
        return image;
    }

    bool IsVideoOutSurface(const AmdGpu::ColorBuffer& color_buffer) const;

    Frame* PrepareFrame(const Libraries::VideoOut::BufferAttributeGroup& attribute,
                        VAddr cpu_address);

    Frame* PrepareBlankFrame(bool present_thread);

    void Present(Frame* frame, bool is_reusing_frame = false, bool is_game_frame = true);
    Frame* PrepareLastFrame();
    /// bbport: VideoOut queued a game frame's Present (it runs on the swap thread): while one
    /// waits, the frame before it shows no more generated frames.
    void NoteFlipQueued() {
        queued_flips.fetch_add(1, std::memory_order_relaxed);
    }

private:
    /// `present_thread`: called on the present thread (PrepareBlankFrame(true)), whose
    /// scheduler and RecreateFrame policy it uses; otherwise the render thread's.
    Frame* GetRenderFrame(bool present_thread);

    /// False when the image could not be made (or the size is 0x0): the frame keeps its
    /// previous one (and size). `optional`: the caller goes on without the image (no retries
    /// before giving up). `policy`: the caller's failure count and back-off, used by its thread
    /// only; `owner`: the scheduler of that thread, whose submitted work is waited for before
    /// the one retry (never the whole device: the other thread may be submitting).
    /// See frame_recreate.h.
    bool RecreateFrame(Frame* frame, u32 width, u32 height, FrameRecreatePolicy& policy,
                       Scheduler& owner, vk::Format format = FrameGenerator::ColorFormat,
                       bool optional = false);
    /// bbport: the first `count` images frame generation writes for `frame` (its size), made
    /// when missing; the others are freed. Returns how many there are.
    u32 EnsureGenerated(Frame* frame, u32 count);
    void DestroyGenerated(Frame* frame, u32 from = 0);
    /// bbport: frame generation is off: its memory is freed.
    void ReleaseFrameGen(Frame* frame);
    /// bbport: present thread, after a game frame: how many generated frames the display can
    /// show per game frame (frame_gen_limit). `present_ms`: the time Present took, `paced_ms`
    /// of it the sleep that spaces its images.
    void UpdateFrameGenLimit(bool wanted, double present_ms, double paced_ms);
    void ReportFrameGeneration(); // bounded periodic output, including failed/skipped presents
    /// bbport: blits `image` (General layout) into a swapchain image with the overlay and
    /// presents it. `last`: the game frame itself, which also signals the frame's fence.
    /// False when the swapchain could not give an image.
    /// `reflex_id`: the Reflex frame id of the game's own image (0: none, also when shown again).
    bool PresentImage(Frame* frame, vk::Image image, bool last, u64 reflex_id = 0);

    void SetExpectedGameSize(s32 width, s32 height);

private:
    float expected_ratio{1920.0 / 1080.0f};
    u32 expected_frame_width{1920};
    u32 expected_frame_height{1080};

    Frontend::WindowSDL& window;
    Instance instance;
    HostPasses::FsrPass fsr_pass;
    HostPasses::FsrPass::Settings fsr_settings{};
    /// Render thread: the last present upscale logged.
    struct PresentUpscale {
        u32 source_width{}, source_height{}, frame_width{}, frame_height{};
        bool easu{};
        float rcas_stops{}; ///< 0 without RCAS
        bool operator==(const PresentUpscale&) const = default;
    } last_present_upscale{};
    HostPasses::PostProcessingPass::Settings pp_settings{};
    HostPasses::PostProcessingPass pp_pass;
    // Presentation-thread pipelines: SDR (desktop HDR compensation) and HDR10. Frame
    // generation always sees SDR; output encoding is applied once after UI composition.
    HostPasses::PostProcessingPass sdr_present_pass;
    HostPasses::PostProcessingPass hdr_present_pass;
    Frame color_conversion_frame{};
    int last_output_color_mode{-1}; // presentation thread: log SDR/desktop-compensated/HDR changes
    AmdGpu::Liverpool* liverpool;
    Scheduler draw_scheduler;
    std::deque<u64> recent_frame_ticks; ///< bbport: BB_FRAMES_AHEAD bound (PrepareFrame)
    Scheduler present_scheduler;
    Scheduler flip_scheduler;
    Swapchain swapchain;
    Runtime runtime;
    std::unique_ptr<Rasterizer> rasterizer;
    VideoCore::TextureCache& texture_cache;
    vk::UniqueCommandPool command_pool;
    std::vector<Frame> present_frames;
    std::queue<Frame*> free_queue;
    Frame* last_submit_frame;
    std::mutex free_mutex;
    std::condition_variable free_cv;
    std::condition_variable_any frame_cv;
    std::vector<VAddr> vo_buffers_addr;
    /// bbport: frame generation, and the interval of the game's frames its frames are paced
    /// in (present thread).
    std::unique_ptr<FrameGenerator> frame_generator;
    /// The game's picture before its UI, through the same passes as the frame.
    Frame hudless_frame{};
    /// bbport: failed presentation image allocations in a row and their back-off
    /// (RecreateFrame), one per image kind and thread: the render thread's game frames and
    /// HUD-free copy, the present thread's blank frames and HDR scratch.
    FrameRecreatePolicy frame_recreate_policy{};
    FrameRecreatePolicy hudless_recreate_policy{};
    FrameRecreatePolicy blank_recreate_policy{};
    FrameRecreatePolicy scratch_recreate_policy{};
    /// bbport: game frames presented (BB_TEST_FRAME_ALLOC_FAILS=N@M counts them).
    std::atomic<u64> presented_game_frames{0};
    /// bbport: render thread: frame generation is skipped for a frame that kept its old size.
    bool fg_skipped_old_size{};
    std::chrono::steady_clock::time_point last_game_present{};
    std::atomic<double> game_frame_ms{16.7}; ///< written by the present thread
    /// DLSS 5's guard (Dlss5Guard): game frames over 60 FPS's interval lately, 0..120.
    u32 dlss5_slow_frames = 0;
    u32 dlss5_frames = 0; ///< game frames with it on, up to 300 ("DLSS 5: running")
    void Dlss5Guard();
    /// Generated frames per game frame the display can show (UpdateFrameGenLimit).
    std::atomic<u32> frame_gen_limit{0};
    // Present thread: the share of the frame interval spent presenting (without the pacing
    // sleep), the generated frames allowed while presenting falls behind and until when, and
    // whether the swapchain was made for frame generation.
    double present_busy{};
    u32 frame_gen_backlog_cap{FrameGenerator::MaxGenerated};
    std::chrono::steady_clock::time_point frame_gen_backlog_until{};
    bool swapchain_frame_gen{};
    PresentationTelemetry presentation_telemetry;
    FrameHandoffTimings handoff_timings; // present thread, BB_FPS_LOG only
    PresentationTelemetry::Counters presentation_counts{}; // present thread only
    /// Game frames VideoOut queued for the swap thread and not yet presented (NoteFlipQueued).
    std::atomic<u32> queued_flips{0};
    // Present thread: the game frames of the current second, and the seconds with room for
    // one more generated frame.
    std::chrono::steady_clock::time_point limit_window{};
    u32 limit_frames{};
    u32 limit_up_seconds{};
    /// Display refreshes per game frame in the last whole second (no measurement yet: room).
    double display_ratio{FrameGenerator::MaxGenerated + 1.0};
    /// BB_FPS_LOG=1, present thread: its time per part since the last pacing line, in ms
    /// (acquire, recording with the overlay, submit, waiting for the submit lock to present,
    /// present, pacing sleep).
    struct SwapTiming {
        double acquire{}, record{}, submit{}, lock{}, present{}, sleep{};
    } swap_timing;
};

} // namespace Vulkan
