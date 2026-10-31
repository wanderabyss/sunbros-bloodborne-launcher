// SPDX-FileCopyrightText: Copyright 2024-2026 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "common/debug.h"
#include "common/elf_info.h"
#include "common/io_file.h"
#include "common/path_util.h"
#include "common/singleton.h"
#include "common/thread.h"
#include "core/debug_state.h"
#include "core/emulator_settings.h"
#include "sdl_window.h"
#include "video_core/buffer_cache/buffer.h"
#include "video_core/renderdoc.h"
#include "video_core/renderer_vulkan/vk_platform.h"
#include "video_core/renderer_vulkan/present_target.h"
#include "bbport_frame_times.h"
#include "bbport_overlay.h"
#include "bbport_settings.h"
#include "video_core/renderer_vulkan/vk_temporal_upscaler.h"
#include "video_core/renderer_vulkan/vk_dlss.h"
#include "video_core/renderer_vulkan/vk_gpu_profiler.h"
#include "video_core/renderer_vulkan/vk_presenter.h"
#include "video_core/renderer_vulkan/vk_rasterizer.h"
#include "video_core/renderer_vulkan/vk_reflex.h"
#include "video_core/texture_cache/image.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cctype>
#include <chrono>
#include <cmath>
#include <csetjmp>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <memory>
#include <span>
#include <sstream>
#include <system_error>
#include <thread>
#include <vector>
#include <vk_mem_alloc.h>
#ifdef MemoryBarrier
#undef MemoryBarrier // bbport: winnt.h macro (through fmt), clashes with vk::MemoryBarrier
#endif

void BbNotePresentedFrame(int width, int height); // bbport: window.cpp (the menu pointer)

namespace Vulkan {

bool CanBlitToSwapchain(const vk::PhysicalDevice physical_device, vk::Format format) {
    const vk::FormatProperties props{physical_device.getFormatProperties(format)};
    return static_cast<bool>(props.optimalTilingFeatures & vk::FormatFeatureFlagBits::eBlitDst);
}

[[nodiscard]] vk::ImageSubresourceLayers MakeImageSubresourceLayers() {
    return vk::ImageSubresourceLayers{
        .aspectMask = vk::ImageAspectFlagBits::eColor,
        .mipLevel = 0,
        .baseArrayLayer = 0,
        .layerCount = 1,
    };
}

[[nodiscard]] vk::ImageBlit MakeImageBlit(s32 frame_width, s32 frame_height, s32 dst_width,
                                          s32 dst_height, s32 offset_x, s32 offset_y) {
    return vk::ImageBlit{
        .srcSubresource = MakeImageSubresourceLayers(),
        .srcOffsets =
            std::array{
                vk::Offset3D{
                    .x = 0,
                    .y = 0,
                    .z = 0,
                },
                vk::Offset3D{
                    .x = frame_width,
                    .y = frame_height,
                    .z = 1,
                },
            },
        .dstSubresource = MakeImageSubresourceLayers(),
        .dstOffsets =
            std::array{
                vk::Offset3D{
                    .x = offset_x,
                    .y = offset_y,
                    .z = 0,
                },
                vk::Offset3D{
                    .x = offset_x + dst_width,
                    .y = offset_y + dst_height,
                    .z = 1,
                },
            },
    };
}

[[nodiscard]] vk::ImageBlit MakeImageBlitStretch(s32 frame_width, s32 frame_height,
                                                 s32 swapchain_width, s32 swapchain_height) {
    return MakeImageBlit(frame_width, frame_height, swapchain_width, swapchain_height, 0, 0);
}

// bbport: BB_FPS_LOG=1: frame generation's pacing and the swap thread's time, every 5 seconds.
static bool FpsLog() {
    static const bool on = [] {
        const char* env = std::getenv("BB_FPS_LOG");
        return env && env[0] == '1';
    }();
    return on;
}

static vk::Rect2D FitImage(s32 frame_width, s32 frame_height, s32 swapchain_width,
                           s32 swapchain_height) {
    float frame_aspect = static_cast<float>(frame_width) / frame_height;
    float swapchain_aspect = static_cast<float>(swapchain_width) / swapchain_height;

    u32 dst_width = swapchain_width;
    u32 dst_height = swapchain_height;

    if (frame_aspect > swapchain_aspect) {
        dst_height = static_cast<s32>(swapchain_width / frame_aspect);
    } else {
        dst_width = static_cast<s32>(swapchain_height * frame_aspect);
    }

    const s32 offset_x = (swapchain_width - dst_width) / 2;
    const s32 offset_y = (swapchain_height - dst_height) / 2;

    return vk::Rect2D{{offset_x, offset_y}, {dst_width, dst_height}};
}

[[nodiscard]] vk::ImageBlit MakeImageBlitFit(s32 frame_width, s32 frame_height, s32 swapchain_width,
                                             s32 swapchain_height) {
    ::BbNotePresentedFrame(frame_width, frame_height);
    const auto& dst_rect = FitImage(frame_width, frame_height, swapchain_width, swapchain_height);

    return MakeImageBlit(frame_width, frame_height, dst_rect.extent.width, dst_rect.extent.height,
                         dst_rect.offset.x, dst_rect.offset.y);
}

// bbport: screenshot capture and ImGui overlays removed; the port presents directly.

Presenter::Presenter(Frontend::WindowSDL& window_, AmdGpu::Liverpool* liverpool_)
    : window{window_}, liverpool{liverpool_},
      instance{window, EmulatorSettings.GetGpuId(), EmulatorSettings.IsVkValidationEnabled(),
               EmulatorSettings.IsVkCrashDiagnosticEnabled()},
      draw_scheduler{instance, true}, present_scheduler{instance}, flip_scheduler{instance},
      swapchain{instance, window}, runtime{instance, draw_scheduler},
      rasterizer{std::make_unique<Rasterizer>(instance, draw_scheduler, runtime, liverpool)},
      texture_cache{rasterizer->GetTextureCache()} {
    const u32 num_images = swapchain.GetImageCount();
    const vk::Device device = instance.GetDevice();
    // bbport: the present thread's submissions (blits, overlay) read no guest memory: they do
    // not run or wait for the render thread's guest copies under the submit lock.
    present_scheduler.SkipGuestCopyWaits();

    // Create presentation frames.
    present_frames.resize(num_images);
    for (u32 i = 0; i < num_images; i++) {
        Frame& frame = present_frames[i];
        frame.id = i;
        auto fence = Check<"create present done fence">(
            device.createFence({.flags = vk::FenceCreateFlagBits::eSignaled}));
        frame.present_done = fence;
        free_queue.push(&frame);
    }

    // bbport: FSR 1 (EASU + RCAS) scales an output-resolution picture smaller than the display
    // to the frame's size; PrepareFrame sets these per frame from present_upscale/present_rcas.
    fsr_settings.enable = false;
    // Two passes a frame (the picture and the UI-free copy for frame generation).
    fsr_pass.Create(device, instance.GetAllocator(), num_images * 2);
    // Frames and FG inputs stay SDR RGBA8. Output color encoding happens on the present
    // queue, directly into the swapchain's SDR or 10-bit HDR attachment.
    pp_pass.Create(device, FrameGenerator::ColorFormat);
    sdr_present_pass.Create(device, swapchain.GetSurfaceFormat().format);
    if (swapchain.HasHDR()) {
        hdr_present_pass.Create(device, Swapchain::HdrFormat);
    }
    // bbport: the overlay draws over every presented image, generated ones included: its
    // vertex buffers must not be reused while one of them is still drawn. Sized for the image
    // the swapchain gets when frame generation is switched on later.
    BbOverlay::Init(instance, swapchain.GetSurfaceFormat().format,
                    (num_images + 1) * (FrameGenerator::MaxGenerated + 1));

    frame_generator = std::make_unique<FrameGenerator>(instance, draw_scheduler);
    swapchain_frame_gen = frame_generator->Wanted();
    rasterizer->GetUpscaler().SetFrameGenerator(frame_generator.get());
}

Presenter::~Presenter() {
    rasterizer->GetUpscaler().SetFrameGenerator(nullptr);

    draw_scheduler.Finish();
    present_scheduler.Finish();
    flip_scheduler.Finish();
    Check(draw_scheduler.CommandBuffer().reset());
    Check(present_scheduler.CommandBuffer().reset());
    Check(flip_scheduler.CommandBuffer().reset());
    // bbport: NGX is released while the device lives (the atexit release ran after it):
    // frame generation's features first, then DLSS. The upscaler holds no NGX object itself.
    frame_generator.reset();
    if (Dlss* dlss = Dlss::Get()) {
        dlss->Shutdown();
    }

    const vk::Device device = instance.GetDevice();
    for (auto& frame : present_frames) {
        DestroyGenerated(&frame);
        vmaDestroyImage(instance.GetAllocator(), frame.image, frame.allocation);
        device.destroyImageView(frame.image_view);
        device.destroyFence(frame.present_done);
    }
    if (hudless_frame.image) {
        vmaDestroyImage(instance.GetAllocator(), hudless_frame.image, hudless_frame.allocation);
        device.destroyImageView(hudless_frame.image_view);
    }
    if (color_conversion_frame.image) {
        device.destroyImageView(color_conversion_frame.image_view);
        vmaDestroyImage(instance.GetAllocator(), color_conversion_frame.image,
                       color_conversion_frame.allocation);
    }
}

void Presenter::DestroyGenerated(Frame* frame, u32 from) {
    const vk::Device device = instance.GetDevice();
    for (u32 i = from; i < frame->generated.size(); ++i) {
        auto& generated = frame->generated[i];
        if (generated.view) {
            device.destroyImageView(generated.view);
        }
        if (generated.image) {
            vmaDestroyImage(instance.GetAllocator(), generated.image, generated.allocation);
        }
        generated = {};
    }
    frame->generated_count = std::min(frame->generated_count, from);
}

u32 Presenter::EnsureGenerated(Frame* frame, u32 count) {
    // Only as many as the setting asks for (FSR 3.1 and DLSS 2x: one): at 4K each is 33 MB,
    // and every presentation frame has its own. The rest are freed (the frame's fence was
    // waited for in GetRenderFrame, so the GPU is done with them).
    count = std::min<u32>(count, u32(frame->generated.size()));
    DestroyGenerated(frame, count);
    const vk::Device device = instance.GetDevice();
    for (u32 i = 0; i < count; ++i) {
        auto& generated = frame->generated[i];
        if (generated.image) {
            continue;
        }
        const VkImageCreateInfo image_info = static_cast<VkImageCreateInfo>(vk::ImageCreateInfo{
            .imageType = vk::ImageType::e2D,
            .format = FrameGenerator::ColorFormat,
            .extent = {frame->width, frame->height, 1},
            .mipLevels = 1,
            .arrayLayers = 1,
            .samples = vk::SampleCountFlagBits::e1,
            .usage = vk::ImageUsageFlagBits::eStorage | vk::ImageUsageFlagBits::eSampled |
                     vk::ImageUsageFlagBits::eTransferSrc | vk::ImageUsageFlagBits::eTransferDst,
        });
        const VmaAllocationCreateInfo alloc_info = {
            .usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE,
        };
        VkImage image{};
        if (vmaCreateImage(instance.GetAllocator(), &image_info, &alloc_info, &image,
                           &generated.allocation, nullptr) != VK_SUCCESS) {
            LOG_ERROR(Render_Vulkan, "Frame generation: no memory for the generated frames");
            DestroyGenerated(frame, i);
            return i;
        }
        generated.image = vk::Image{image};
        SetObjectName(device, generated.image, "Generated frame #{}.{}", frame->id, i);
        generated.view = Check<"create generated frame view">(device.createImageView({
            .image = generated.image,
            .viewType = vk::ImageViewType::e2D,
            .format = FrameGenerator::ColorFormat,
            .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
        }));
    }
    return count;
}

void Presenter::ReleaseFrameGen(Frame* frame) {
    DestroyGenerated(frame);
    if (frame_generator->Wanted()) {
        return; // the remaining presentation frames release their own images when reused
    }
    // Switched off: the other frames free theirs when they are next used.
    if (hudless_frame.image) {
        // The previous frames' commands may still read it.
        draw_scheduler.DeferOperation([allocator = instance.GetAllocator(),
                                       device = instance.GetDevice(),
                                       image = hudless_frame.image, view = hudless_frame.image_view,
                                       allocation = hudless_frame.allocation] {
            device.destroyImageView(view);
            vmaDestroyImage(allocator, image, allocation);
        });
        hudless_frame.image = vk::Image{};
        hudless_frame.image_view = vk::ImageView{};
        hudless_frame.allocation = {};
        hudless_frame.width = hudless_frame.height = 0;
    }
    frame_generator->Release();
}

bool Presenter::IsVideoOutSurface(const AmdGpu::ColorBuffer& color_buffer) const {
    return std::ranges::find(vo_buffers_addr, color_buffer.Address()) != vo_buffers_addr.cend();
}

bool Presenter::RecreateFrame(Frame* frame, u32 width, u32 height, FrameRecreatePolicy& policy,
                              Scheduler& owner, vk::Format format, bool optional) {
    const vk::Device device = instance.GetDevice();
    if (width == 0 || height == 0) [[unlikely]] {
        // bbport: no image can have no size; keep the frame as it is until a real size comes.
        LOG_WARNING(Render_Vulkan, "Frame #{} recreation at {}x{} skipped", frame->id, width,
                    height);
        return false;
    }

    const vk::ImageCreateInfo image_info = {
        .flags = vk::ImageCreateFlagBits::eMutableFormat,
        .imageType = vk::ImageType::e2D,
        .format = format,
        .extent = {width, height, 1},
        .mipLevels = 1,
        .arrayLayers = 1,
        .samples = vk::SampleCountFlagBits::e1,
        .usage = vk::ImageUsageFlagBits::eColorAttachment | vk::ImageUsageFlagBits::eTransferDst |
                 vk::ImageUsageFlagBits::eTransferSrc | vk::ImageUsageFlagBits::eSampled,
    };

    const VmaAllocationCreateInfo alloc_info = {
        .flags = VMA_ALLOCATION_CREATE_WITHIN_BUDGET_BIT,
        .usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE,
        .requiredFlags = 0,
        .preferredFlags = 0,
        .pool = VK_NULL_HANDLE,
        .pUserData = nullptr,
    };

    // bbport: the new image is made before the old one goes, so that a failure leaves the
    // frame usable (frame_recreate.h). Seen in 3.3.3 testing and in a 3.4.0 15-minute run:
    // ErrorInitializationFailed asserted, and a retry once idle failed the same way.
    VkImage unsafe_image{};
    VmaAllocation allocation{};
    vk::ImageView view{};
    VkImageCreateInfo unsafe_image_info = static_cast<VkImageCreateInfo>(image_info);
    // BB_TEST_FRAME_ALLOC_FAILS=N[@M]: N allocations fail as in those reports
    // (ErrorInitializationFailed), starting with the first one after M presented game frames
    // (plain N or M=0: from boot, the first images). An M past boot reaches the keep-old and
    // optional-image fallbacks (FrameAllocFailTest in frame_recreate.h), to check them in game.
    static const FrameAllocFailTest injection =
        FrameAllocFailTest::Parse(std::getenv("BB_TEST_FRAME_ALLOC_FAILS"));
    static std::atomic<int> injected_failures = injection.count;
    const auto attempt = [&]() -> VkResult {
        VkResult result = vmaCreateImage(instance.GetAllocator(), &unsafe_image_info, &alloc_info,
                                         &unsafe_image, &allocation, nullptr);
        if (result == VK_ERROR_OUT_OF_DEVICE_MEMORY) {
            // bbport: VRAM full (the texture cache fills the budget on 4-8 GB cards): past the
            // budget, in system memory if need be, as buffers and images do (buffer.cpp).
            NoteOverBudget("presentation frame");
            VmaAllocationCreateInfo over_budget = alloc_info;
            over_budget.flags &= ~VMA_ALLOCATION_CREATE_WITHIN_BUDGET_BIT;
            result = vmaCreateImage(instance.GetAllocator(), &unsafe_image_info, &over_budget,
                                    &unsafe_image, &allocation, nullptr);
        }
        if (result == VK_SUCCESS && injected_failures.load() > 0 &&
            presented_game_frames.load(std::memory_order_relaxed) >= injection.after_frames &&
            injected_failures.fetch_sub(1) > 0) {
            vmaDestroyImage(instance.GetAllocator(), unsafe_image, allocation);
            return VK_ERROR_INITIALIZATION_FAILED;
        }
        if (result != VK_SUCCESS) {
            return result;
        }
        const vk::ImageViewCreateInfo view_info = {
            .image = vk::Image{unsafe_image},
            .viewType = vk::ImageViewType::e2D,
            .format = format,
            .subresourceRange{
                .aspectMask = vk::ImageAspectFlagBits::eColor,
                .baseMipLevel = 0,
                .levelCount = 1,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
        };
        const auto [view_result, created] = device.createImageView(view_info);
        if (view_result != vk::Result::eSuccess) {
            vmaDestroyImage(instance.GetAllocator(), unsafe_image, allocation);
            return static_cast<VkResult>(view_result);
        }
        view = created;
        return VK_SUCCESS;
    };
    // The caller can go on without a new image: the frame's previous one, or none for the
    // optional ones (HUD-free copy, HDR scratch). Otherwise (a first presentation image) a few
    // attempts a little apart, then fatal as before.
    const bool has_fallback = optional || (frame->image && frame->image_view);
    VkResult result = attempt();
    if (result != VK_SUCCESS && result != VK_ERROR_OUT_OF_DEVICE_MEMORY) [[unlikely]] {
        // bbport: seen while another program registered a Vulkan layer, and once in a 15-minute
        // run on entering a new area. The heaps go to the log with the failures that are
        // logged (1st, 2nd, 4th... in a row). On the first failure of a streak, one retry once
        // this thread's submitted work is done: not vkDeviceWaitIdle, which needs every queue
        // externally synchronized while the other thread may be submitting. Later failures of
        // the streak back off instead (frame_recreate.h).
        const bool first_failure = policy.Failures() == 0;
        if (FrameRecreatePolicy::ShouldLogCount(policy.Failures() + 1)) {
            LOG_WARNING(Render_Vulkan,
                        "Frame #{} image {}x{} {} allocation failed with {}{}", frame->id,
                        width, height, vk::to_string(format), vk::to_string(vk::Result{result}),
                        first_failure ? "; retrying once idle" : "");
            const VkPhysicalDeviceMemoryProperties* props = nullptr;
            vmaGetMemoryProperties(instance.GetAllocator(), &props);
            VmaBudget budgets[VK_MAX_MEMORY_HEAPS]{};
            vmaGetHeapBudgets(instance.GetAllocator(), budgets);
            for (u32 i = 0; i < props->memoryHeapCount; ++i) {
                std::printf("GPU: heap %u%s: %llu MiB, used %llu of budget %llu MiB\n", i,
                            props->memoryHeaps[i].flags & VK_MEMORY_HEAP_DEVICE_LOCAL_BIT
                                ? " (device-local)" : "",
                            (unsigned long long)(props->memoryHeaps[i].size >> 20),
                            (unsigned long long)(budgets[i].usage >> 20),
                            (unsigned long long)(budgets[i].budget >> 20));
            }
            std::fflush(stdout);
        }
        if (first_failure) {
            owner.WaitSubmitted();
            result = attempt();
        }
    }
    for (int retry = 0; result != VK_SUCCESS && !has_fallback && retry < 5; ++retry) {
        LOG_ERROR(Render_Vulkan, "Allocating a first {}x{} presentation image failed with {}, "
                  "retrying", width, height, vk::to_string(vk::Result{result}));
        std::printf("Presentation: a first %ux%u frame image could not be allocated (%s); "
                    "retrying\n",
                    width, height, vk::to_string(vk::Result{result}).c_str());
        std::fflush(stdout);
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        result = attempt();
    }
    if (result != VK_SUCCESS) [[unlikely]] {
        const auto action = policy.OnFailure(has_fallback);
        if (action == FrameRecreatePolicy::Action::Fatal) {
            LOG_CRITICAL(Render_Vulkan,
                         "Failed allocating a {}x{} presentation image with error {} ({} in a "
                         "row, {} fallback)",
                         width, height, vk::to_string(vk::Result{result}), policy.Failures(),
                         has_fallback ? "with a" : "no");
            UNREACHABLE();
        }
        if (policy.ShouldLog()) {
            LOG_ERROR(Render_Vulkan,
                      "Failed allocating a {}x{} presentation image with error {} ({} in a "
                      "row); keeping the {}x{} one, trying again in {} frame(s)",
                      width, height, vk::to_string(vk::Result{result}), policy.Failures(),
                      frame->width, frame->height,
                      FrameRecreatePolicy::BackoffFrames(policy.Failures()));
            std::printf("Presentation: a %ux%u frame image could not be allocated (%s, %u in a "
                        "row); keeping the %ux%u one, trying again in %u frame(s)\n",
                        width, height, vk::to_string(vk::Result{result}).c_str(),
                        policy.Failures(), frame->width, frame->height,
                        FrameRecreatePolicy::BackoffFrames(policy.Failures()));
            std::fflush(stdout);
        }
        return false;
    }
    if (policy.Failures() != 0) {
        std::printf("Presentation: a %ux%u frame image was allocated after %u failures in a "
                    "row\n",
                    width, height, policy.Failures());
        std::fflush(stdout);
    }
    policy.OnSuccess();

    if (frame->image_view) {
        device.destroyImageView(frame->image_view);
    }
    if (frame->image) {
        vmaDestroyImage(instance.GetAllocator(), frame->image, frame->allocation);
    }
    DestroyGenerated(frame); // made again at the new size when needed

    frame->image = vk::Image{unsafe_image};
    frame->allocation = allocation;
    SetObjectName(device, frame->image, "Frame image #{}", frame->id);
    frame->image_view = view;
    frame->width = width;
    frame->height = height;
    return true;
}

Frame* Presenter::PrepareLastFrame() {
    if (last_submit_frame == nullptr) {
        return nullptr;
    }

    Frame* frame = last_submit_frame;

    while (true) {
        vk::Result result = instance.GetDevice().waitForFences(frame->present_done, false,
                                                               std::numeric_limits<u64>::max());
        if (result == vk::Result::eSuccess) {
            break;
        }
        if (result == vk::Result::eTimeout) {
            continue;
        }
        if (result == vk::Result::eErrorDeviceLost) {
            instance.DeviceLost("waiting for a frame");
        }
    }

    auto& scheduler = flip_scheduler;
    scheduler.EndRendering();
    const auto cmdbuf = scheduler.CommandBuffer();

    const auto frame_subresources = vk::ImageSubresourceRange{
        .aspectMask = vk::ImageAspectFlagBits::eColor,
        .baseMipLevel = 0,
        .levelCount = 1,
        .baseArrayLayer = 0,
        .layerCount = VK_REMAINING_ARRAY_LAYERS,
    };

    const auto pre_barrier =
        vk::ImageMemoryBarrier2{.srcStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
                                .srcAccessMask = vk::AccessFlagBits2::eColorAttachmentRead,
                                .dstStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
                                .dstAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite,
                                .oldLayout = vk::ImageLayout::eShaderReadOnlyOptimal,
                                .newLayout = vk::ImageLayout::eGeneral,
                                .image = frame->image,
                                .subresourceRange{frame_subresources}};

    cmdbuf.pipelineBarrier2(vk::DependencyInfo{
        .imageMemoryBarrierCount = 1,
        .pImageMemoryBarriers = &pre_barrier,
    });

    // Flush frame creation commands.
    frame->ready_semaphore = scheduler.GetWorkSemaphore()->Handle();
    frame->ready_tick = scheduler.CurrentTick();
    SubmitInfo info{};
    scheduler.Flush(info);
    return frame;
}

static vk::Format GetFrameViewFormat(const Libraries::VideoOut::PixelFormat format) {
    switch (format) {
    case Libraries::VideoOut::PixelFormat::A8B8G8R8Srgb:
        return vk::Format::eR8G8B8A8Srgb;
    case Libraries::VideoOut::PixelFormat::A8R8G8B8Srgb:
        return vk::Format::eB8G8R8A8Srgb;
    case Libraries::VideoOut::PixelFormat::A2R10G10B10:
    case Libraries::VideoOut::PixelFormat::A2R10G10B10Srgb:
    case Libraries::VideoOut::PixelFormat::A2R10G10B10Bt2020Pq:
        return vk::Format::eA2R10G10B10UnormPack32;
    default:
        break;
    }
    UNREACHABLE_MSG("Unknown format={}", static_cast<u32>(format));
    return {};
}

// bbport: raw copy of an image for BB_FRAME_DUMP_TRIGGER, written once the GPU is done.
static void DumpRaw(const Instance& instance, Scheduler& scheduler, vk::CommandBuffer cmdbuf,
                    vk::Image image, vk::ImageLayout layout, u32 w, u32 h, const char* name,
                    int index) {
    const VkBufferCreateInfo buffer_ci{.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
                                       .size = VkDeviceSize(w) * h * 4,
                                       .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT};
    const VmaAllocationCreateInfo alloc_ci{
        .flags = VMA_ALLOCATION_CREATE_MAPPED_BIT | VMA_ALLOCATION_CREATE_HOST_ACCESS_RANDOM_BIT,
        .usage = VMA_MEMORY_USAGE_AUTO_PREFER_HOST};
    VkBuffer buffer{};
    VmaAllocation allocation{};
    VmaAllocationInfo info{};
    if (vmaCreateBuffer(instance.GetAllocator(), &buffer_ci, &alloc_ci, &buffer, &allocation,
                        &info) != VK_SUCCESS) {
        return;
    }
    cmdbuf.copyImageToBuffer(image, layout, buffer,
                             vk::BufferImageCopy{.imageSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
                                                 .imageExtent = {w, h, 1}});
    const char* dir = std::getenv("BB_DUMP_DIR");
    char path[512];
    std::snprintf(path, sizeof(path), "%s/%s_%03d_%ux%u.raw", dir && *dir ? dir : "out/dump", name,
                  index, w, h);
    scheduler.DeferPriorityOperation([allocator = instance.GetAllocator(), buffer, allocation, info,
                                      size = buffer_ci.size, file = std::string{path}] {
        vmaInvalidateAllocation(allocator, allocation, 0, VK_WHOLE_SIZE);
        if (FILE* f = std::fopen(file.c_str(), "wb")) {
            std::fwrite(info.pMappedData, 1, size, f);
            std::fclose(f);
        }
        vmaDestroyBuffer(allocator, buffer, allocation);
    });
}

Frame* Presenter::PrepareFrame(const Libraries::VideoOut::BufferAttributeGroup& attribute,
                               VAddr cpu_address) {
    // bbport: Reflex (vk_reflex.h): the game's flip ends this frame's simulation.
    const u64 reflex_id = Reflex::Get().OnFlip();
    // bbport: BB_FRAME_DUMP_TRIGGER=<file>: when the file exists it is removed and this frame's
    // guest display buffer and presented image are written to BB_DUMP_DIR (default out/dump)
    // as raw 32-bit pixels (menus and movies included; the upscaler dumps scene frames only).
    static const char* frame_dump_trigger = std::getenv("BB_FRAME_DUMP_TRIGGER");
    static int frame_dump_index = 0;
    const bool frame_dump = frame_dump_trigger && std::remove(frame_dump_trigger) == 0;
    // bbport: scaled upscaler presets: the output-size display buffer drawn by the port.
    TemporalUpscaler::Display display{};
    const bool upscaled = rasterizer->GetUpscaler().DisplayOverride(cpu_address, display);
    VideoCore::ImageId image_id{};
    if (!upscaled) {
        auto desc = VideoCore::TextureCache::ImageDesc{attribute, cpu_address};
        image_id = texture_cache.FindImage(desc);
        texture_cache.UpdateImage(image_id);
    }

    Frame* frame = GetRenderFrame(false);

    const auto frame_subresources = vk::ImageSubresourceRange{
        .aspectMask = vk::ImageAspectFlagBits::eColor,
        .baseMipLevel = 0,
        .levelCount = 1,
        .baseArrayLayer = 0,
        .layerCount = VK_REMAINING_ARRAY_LAYERS,
    };

    const auto pre_barrier = vk::ImageMemoryBarrier2{
        .srcStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
        .srcAccessMask = vk::AccessFlagBits2::eColorAttachmentRead,
        .dstStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
        .dstAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite,
        .oldLayout = vk::ImageLayout::eUndefined,
        .newLayout = vk::ImageLayout::eColorAttachmentOptimal,
        .image = frame->image,
        .subresourceRange{frame_subresources},
    };

    draw_scheduler.EndRendering();
    const auto cmdbuf = draw_scheduler.CommandBuffer();
    cmdbuf.pipelineBarrier2(vk::DependencyInfo{
        .imageMemoryBarrierCount = 1,
        .pImageMemoryBarriers = &pre_barrier,
    });

    VideoCore::ImageViewInfo view_info{};
    view_info.format = GetFrameViewFormat(attribute.attrib.pixel_format);
    // Exclude alpha from output frame to avoid blending with UI.
    view_info.mapping.a = vk::ComponentSwizzle::eOne;

    vk::ImageView image_view{};
    vk::Extent2D image_size{};
    if (upscaled) {
        const auto device = instance.GetDevice();
        image_view = Check(device.createImageView({
            .image = display.image,
            .viewType = vk::ImageViewType::e2D,
            .format = view_info.format,
            .components = {vk::ComponentSwizzle::eIdentity, vk::ComponentSwizzle::eIdentity,
                           vk::ComponentSwizzle::eIdentity, vk::ComponentSwizzle::eOne},
            .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
        }));
        draw_scheduler.DeferOperation([device, image_view] { device.destroyImageView(image_view); });
        image_size = vk::Extent2D{display.width, display.height};
        const vk::ImageMemoryBarrier2 to_read{
            .srcStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
            .srcAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite,
            .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
            .dstAccessMask = vk::AccessFlagBits2::eShaderRead,
            .oldLayout = vk::ImageLayout::eGeneral,
            .newLayout = vk::ImageLayout::eShaderReadOnlyOptimal,
            .image = display.image,
            .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
        };
        cmdbuf.pipelineBarrier2({.imageMemoryBarrierCount = 1, .pImageMemoryBarriers = &to_read});
    } else {
        auto& image = texture_cache.GetImage(image_id);
        if (frame_dump) {
            runtime.Transit(&image, vk::ImageLayout::eTransferSrcOptimal,
                            vk::PipelineStageFlagBits2::eTransfer, vk::AccessFlagBits2::eTransferRead);
            runtime.FlushBarriers();
            DumpRaw(instance, draw_scheduler, cmdbuf, image.GetImage(),
                    vk::ImageLayout::eTransferSrcOptimal, image.info.size.width,
                    image.info.size.height, "display", frame_dump_index);
        }
        image_view = *image.FindView(view_info).image_view;
        image_size = vk::Extent2D{image.info.size.width, image.info.size.height};
        runtime.Transit(&image, vk::ImageLayout::eShaderReadOnlyOptimal,
                        vk::PipelineStageFlagBits2::eFragmentShader,
                        vk::AccessFlagBits2::eShaderRead);
        runtime.FlushBarriers();
    }
    expected_ratio = static_cast<float>(image_size.width) / static_cast<float>(image_size.height);

    // bbport: the frame has the display's size (fitted to the picture's shape, see
    // SetExpectedGameSize), so a smaller output resolution is upscaled here, before the frame
    // generation inputs and the HDR encode (both stay after it, on SDR RGBA8 frames). FSR 1 EASU
    // (+ RCAS) by default (bbport.ini present_upscale / present_rcas, BB_PRESENT_UPSCALE /
    // BB_PRESENT_RCAS); linear is the post process pass's bilinear sampler. Equal sizes and
    // downscales take the plain pass as before.
    {
        const auto& bb = BbSettings::Get();
        const float stops = bb.present_rcas.load(std::memory_order_relaxed);
        fsr_settings.enable =
            BbSettings::PresentUsesEasu(bb.present_upscale.load(std::memory_order_relaxed),
                                        image_size.width, image_size.height, frame->width,
                                        frame->height);
        fsr_settings.use_rcas = BbSettings::PresentUsesRcas(stops);
        fsr_settings.rcas_attenuation = stops;
        const PresentUpscale now{
            .source_width = image_size.width,
            .source_height = image_size.height,
            .frame_width = frame->width,
            .frame_height = frame->height,
            .easu = fsr_settings.enable,
            .rcas_stops = fsr_settings.enable && fsr_settings.use_rcas ? stops : 0.0f,
        };
        if (now != last_present_upscale) {
            last_present_upscale = now;
            if (image_size.width == frame->width && image_size.height == frame->height) {
                std::printf("Present upscale: %ux%u, same size as the display frame (no scaling)\n",
                            image_size.width, image_size.height);
            } else if (fsr_settings.enable && fsr_settings.use_rcas) {
                std::printf("Present upscale: %ux%u -> %ux%u with FSR 1 EASU + RCAS %.2f stops\n",
                            image_size.width, image_size.height, frame->width, frame->height,
                            stops);
            } else {
                std::printf("Present upscale: %ux%u -> %ux%u with %s\n", image_size.width,
                            image_size.height, frame->width, frame->height,
                            fsr_settings.enable ? "FSR 1 EASU (RCAS off)" : "bilinear filtering");
            }
        }
    }
    // A UNORM view (the 10-bit formats) holds encoded values; an sRGB view samples linear light.
    const bool linear_view = view_info.format == vk::Format::eR8G8B8A8Srgb ||
                             view_info.format == vk::Format::eB8G8R8A8Srgb;
    auto* profiler = GpuProfiler::Get();
    const bool profile = fsr_settings.enable && profiler && profiler->Records(&draw_scheduler);
    const u64 profile_resume = profile ? profiler->Current() : 0;
    image_view = fsr_pass.Render(cmdbuf, image_view, image_size, {frame->width, frame->height},
                                 fsr_settings, linear_view, profile ? "present: fsr1" : nullptr);
    if (profile) {
        profiler->Mark(0xF5C0'0100ull, [] { return std::string{"present: compose"}; });
    }

    // Vulkan has no sRGB variant of the 10-bit format, so an A2R10G10B10Srgb buffer reaches
    // the post process pass still sRGB encoded and has to be decoded there instead.
    pp_settings.srgb_input =
        attribute.attrib.pixel_format == Libraries::VideoOut::PixelFormat::A2R10G10B10Srgb;
    // Keep rendered, generated and HUD-less pictures in the same SDR encoding. HDR10 PQ
    // and SDR-on-HDR desktop compensation belong at presentation, after interpolation.
    auto composition = pp_settings;
    composition.hdr = 0;
    composition.sdr_on_hdr = 0;
    pp_pass.Render(cmdbuf, image_view, image_size, *frame, composition);
    if (profile && profile_resume) {
        profiler->Resume(profile_resume); // the segment before the upscale goes on
    }

    // bbport: frame generation: the frames between the previous frame and this one.
    frame->generated_count = 0;
    // bbport: also for the upscaled display (outputs other than 1080p): composed the same way.
    if (!frame_generator->Wanted()) {
        ReleaseFrameGen(frame);
        frame_generator->Skip("frame generation off");
    } else if (frame->kept_old_size) {
        // bbport: this frame could not be resized (frame_recreate.h) and has its old size while
        // others may have the new one. The FSR 3.1 context, the DLSS-G feature and the HUD-free
        // copy are made for one size: frames of both sizes back to back would tear them down and
        // make them again every frame, under the memory pressure that failed the resize. No
        // generated frames for it, as when generation pauses.
        if (!fg_skipped_old_size) {
            fg_skipped_old_size = true;
            std::printf("Frame generation: paused while a presentation frame keeps its old "
                        "%ux%u size\n",
                        frame->width, frame->height);
            std::fflush(stdout);
        }
        frame_generator->Skip("presentation frame kept its old size");
    } else {
        fg_skipped_old_size = false;
        // At most the frames the display can show between two of the game's (present thread):
        // more are dropped by Mailbox, and with FIFO they would slow the game to the display.
        const u32 count = std::min(EnsureGenerated(frame, frame_generator->WantedCount()),
                                   frame_gen_limit.load(std::memory_order_relaxed));
        // The picture before the UI, composed like the frame (equal outside the UI).
        vk::Image hudless{};
        vk::ImageView hudless_view{};
        vk::Extent2D hudless_size{};
        const auto source = frame_generator->Hudless(view_info.format, hudless_size);
        const bool hudless_wanted = count && source && hudless_size == image_size;
        const auto hudless_fits = [&] {
            return hudless_frame.image && hudless_frame.width == frame->width &&
                   hudless_frame.height == frame->height;
        };
        // After failed allocations, not every frame (frame_recreate.h).
        if (hudless_wanted && !hudless_fits() && hudless_recreate_policy.ShouldRetry()) {
            // A single image: the previous frames' commands may still read the old one.
            draw_scheduler.WaitSubmitted();
            RecreateFrame(&hudless_frame, frame->width, frame->height, hudless_recreate_policy,
                          draw_scheduler, FrameGenerator::ColorFormat, true);
        }
        // Not allocated (RecreateFrame failed): generation goes on without the HUD-free image.
        if (hudless_wanted && hudless_fits()) {
            const vk::ImageMemoryBarrier2 to_target{
                .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
                .srcAccessMask = vk::AccessFlagBits2::eShaderRead,
                .dstStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
                .dstAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite,
                .oldLayout = vk::ImageLayout::eUndefined,
                .newLayout = vk::ImageLayout::eColorAttachmentOptimal,
                .image = hudless_frame.image,
                .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
            };
            cmdbuf.pipelineBarrier2({.imageMemoryBarrierCount = 1, .pImageMemoryBarriers = &to_target});
            const auto scaled = fsr_pass.Render(cmdbuf, source, hudless_size,
                                                {frame->width, frame->height}, fsr_settings,
                                                linear_view,
                                                profile ? "present: fsr1 UI-free" : nullptr);
            if (profile) {
                profiler->Mark(0xF5C0'0101ull,
                               [] { return std::string{"present: compose UI-free"}; });
            }
            pp_pass.Render(cmdbuf, scaled, hudless_size, hudless_frame, composition);
            if (profile && profile_resume) {
                profiler->Resume(profile_resume);
            }
            hudless = hudless_frame.image;
            hudless_view = hudless_frame.image_view;
        }
        // Also with none: a frame without generation starts the sequence over.
        std::array<FrameGenerator::Output, FrameGenerator::MaxGenerated> outputs{};
        for (u32 i = 0; i < count; ++i) {
            outputs[i] = {frame->generated[i].image, frame->generated[i].view};
        }
        frame->generated_count = frame_generator->Generate(
            cmdbuf, frame->image, frame->image_view,
            vk::ImageUsageFlagBits::eColorAttachment | vk::ImageUsageFlagBits::eTransferDst |
                vk::ImageUsageFlagBits::eTransferSrc | vk::ImageUsageFlagBits::eSampled,
            hudless, hudless_view, frame->width, frame->height,
            std::span<const FrameGenerator::Output>{outputs.data(), count});
    }
    if (frame_dump) {
        // The presented image as the swapchain blit reads it (General after the pass), and
        // the generated frames shown before it.
        const vk::MemoryBarrier2 done{.srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
                                      .srcAccessMask = vk::AccessFlagBits2::eMemoryWrite,
                                      .dstStageMask = vk::PipelineStageFlagBits2::eTransfer,
                                      .dstAccessMask = vk::AccessFlagBits2::eTransferRead};
        cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &done});
        for (u32 i = 0; i < frame->generated_count; ++i) {
            char name[16];
            std::snprintf(name, sizeof(name), "generated%u", i);
            DumpRaw(instance, draw_scheduler, cmdbuf, frame->generated[i].image,
                    vk::ImageLayout::eGeneral, frame->width, frame->height, name,
                    frame_dump_index);
        }
        DumpRaw(instance, draw_scheduler, cmdbuf, frame->image, vk::ImageLayout::eGeneral,
                frame->width, frame->height, "output", frame_dump_index);
        ++frame_dump_index;
    }

    // Flush frame creation commands.
    frame->ready_semaphore = draw_scheduler.GetWorkSemaphore()->Handle();
    frame->ready_tick = draw_scheduler.CurrentTick();
    frame->reflex_id = reflex_id;
    SubmitInfo info{};
    draw_scheduler.Flush(info);

    // bbport: the GPU command thread runs at most BB_FRAMES_AHEAD (default 1) guest frames
    // ahead of the GPU: it waits here for the frame that many flips back. When the GPU is the
    // bottleneck it finishes frames at an even rate; without this bound the command thread ran
    // ahead and then blocked wherever a resource ran out, so flips (and the guest's frame
    // timing) came in bursts: 12.5/25 ms alternation at 80 FPS. 0 turns it off.
    static const u32 frames_ahead = [] {
        const char* env = std::getenv("BB_FRAMES_AHEAD");
        return env ? u32(std::max(0, std::atoi(env))) : 1u;
    }();
    if (frames_ahead) {
        recent_frame_ticks.push_back(frame->ready_tick);
        while (recent_frame_ticks.size() > frames_ahead) {
            const u64 tick = recent_frame_ticks.front();
            recent_frame_ticks.pop_front();
            if (recent_frame_ticks.size() == frames_ahead) {
                draw_scheduler.Wait(tick);
            }
        }
    }
    // End the marker span here, but do not sleep before publishing this frame to VideoOut.
    const auto submission = Reflex::Get().OnSubmitted(reflex_id);
    frame->reflex_id = submission.id;
    frame->handoff = {};
    if (FrameHandoff::Enabled()) {
        frame->handoff.work_started = submission.started;
        frame->handoff.prepared = FrameHandoff::Clock::now();
    }
    return frame;
}

Frame* Presenter::PrepareBlankFrame(bool present_thread) {
    // Request a free presentation frame.
    Frame* frame = GetRenderFrame(present_thread);
    frame->generated_count = 0;
    frame->reflex_id = 0;
    frame->handoff = {};

    auto& scheduler = present_thread ? present_scheduler : draw_scheduler;
    scheduler.EndRendering();

    const auto cmdbuf = scheduler.CommandBuffer();

    constexpr vk::ImageSubresourceRange simple_subresource = {
        .aspectMask = vk::ImageAspectFlagBits::eColor,
        .levelCount = 1,
        .layerCount = 1,
    };
    const auto pre_barrier = vk::ImageMemoryBarrier2{
        .srcStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
        .srcAccessMask = vk::AccessFlagBits2::eColorAttachmentRead,
        .dstStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
        .dstAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite,
        .oldLayout = vk::ImageLayout::eUndefined,
        .newLayout = vk::ImageLayout::eColorAttachmentOptimal,
        .image = frame->image,
        .subresourceRange = simple_subresource,
    };

    const auto post_barrier = vk::ImageMemoryBarrier2{
        .srcStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
        .srcAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eFragmentShader,
        .dstAccessMask = vk::AccessFlagBits2::eShaderRead,
        .oldLayout = vk::ImageLayout::eColorAttachmentOptimal,
        .newLayout = vk::ImageLayout::eGeneral,
        .image = frame->image,
        .subresourceRange = simple_subresource,
    };

    const vk::RenderingAttachmentInfo attachment = {
        .imageView = frame->image_view,
        .imageLayout = vk::ImageLayout::eColorAttachmentOptimal,
        .loadOp = vk::AttachmentLoadOp::eClear,
        .storeOp = vk::AttachmentStoreOp::eStore,
    };
    const vk::RenderingInfo rendering_info = {
        .renderArea =
            {
                .extent = {frame->width, frame->height},
            },
        .layerCount = 1,
        .colorAttachmentCount = 1u,
        .pColorAttachments = &attachment,
    };

    cmdbuf.pipelineBarrier2(vk::DependencyInfo{
        .imageMemoryBarrierCount = 1,
        .pImageMemoryBarriers = &pre_barrier,
    });

    cmdbuf.beginRendering(rendering_info);
    cmdbuf.endRendering();

    cmdbuf.pipelineBarrier2(vk::DependencyInfo{
        .imageMemoryBarrierCount = 1,
        .pImageMemoryBarriers = &post_barrier,
    });

    // Flush frame creation commands.
    frame->ready_semaphore = scheduler.GetWorkSemaphore()->Handle();
    frame->ready_tick = scheduler.CurrentTick();
    SubmitInfo info{};
    scheduler.Flush(info);
    return frame;
}

void Presenter::Present(Frame* frame, bool is_reusing_frame, bool is_game_frame) {
    if (!is_reusing_frame && is_game_frame && FrameHandoff::Enabled()) {
        handoff_timings.Add(frame->handoff, FrameHandoff::Clock::now());
    }
    u32 shown = 0;
    // bbport: VideoOut's Flip counted this game frame (NoteFlipQueued) before queueing it.
    if (!is_reusing_frame && is_game_frame) {
        queued_flips.fetch_sub(1, std::memory_order_relaxed);
    }
    // Free the frame for reuse
    const auto free_frame = [&] {
        if (!is_reusing_frame) {
            presentation_counts.unpresented_generated += frame->generated_count - shown;
            last_submit_frame = frame;
            std::scoped_lock fl{free_mutex};
            free_queue.push(frame);
            free_cv.notify_one();
        }
        ReportFrameGeneration();
    };

    // bbport: a minimized window has no pixels on Windows; keep the swapchain and skip
    // presenting until the window is restored. SDL keeps the window's size while minimized,
    // but the surface is 0x0, and a swapchain made then (after a failed present) has no area:
    // it is made again once the surface has one (present_target.h). The swapchain is also made
    // again when the window was resized, and when frame generation was switched in the menu:
    // it presents several images per game frame and the swapchain gets one more for them
    // (Swapchain::SetSurfaceProperties).
    const bool frame_gen = frame_generator->Wanted();
    const vk::Extent2D swapchain_extent = swapchain.GetExtent();
    const PresentTarget target = ChoosePresentTarget(
        {u32(window.GetWidth()), u32(window.GetHeight())},
        {swapchain.GetWidth(), swapchain.GetHeight()},
        {swapchain_extent.width, swapchain_extent.height}, frame_gen != swapchain_frame_gen,
        [this] {
            const vk::Extent2D surface = swapchain.SurfaceExtent();
            return PresentExtent{surface.width, surface.height};
        });
    if (target == PresentTarget::Skip) {
        free_frame();
        return;
    }
    if (target == PresentTarget::Recreate) {
        swapchain_frame_gen = frame_gen;
        swapchain.Recreate(window.GetWidth(), window.GetHeight());
        const vk::Extent2D made = swapchain.GetExtent();
        if (made.width == 0 || made.height == 0) {
            free_frame(); // minimized in between: nothing to present into yet
            return;
        }
    }

    // bbport: frame generation: the generated frames first, then the game's own, evenly
    // spaced over the interval between the game's frames (the generated ones belong to the
    // time before this frame). A frame shown again has none.
    u32 generated = is_reusing_frame ? 0 : frame->generated_count;
    const auto start = std::chrono::steady_clock::now();
    if (!is_reusing_frame && is_game_frame) {
        const double ms =
            std::chrono::duration<double, std::milli>(start - last_game_present).count();
        if (ms > 1.0 && ms < 100.0) {
            game_frame_ms = game_frame_ms + (ms - game_frame_ms) * 0.1;
        }
        last_game_present = start;
        Dlss5Guard();
    }
    const auto step = std::chrono::duration_cast<std::chrono::steady_clock::duration>(
        std::chrono::duration<double, std::milli>(game_frame_ms / (generated + 1)));
    // The game must never wait for generated frames: when every frame is in use (the GPU
    // thread would block on the next one, and the game on its GPU work: Uncharted 3 asserts
    // in FrameBegin) they are dropped and the game's frame goes out at once. So they are when
    // a newer game frame already waits: its own images are more recent.
    const auto behind = [this] {
        if (queued_flips.load(std::memory_order_relaxed) > 0) {
            return true;
        }
        std::scoped_lock lock{free_mutex};
        return free_queue.empty();
    };
    if (generated && behind()) {
        generated = 0;
    }
    double paced_ms = 0.0; // the sleep between this frame's images
    const auto wait_until = [&](std::chrono::steady_clock::time_point at) {
        const auto now = std::chrono::steady_clock::now();
        Common::PreciseSleepUntil(at);
        const double ms =
            std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - now)
                .count();
        paced_ms += ms;
        if (FpsLog()) {
            swap_timing.sleep += ms;
        }
    };
    for (; shown < generated; ++shown) {
        if (shown > 0) {
            if (behind()) {
                break;
            }
            wait_until(start + step * shown);
        }
        if (!PresentImage(frame, frame->generated[shown].image, false)) {
            break;
        }
        BbSettings::Get().status.presented_generated_frames.fetch_add(1, std::memory_order_relaxed);
    }
    if (shown && !behind()) {
        wait_until(start + step * shown);
    }
    const auto presented_generated = std::chrono::steady_clock::now();
    // bbport: Reflex markers and present id for a game frame shown for the first time.
    const u64 reflex_id = is_reusing_frame || !is_game_frame ? 0 : frame->reflex_id;
    if (!PresentImage(frame, frame->image, true, reflex_id)) {
        if (shown) {
            // The frame's fence was not reset and so does not cover the generated frames'
            // blits: they must be done before the frame is drawn again.
            present_scheduler.Finish();
        }
        free_frame();
        return;
    }
    if (!is_reusing_frame && is_game_frame) {
        ++presentation_counts.game_images;
        presented_game_frames.fetch_add(1, std::memory_order_relaxed);
        UpdateFrameGenLimit(frame_gen,
                            std::chrono::duration<double, std::milli>(
                                std::chrono::steady_clock::now() - start)
                                .count(),
                            paced_ms);
        auto& s = BbSettings::Get();
        const double interval = game_frame_ms.load(std::memory_order_relaxed);
        if (interval > 0.0) {
            s.status.measured_render_fps.store(float(1000.0 / interval), std::memory_order_relaxed);
            s.status.measured_frame_time_ms.store(float(interval), std::memory_order_relaxed);
        }
        s.status.hdr_swapchain_active.store(swapchain.GetHDR(), std::memory_order_relaxed);
    }
    if (FpsLog() && is_game_frame && !is_reusing_frame) {
        static auto window = start;
        static u32 frames = 0, made = 0, shown_total = 0;
        static double busy_ms = 0.0, present_ms = 0.0;
        ++frames;
        made += frame->generated_count;
        shown_total += shown;
        const auto end = std::chrono::steady_clock::now();
        busy_ms += std::chrono::duration<double, std::milli>(end - start).count();
        present_ms += std::chrono::duration<double, std::milli>(end - presented_generated).count();
        const double elapsed = std::chrono::duration<double>(end - window).count();
        if (elapsed >= 5.0) {
            std::printf("Frame generation pacing: %.1f game frames/s, %u generated, %u shown, "
                        "Present %.2f ms/frame (last image %.2f ms), interval %.2f ms\n",
                        frames / elapsed, made, shown_total, busy_ms / frames, present_ms / frames,
                        game_frame_ms.load());
            const auto& t = swap_timing;
            std::printf("Swap thread per game frame: acquire %.2f ms, record %.2f, submit %.2f, "
                        "submit lock wait %.2f, present %.2f, pacing sleep %.2f\n",
                        t.acquire / frames, t.record / frames, t.submit / frames, t.lock / frames,
                        t.present / frames, t.sleep / frames);
            swap_timing = {};
            window = end;
            frames = made = shown_total = 0;
            busy_ms = present_ms = 0.0;
        }
    }

    free_frame();
    if (!is_reusing_frame && is_game_frame) {
        DebugState.IncFlipFrameNum();
    }
}

void Presenter::Dlss5Guard() {
    // DLSS 5 runs only at a fixed 60 FPS: game frames that stay longer than 16.7 ms slow the
    // game itself (Bloodborne slows its time on long frames). Two seconds of them set the
    // warning (the menu, Dlss5SlowNotice); as long again under, it clears. One compare a flip.
    auto& settings = BbSettings::Get();
    if (!settings.dlss5_active.load(std::memory_order_relaxed)) {
        return;
    }
    // run.py's crash rule: a start with DLSS 5 on that never logged this line crashed with it.
    if (dlss5_frames < 300 && ++dlss5_frames == 300) {
        std::puts("DLSS 5: running");
    }
    constexpr u32 Frames = 120;
    if (game_frame_ms.load(std::memory_order_relaxed) > 17.2) {
        dlss5_slow_frames = std::min(dlss5_slow_frames + 1, Frames);
        if (dlss5_slow_frames == Frames && !settings.dlss5_slow) {
            settings.dlss5_slow = true;
            std::printf("DLSS 5: too slow here, game frames %.1f ms (the game slows down)%s\n",
                        game_frame_ms.load(),
                        BbSettings::Dlss5OutputTooLarge(settings.output_res.load(std::memory_order_relaxed))
                            ? "; use 2560x1440 output (sharper than NR upscaling at 4K), or NR "
                              "upscaling with DLSS Balanced and ray tracing Off"
                            : "");
        }
    } else if (dlss5_slow_frames > 0 && --dlss5_slow_frames == 0 && settings.dlss5_slow) {
        settings.dlss5_slow = false;
        std::printf("DLSS 5: 60 FPS again\n");
    }
}

void Presenter::ReportFrameGeneration() {
    auto& settings = BbSettings::Get();
    const auto& status = settings.status;
    presentation_counts.dlss_pairs = status.dlss_frame_gen_pairs.load(std::memory_order_relaxed);
    presentation_counts.fsr_pairs = status.fsr_frame_gen_pairs.load(std::memory_order_relaxed);
    presentation_counts.generated = status.generated_frames.load(std::memory_order_relaxed);
    presentation_counts.accepted_generated =
        status.presented_generated_frames.load(std::memory_order_relaxed);
    const auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                            std::chrono::steady_clock::now().time_since_epoch())
                            .count();
    const auto report = presentation_telemetry.Poll(now_ms, presentation_counts);
    if (!report) {
        return;
    }
    const auto& t = report->totals;
    const auto& d = report->delta;
    const auto* inactive = status.frame_gen_inactive_reason.load(std::memory_order_relaxed);
    const auto* fallback = status.frame_gen_fallback_reason.load(std::memory_order_relaxed);
    // The game's stdout is unbuffered. Format in memory and write once, as the RT
    // reporter does, rather than issuing a write for each printf conversion on
    // the present thread.
    char text[1536];
    const int length = std::snprintf(
        text, sizeof(text),
        "Frame generation telemetry (%.2f s): totals DLSS pairs=%llu, FSR "
        "pairs=%llu, "
        "generated=%llu, accepted generated=%llu; interval generated=%llu, "
        "accepted generated=%llu, not presented=%llu, failed presents=%llu; "
        "game-present FPS=%.1f, accepted-image FPS=%.1f; requested=%s, latest "
        "pair=%s x%d, "
        "HDR=%s, inactive=%.160s, fallback=%.160s\n",
        report->seconds, (unsigned long long)t.dlss_pairs, (unsigned long long)t.fsr_pairs,
        (unsigned long long)t.generated, (unsigned long long)t.accepted_generated,
        (unsigned long long)d.generated, (unsigned long long)d.accepted_generated,
        (unsigned long long)d.unpresented_generated, (unsigned long long)d.failed_presents,
        report->GamePresentFps(), report->AcceptedImageFps(),
        BbSettings::FrameGenName(settings.frame_gen.load()),
        BbSettings::FrameGenName(status.active_frame_gen.load(std::memory_order_relaxed)),
        status.active_frame_gen_multiplier.load(std::memory_order_relaxed),
        swapchain.GetHDR() ? "on" : "off", inactive ? inactive : "none",
        fallback ? fallback : "none");
    if (length > 0) {
        std::fwrite(text, 1, std::min(size_t(length), sizeof(text) - 1), stdout);
    }
    if (FrameHandoff::Enabled()) {
        const auto h = handoff_timings.Take();
        using Stages = FrameHandoffTimings;
        char timing_text[768];
        const int n = std::snprintf(timing_text, sizeof(timing_text),
            "Frame handoff CPU: %llu frames, avg/max ms: work-to-ready %.2f/%.2f (%llu marked), "
            "ready-to-queue %.2f/%.2f, VideoOut queue %.2f/%.2f, VideoOut dispatch %.2f/%.2f, "
            "swap queue/dispatch %.2f/%.2f, ready-to-present-start %.2f/%.2f; %llu invalid samples\n",
            (unsigned long long)h.samples, h.Mean(Stages::Work), h.maximum[Stages::Work],
            (unsigned long long)h.work_samples, h.Mean(Stages::Publish), h.maximum[Stages::Publish],
            h.Mean(Stages::VideoOut), h.maximum[Stages::VideoOut],
            h.Mean(Stages::Dispatch), h.maximum[Stages::Dispatch],
            h.Mean(Stages::Swap), h.maximum[Stages::Swap],
            h.Mean(Stages::ReadyToPresent), h.maximum[Stages::ReadyToPresent],
            (unsigned long long)h.invalid);
        if (n > 0) {
            std::fwrite(timing_text, 1, std::min(size_t(n), sizeof(timing_text) - 1), stdout);
        }
    }
}

void Presenter::UpdateFrameGenLimit(bool wanted, double present_ms, double paced_ms) {
    auto& settings = BbSettings::Get();
    settings.game_fps = float(1000.0 / game_frame_ms.load(std::memory_order_relaxed));
    if (!wanted) {
        frame_gen_limit = 0;
        frame_generator->SetActive(false);
        settings.frame_gen_now = 0;
        settings.frame_gen_flip_limit = 0;
        present_busy = 0.0;
        frame_gen_backlog_cap = FrameGenerator::MaxGenerated;
        return;
    }
    const double interval = game_frame_ms.load(std::memory_order_relaxed);
    const u32 hz = BbDisplayRefreshHz();
    const auto now = std::chrono::steady_clock::now();
    const u32 before = frame_gen_limit.load(std::memory_order_relaxed);
    u32 limit = before;
    // The images the display shows per game frame: 60 FPS on 144 Hz has room for one generated
    // frame, on 240 Hz for three. Decided once a second from that second's game frame rate
    // (single slow frames while an area loads do not count): down at once when 10% short, up
    // after two seconds with 5% to spare.
    ++limit_frames;
    const double window_s = std::chrono::duration<double>(now - limit_window).count();
    if (window_s >= 1.0) {
        const double ratio = hz * window_s / limit_frames;
        display_ratio = ratio;
        limit_window = now;
        limit_frames = 0;
        if (window_s < 2.0) { // not the first, nor after a pause of the game
            if (limit > 0 && ratio < (limit + 1) * 0.9) {
                while (limit > 0 && ratio < (limit + 1) * 0.9) {
                    --limit;
                }
                limit_up_seconds = 0;
            } else if (limit < FrameGenerator::MaxGenerated && ratio >= (limit + 2) * 0.95) {
                if (++limit_up_seconds >= 2) {
                    ++limit;
                    limit_up_seconds = 0;
                }
            } else {
                limit_up_seconds = 0;
            }
        }
    }
    const bool fifo = swapchain.WaitsForDisplay();
    if (!settings.frame_gen_fit_display || fifo) {
        // The multiplier as chosen, past the display's refresh rate with an uncapped game (the
        // display shows the newest image at each refresh); with FIFO the game is capped below
        // instead. The backlog cap below still applies.
        limit = FrameGenerator::MaxGenerated;
    }
    // The share of the game's frame interval the swap thread spends presenting, without the
    // sleep that spaces the images. Near one, presenting holds the game back (a GPU too slow
    // for generation, a display that blocks): one generated frame fewer, for at least two
    // seconds, then one more again once the display has room for it at the game's frame rate
    // (an uncapped game above half the refresh rate stays without, instead of trying every two
    // seconds). Each frame counts at most 1.2, so one hitch (a load, a shader compile) is not
    // enough; about ten overloaded frames in a row are. With FIFO each image waits for a refresh
    // by design (the game is capped instead).
    if (!fifo) {
        const double work_ms = std::max(present_ms - paced_ms, 0.0);
        present_busy += (std::min(work_ms / interval, 1.2) - present_busy) * 0.1;
        const u32 effective =
            std::min({limit, frame_gen_backlog_cap, frame_generator->WantedCount()});
        if (effective > 0 && present_busy > 0.9) {
            frame_gen_backlog_cap = effective - 1;
            frame_gen_backlog_until = now + std::chrono::seconds(2);
            std::printf("Frame generation: %u generated per game frame for now, presenting takes "
                        "%.1f of %.1f ms per game frame\n",
                        frame_gen_backlog_cap, work_ms, interval);
            present_busy = 0.0;
        } else if (frame_gen_backlog_cap < FrameGenerator::MaxGenerated &&
                   now >= frame_gen_backlog_until && present_busy < 0.6 &&
                   display_ratio >= (frame_gen_backlog_cap + 2) * 0.95) {
            ++frame_gen_backlog_cap;
            frame_gen_backlog_until = now + std::chrono::seconds(2);
        }
    }
    limit = std::min(limit, frame_gen_backlog_cap);
    if (limit != before && settings.frame_gen_fit_display) {
        std::printf("Frame generation: %u generated per game frame (display %u Hz, game %.0f "
                    "FPS)\n",
                    limit, hz, 1000.0 / interval);
    }
    // FIFO (V-Sync; AMD's Windows driver has no Mailbox) shows at most `hz` images a second
    // and makes each one more wait for the display: the game is capped so that its frames and
    // the generated ones fit, e.g. 72 FPS for 2x on 144 Hz (VideoOut applies it).
    int flip_limit = 0;
    if (fifo && limit) {
        const u32 count = std::min(frame_generator->WantedCount(), limit);
        flip_limit = count ? int(hz / (count + 1)) : 0;
    }
    if (flip_limit != settings.frame_gen_flip_limit.exchange(flip_limit) && flip_limit) {
        std::printf("Frame generation: V-Sync (FIFO) at %u Hz: the game is capped at %d FPS so "
                    "its frames and the generated ones fit\n",
                    hz, flip_limit);
    }
    frame_gen_limit = limit;
    // No generated frames: none of their inputs are captured either (vk_temporal_upscaler.cpp).
    frame_generator->SetActive(limit > 0);
    settings.frame_gen_now = int(limit);
    settings.frame_gen_display_hz = int(hz);
}

bool Presenter::PresentImage(Frame* frame, vk::Image image, bool last, u64 reflex_id) {
    // BB_FPS_LOG: adds the time since the previous lap to one part of swap_timing.
    const bool timing = FpsLog();
    auto lap_start =
        timing ? std::chrono::steady_clock::now() : std::chrono::steady_clock::time_point{};
    const auto image_start = lap_start;
    double overlay_ms = 0.0;
    bool scratch_resized = false;
    const auto lap = [&](double& part) {
        if (timing) {
            const auto now = std::chrono::steady_clock::now();
            const double elapsed = std::chrono::duration<double, std::milli>(now - lap_start).count();
            part += elapsed;
            lap_start = now;
            return elapsed;
        }
        return 0.0;
    };
    double acquire_ms = 0.0, record_ms = 0.0, submit_ms = 0.0, lock_ms = 0.0, present_ms = 0.0;
    if (!swapchain.AcquireNextImage()) {
        swapchain.Recreate(window.GetWidth(), window.GetHeight());
        if (!swapchain.AcquireNextImage()) {
            // User resizes the window too fast and GPU can't keep up. Skip this frame.
            LOG_WARNING(Render_Vulkan, "Skipping frame!");
            ++presentation_counts.failed_presents;
            return false;
        }
    }
    acquire_ms = lap(swap_timing.acquire);

    // Reset fence for queue submission. Do it here instead of GetRenderFrame() because we may
    // skip frame because of slow swapchain recreation. If a frame skip occurs, we skip signal
    // the frame's present fence and future GetRenderFrame() call will hang waiting for this frame.
    if (last) {
        const auto reset_result = instance.GetDevice().resetFences(frame->present_done);
        ASSERT_MSG(reset_result == vk::Result::eSuccess,
                   "Unexpected error resetting present done fence: {}",
                   vk::to_string(reset_result));
    }

    // Compose the overlay in SDR before HDR encoding. The scratch attachment uses the same
    // format as BbOverlay's pipeline, including on BGRA-only SDR surfaces. Every generated
    // and rendered image goes through this identical final conversion.
    const vk::Image swapchain_image = swapchain.Image();
    auto& scheduler = present_scheduler;
    const bool hdr = swapchain.GetHDR();
    const bool sdr_on_hdr =
        !hdr && window.IsOnHdrDisplay() && EmulatorSettings.IsHdrGammaEnabled();
    bool convert_output = hdr || sdr_on_hdr;
    const int output_mode = hdr ? 2 : sdr_on_hdr ? 1 : 0;
    if (output_mode != last_output_color_mode) {
        std::printf("Presentation color: %s; rendered/generated/HUD inputs remain SDR\n",
                    hdr ? "HDR10 PQ (10-bit), final conversion after frame generation and overlay"
                        : sdr_on_hdr ? "SDR with Windows HDR compensation" : "SDR");
        last_output_color_mode = output_mode;
    }
    const vk::Extent2D output_extent = swapchain.GetExtent();
    // A 0x0 extent never gets a scratch image (RecreateFrame skips it): no Finish() for it.
    if (convert_output && output_extent.width != 0 && output_extent.height != 0 &&
        (!color_conversion_frame.image ||
                           color_conversion_frame.width != output_extent.width ||
                           color_conversion_frame.height != output_extent.height)) {
        // After failed allocations, not every frame (frame_recreate.h).
        if (scratch_recreate_policy.ShouldRetry()) {
            scratch_resized = true;
            // Scratch is only read/written on this queue; finish its previous uses before resize.
            scheduler.Finish();
            RecreateFrame(&color_conversion_frame, output_extent.width, output_extent.height,
                          scratch_recreate_policy, scheduler, swapchain.GetSurfaceFormat().format,
                          true);
        }
        if (!color_conversion_frame.image || color_conversion_frame.width != output_extent.width ||
            color_conversion_frame.height != output_extent.height) {
            // No scratch image of the swapchain's size: this image is composed straight into
            // the swapchain without the HDR / SDR-on-HDR encode (its colors are off until the
            // scratch is made) instead of the presenter stopping; tried again after a back-off.
            convert_output = false;
        }
    }
    const vk::Image composition_image =
        convert_output ? color_conversion_frame.image : swapchain_image;
    const vk::ImageView composition_view =
        convert_output ? color_conversion_frame.image_view : swapchain.ImageView();
    const auto cmdbuf = scheduler.CommandBuffer();

    if (EmulatorSettings.IsVkHostMarkersEnabled()) {
        cmdbuf.beginDebugUtilsLabelEXT(vk::DebugUtilsLabelEXT{
            .pLabelName = "Present",
        });
    }

    {
        const vk::Extent2D extent = swapchain.GetExtent();
        SetExpectedGameSize(s32(extent.width), s32(extent.height));
        const vk::ImageSubresourceRange color_range{
            .aspectMask = vk::ImageAspectFlagBits::eColor,
            .baseMipLevel = 0,
            .levelCount = 1,
            .baseArrayLayer = 0,
            .layerCount = VK_REMAINING_ARRAY_LAYERS,
        };
        const std::array pre_barriers{
            vk::ImageMemoryBarrier{
                .srcAccessMask = vk::AccessFlagBits::eShaderRead,
                .dstAccessMask = vk::AccessFlagBits::eTransferWrite,
                .oldLayout = vk::ImageLayout::eUndefined,
                .newLayout = vk::ImageLayout::eTransferDstOptimal,
                .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .image = composition_image,
                .subresourceRange = color_range,
            },
            vk::ImageMemoryBarrier{
                .srcAccessMask =
                    vk::AccessFlagBits::eColorAttachmentWrite | vk::AccessFlagBits::eShaderWrite,
                .dstAccessMask = vk::AccessFlagBits::eTransferRead,
                .oldLayout = vk::ImageLayout::eGeneral,
                .newLayout = vk::ImageLayout::eTransferSrcOptimal,
                .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .image = image,
                .subresourceRange = color_range,
            },
        };
        cmdbuf.pipelineBarrier(vk::PipelineStageFlagBits::eAllCommands,
                               vk::PipelineStageFlagBits::eTransfer, vk::DependencyFlagBits::eByRegion,
                               {}, {}, pre_barriers);
        const vk::ClearColorValue black{std::array<float, 4>{0.0f, 0.0f, 0.0f, 1.0f}};
        cmdbuf.clearColorImage(composition_image, vk::ImageLayout::eTransferDstOptimal, black, color_range);
        const vk::MemoryBarrier clear_done{
            .srcAccessMask = vk::AccessFlagBits::eTransferWrite,
            .dstAccessMask = vk::AccessFlagBits::eTransferWrite,
        };
        cmdbuf.pipelineBarrier(vk::PipelineStageFlagBits::eTransfer, vk::PipelineStageFlagBits::eTransfer,
                               vk::DependencyFlagBits::eByRegion, clear_done, {}, {});
        cmdbuf.blitImage(image, vk::ImageLayout::eTransferSrcOptimal, composition_image,
                         vk::ImageLayout::eTransferDstOptimal,
                         MakeImageBlitFit(frame->width, frame->height, extent.width, extent.height),
                         vk::Filter::eLinear);
        // bbport: the settings menu / FPS counter over the frame, at display resolution.
        BbOverlay::NotePresent();
        const bool overlay = BbOverlay::Visible();
        if (!overlay) {
            BbOverlay::PollTests();
        }
        const std::array post_barriers{
            vk::ImageMemoryBarrier{
                .srcAccessMask = vk::AccessFlagBits::eTransferWrite,
                .dstAccessMask = overlay ? vk::AccessFlagBits::eColorAttachmentRead |
                                               vk::AccessFlagBits::eColorAttachmentWrite
                                          : convert_output ? vk::AccessFlagBits::eShaderRead
                                                           : vk::AccessFlagBits::eNone,
                .oldLayout = vk::ImageLayout::eTransferDstOptimal,
                .newLayout = overlay ? vk::ImageLayout::eColorAttachmentOptimal
                                     : convert_output ? vk::ImageLayout::eShaderReadOnlyOptimal
                                                      : vk::ImageLayout::ePresentSrcKHR,
                .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .image = composition_image,
                .subresourceRange = color_range,
            },
            vk::ImageMemoryBarrier{
                .srcAccessMask = vk::AccessFlagBits::eTransferRead,
                .dstAccessMask = vk::AccessFlagBits::eColorAttachmentWrite,
                .oldLayout = vk::ImageLayout::eTransferSrcOptimal,
                .newLayout = vk::ImageLayout::eGeneral,
                .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .image = image,
                .subresourceRange = color_range,
            },
        };
        cmdbuf.pipelineBarrier(vk::PipelineStageFlagBits::eTransfer,
                               vk::PipelineStageFlagBits::eAllCommands,
                               vk::DependencyFlagBits::eByRegion, {}, {}, post_barriers);
        if (overlay) {
            const auto overlay_start = timing ? std::chrono::steady_clock::now()
                                              : std::chrono::steady_clock::time_point{};
            BbOverlay::Render(cmdbuf, composition_view, extent);
            if (timing) {
                overlay_ms = std::chrono::duration<double, std::milli>(
                    std::chrono::steady_clock::now() - overlay_start).count();
            }
            const vk::ImageMemoryBarrier to_present{
                .srcAccessMask = vk::AccessFlagBits::eColorAttachmentWrite,
                .dstAccessMask = convert_output ? vk::AccessFlagBits::eShaderRead : vk::AccessFlagBits::eNone,
                .oldLayout = vk::ImageLayout::eColorAttachmentOptimal,
                .newLayout = convert_output ? vk::ImageLayout::eShaderReadOnlyOptimal
                                           : vk::ImageLayout::ePresentSrcKHR,
                .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .image = composition_image,
                .subresourceRange = color_range,
            };
            cmdbuf.pipelineBarrier(vk::PipelineStageFlagBits::eColorAttachmentOutput,
                                   vk::PipelineStageFlagBits::eAllCommands,
                                   vk::DependencyFlagBits::eByRegion, {}, {}, to_present);
        }
        if (convert_output) {
            const vk::ImageMemoryBarrier to_target{
                .dstAccessMask = vk::AccessFlagBits::eColorAttachmentWrite,
                .oldLayout = vk::ImageLayout::eUndefined,
                .newLayout = vk::ImageLayout::eColorAttachmentOptimal,
                .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .image = swapchain_image,
                .subresourceRange = color_range,
            };
            cmdbuf.pipelineBarrier(vk::PipelineStageFlagBits::eAllCommands,
                                   vk::PipelineStageFlagBits::eColorAttachmentOutput,
                                   vk::DependencyFlagBits::eByRegion, {}, {}, to_target);
            Frame target{};
            target.width = extent.width;
            target.height = extent.height;
            target.image = swapchain_image;
            target.image_view = swapchain.ImageView();
            const auto& bb = BbSettings::Get();
            const auto levels = BbSettings::ResolveHdrLevels(
                bb.hdr_white_nits.load(std::memory_order_relaxed),
                bb.hdr_peak_nits.load(std::memory_order_relaxed),
                bb.hdr_highlight_boost.load(std::memory_order_relaxed), window.SdrWhiteNits(),
                window.PeakNits());
            const HostPasses::PostProcessingPass::Settings output_settings{
                .gamma = 1.0f, .hdr = hdr ? 1u : 0u, .srgb_input = 1,
                .sdr_on_hdr = sdr_on_hdr ? 1u : 0u,
                .white_nits = levels.white_nits, .peak_nits = levels.peak_nits,
                .boost = levels.boost,
            };
            auto& pass = hdr ? hdr_present_pass : sdr_present_pass;
            pass.Render(cmdbuf, composition_view, extent, target, output_settings);
            const vk::ImageMemoryBarrier to_present{
                .srcAccessMask = vk::AccessFlagBits::eColorAttachmentWrite,
                .oldLayout = vk::ImageLayout::eGeneral,
                .newLayout = vk::ImageLayout::ePresentSrcKHR,
                .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                .image = swapchain_image,
                .subresourceRange = color_range,
            };
            cmdbuf.pipelineBarrier(vk::PipelineStageFlagBits::eAllCommands,
                                   vk::PipelineStageFlagBits::eBottomOfPipe,
                                   vk::DependencyFlagBits::eByRegion, {}, {}, to_present);
        }
    }
    if (EmulatorSettings.IsVkHostMarkersEnabled()) {
        cmdbuf.endDebugUtilsLabelEXT();
    }

    // Flush vulkan commands.

    SubmitInfo info{};
    info.AddWait(swapchain.GetImageAcquiredSemaphore());
    info.AddWait(frame->ready_semaphore, frame->ready_tick);
    info.AddSignal(swapchain.GetPresentReadySemaphore());
    if (last) {
        // Also covers the generated frames' submissions before it on this queue.
        info.AddSignal(frame->present_done);
    }
    record_ms = lap(swap_timing.record);
    scheduler.Flush(info);
    submit_ms = lap(swap_timing.submit);

    // Present to swapchain.
    bool presented = false;
    {
        std::scoped_lock submit_lock{Scheduler::submit_mutex};
        lock_ms = lap(swap_timing.lock);
        Reflex::Get().OnPresentStart(reflex_id);
        presented = swapchain.Present(reflex_id);
        present_ms = lap(swap_timing.present);
        Reflex::Get().OnPresentEnd(reflex_id);
        if (!presented && window.GetWidth() != 0 && window.GetHeight() != 0) {
            swapchain.Recreate(window.GetWidth(), window.GetHeight());
        }
    }
    if (presented) {
        ++presentation_counts.accepted_images;
        static std::chrono::steady_clock::time_point last_present;
        BbFrameTimes::Interval('p', last_present);
    } else {
        ++presentation_counts.failed_presents;
    }
    if (timing) {
        const auto now = std::chrono::steady_clock::now();
        const double total_ms = std::chrono::duration<double, std::milli>(now - image_start).count();
        if (total_ms >= 50.0) {
            // One bounded write, only on slow images. Stage times belong to this
            // image (overlay is a subset of record), unlike five-second maxima.
            char line[640];
            const int length = std::snprintf(line, sizeof(line),
                "Present hitch CPU: t=%lld ms, reflex=%llu, last=%u, HDR=%u, scratch-resized=%u, "
                "accepted=%u; total %.2f ms, acquire %.2f, record %.2f (overlay %.2f), "
                "submit %.2f, submit-lock %.2f, present %.2f\n",
                (long long)std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count(),
                (unsigned long long)reflex_id, unsigned(last), unsigned(hdr), unsigned(scratch_resized),
                unsigned(presented), total_ms, acquire_ms, record_ms, overlay_ms,
                submit_ms, lock_ms, present_ms);
            if (length > 0) {
                std::fwrite(line, 1, std::min(size_t(length), sizeof(line) - 1), stdout);
            }
        }
    }
    return presented;
}

Frame* Presenter::GetRenderFrame(bool present_thread) {
    // Wait for free presentation frames
    Frame* frame;
    {
        std::unique_lock lock{free_mutex};
        free_cv.wait(lock, [this] { return !free_queue.empty(); });
        LOG_DEBUG(Render_Vulkan, "Got render frame, remaining {}", free_queue.size() - 1);

        // Take the frame from the queue
        frame = free_queue.front();
        free_queue.pop();
    }

    const vk::Device device = instance.GetDevice();
    vk::Result result{};

    const auto wait = [&]() {
        result = device.waitForFences(frame->present_done, false, std::numeric_limits<u64>::max());
        return result;
    };

    // Wait for the presentation to be finished so all frame resources are free
    while (wait() != vk::Result::eSuccess) {
        if (result == vk::Result::eErrorDeviceLost) {
            instance.DeviceLost("waiting for a frame");
        }
        // Retry if the waiting times out
        if (result == vk::Result::eTimeout) {
            continue;
        }
    }

    // bbport: each thread its own policy and scheduler (RecreateFrame). While backing off after
    // failed allocations the frame keeps its old image; a frame without one always tries.
    auto& policy = present_thread ? blank_recreate_policy : frame_recreate_policy;
    auto& scheduler = present_thread ? present_scheduler : draw_scheduler;
    const u32 width = expected_frame_width, height = expected_frame_height;
    if ((frame->width != width || frame->height != height) &&
        (!frame->image || policy.ShouldRetry())) {
        RecreateFrame(frame, width, height, policy, scheduler);
    }
    frame->kept_old_size = frame->width != width || frame->height != height;

    return frame;
}

void Presenter::SetExpectedGameSize(s32 width, s32 height) {
    if (width <= 0 || height <= 0) {
        return; // no surface (minimized window): keep the last frame size
    }
    const float ratio = (float)width / (float)height;

    expected_frame_height = height;
    expected_frame_width = width;
    if (ratio > expected_ratio) {
        expected_frame_width = static_cast<s32>(height * expected_ratio);
    } else {
        expected_frame_height = static_cast<s32>(width / expected_ratio);
    }
}

} // namespace Vulkan
