// SPDX-License-Identifier: GPL-2.0-or-later
#include "video_core/renderer_vulkan/vk_native_hdr.h"

#include <array>
#include <cstdio>
#include <mutex>
#include <unordered_map>
#include <vector>

#include "bbport_settings.h"
#include "video_core/host_shaders/native_hdr_alpha_comp.h"
#include "video_core/host_shaders/native_hdr_generated_comp.h"
#include "video_core/host_shaders/native_hdr_stamp_comp.h"
#include "video_core/renderer_vulkan/native_hdr_gain.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_platform.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/renderer_vulkan/vk_shader_util.h"

namespace Vulkan {

namespace {

constexpr vk::Format GainFormat = vk::Format::eR16Sfloat;

struct Stored {
    u64 pgm_hash = 0;
    std::vector<u32> spv;
    vk::ShaderModule gain{};
    bool tried = false;
};
std::mutex stored_mutex;
std::unordered_map<VkShaderModule, Stored> stored;

} // namespace

bool NativeHdr::Wanted() {
    const auto& s = BbSettings::Get();
    const bool on = s.hdr_native.load(std::memory_order_relaxed);
    if (!on || !s.hdr.load(std::memory_order_relaxed)) {
        return false;
    }
    static bool told = false;
    if (!told) {
        told = true;
        std::printf("Native HDR: on\n");
    }
    return true;
}

void NativeHdr::Remember(vk::ShaderModule module, u64 pgm_hash, std::span<const u32> spv) {
    // Kept with the setting off as well: the overlay can turn native HDR on while playing.
    if (!NativeHdrGain::IsToneMapper(pgm_hash)) {
        return;
    }
    std::scoped_lock lock{stored_mutex};
    auto& entry = stored[VkShaderModule(module)];
    entry.pgm_hash = pgm_hash;
    entry.spv.assign(spv.begin(), spv.end());
}

vk::ShaderModule NativeHdr::GainModule(vk::Device device, vk::ShaderModule module) {
    std::scoped_lock lock{stored_mutex};
    const auto it = stored.find(VkShaderModule(module));
    if (it == stored.end()) {
        return {};
    }
    auto& entry = it->second;
    if (!entry.tried) {
        entry.tried = true;
        const auto gain = NativeHdrGain::AddGainOutput(entry.spv);
        if (!gain.empty()) {
            entry.gain = CompileSPV(gain, device);
        }
        std::printf("Native HDR: tone mapper %016llx %s\n",
                    static_cast<unsigned long long>(entry.pgm_hash),
                    entry.gain ? "writes the gain" : "has an unknown form: no gain");
        entry.spv.clear();
        entry.spv.shrink_to_fit();
    }
    return entry.gain;
}

NativeHdr::NativeHdr(const Instance& instance_, Scheduler& scheduler_)
    : instance{instance_}, scheduler{scheduler_} {}

NativeHdr::~NativeHdr() = default;

void NativeHdr::EnsureImage(u32 width, u32 height) {
    if (image && image_width == width && image_height == height) {
        return;
    }
    scheduler.Finish();
    view.reset();
    image = VideoCore::UniqueImage(instance.GetDevice(), instance.GetAllocator());
    image.Create(vk::ImageCreateInfo{
        .imageType = vk::ImageType::e2D,
        .format = GainFormat,
        .extent = {width, height, 1},
        .mipLevels = 1,
        .arrayLayers = 1,
        .samples = vk::SampleCountFlagBits::e1,
        .tiling = vk::ImageTiling::eOptimal,
        .usage = vk::ImageUsageFlagBits::eColorAttachment | vk::ImageUsageFlagBits::eSampled,
        .initialLayout = vk::ImageLayout::eUndefined,
    });
    view = Check(instance.GetDevice().createImageViewUnique({
        .image = vk::Image(image),
        .viewType = vk::ImageViewType::e2D,
        .format = GainFormat,
        .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
    }));
    image_width = width;
    image_height = height;
    layout = vk::ImageLayout::eUndefined;
    written = false;
}

void NativeHdr::Attach(RenderState& state) {
    constexpr u32 slot = NativeHdrGain::Attachment;
    EnsureImage(state.width, state.height);
    if (layout != vk::ImageLayout::eColorAttachmentOptimal) {
        scheduler.EndRendering();
        const vk::ImageMemoryBarrier2 barrier{
            .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
            .srcAccessMask = vk::AccessFlagBits2::eMemoryRead,
            .dstStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
            .dstAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite,
            .oldLayout = vk::ImageLayout::eUndefined, // the whole picture is written again
            .newLayout = vk::ImageLayout::eColorAttachmentOptimal,
            .image = vk::Image(image),
            .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
        };
        scheduler.Record([barrier](vk::CommandBuffer cmd) {
            cmd.pipelineBarrier2({.imageMemoryBarrierCount = 1, .pImageMemoryBarriers = &barrier});
        });
        layout = vk::ImageLayout::eColorAttachmentOptimal;
    }
    auto& attachment = state.color_attachments[slot];
    attachment = {};
    attachment.image_view = *view;
    attachment.image_layout = vk::ImageLayout::eColorAttachmentOptimal;
    state.num_color_attachments = std::max<u16>(state.num_color_attachments, slot + 1);
    written = true;
}

void NativeHdr::EnsurePipeline() {
    if (pipeline) {
        return;
    }
    const auto device = instance.GetDevice();
    sampler = Check(device.createSamplerUnique({
        .magFilter = vk::Filter::eLinear,
        .minFilter = vk::Filter::eLinear,
        .addressModeU = vk::SamplerAddressMode::eClampToEdge,
        .addressModeV = vk::SamplerAddressMode::eClampToEdge,
        .addressModeW = vk::SamplerAddressMode::eClampToEdge,
    }));
    const std::array bindings{
        vk::DescriptorSetLayoutBinding{.binding = 0,
                                       .descriptorType = vk::DescriptorType::eCombinedImageSampler,
                                       .descriptorCount = 1,
                                       .stageFlags = vk::ShaderStageFlagBits::eCompute},
        vk::DescriptorSetLayoutBinding{.binding = 1,
                                       .descriptorType = vk::DescriptorType::eStorageImage,
                                       .descriptorCount = 1,
                                       .stageFlags = vk::ShaderStageFlagBits::eCompute},
        vk::DescriptorSetLayoutBinding{.binding = 2,
                                       .descriptorType = vk::DescriptorType::eStorageImage,
                                       .descriptorCount = 1,
                                       .stageFlags = vk::ShaderStageFlagBits::eCompute},
    };
    set_layout = Check(device.createDescriptorSetLayoutUnique({
        .flags = vk::DescriptorSetLayoutCreateFlagBits::ePushDescriptorKHR,
        .bindingCount = u32(bindings.size()),
        .pBindings = bindings.data(),
    }));
    const vk::PushConstantRange range{.stageFlags = vk::ShaderStageFlagBits::eCompute,
                                      .size = 4 * sizeof(float)};
    pipeline_layout = Check(device.createPipelineLayoutUnique({
        .setLayoutCount = 1,
        .pSetLayouts = &*set_layout,
        .pushConstantRangeCount = 1,
        .pPushConstantRanges = &range,
    }));
    const auto module = CompileSPV(NATIVE_HDR_STAMP_COMP, device);
    pipeline = Check(device.createComputePipelineUnique(
        {}, vk::ComputePipelineCreateInfo{
                .stage = {.stage = vk::ShaderStageFlagBits::eCompute,
                          .module = module,
                          .pName = "main"},
                .layout = *pipeline_layout,
            }));
    device.destroyShaderModule(module);
}

void NativeHdr::EnsureSnapshot(u32 width, u32 height) {
    if (snapshot && snapshot_width == width && snapshot_height == height) {
        return;
    }
    scheduler.Finish();
    snapshot_view.reset();
    snapshot = VideoCore::UniqueImage(instance.GetDevice(), instance.GetAllocator());
    snapshot.Create(vk::ImageCreateInfo{
        .imageType = vk::ImageType::e2D,
        .format = vk::Format::eR8G8B8A8Unorm,
        .extent = {width, height, 1},
        .mipLevels = 1,
        .arrayLayers = 1,
        .samples = vk::SampleCountFlagBits::e1,
        .tiling = vk::ImageTiling::eOptimal,
        .usage = vk::ImageUsageFlagBits::eTransferDst | vk::ImageUsageFlagBits::eStorage,
        .initialLayout = vk::ImageLayout::eUndefined,
    });
    snapshot_view = Check(instance.GetDevice().createImageViewUnique({
        .image = vk::Image(snapshot),
        .viewType = vk::ImageViewType::e2D,
        .format = vk::Format::eR8G8B8A8Unorm,
        .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
    }));
    snapshot_width = width;
    snapshot_height = height;
}

void NativeHdr::Snapshot(vk::CommandBuffer cmdbuf, vk::Image frame, u32 scene_width,
                         u32 scene_height) {
    snapshot_taken = false;
    if (!written || !snapshot) {
        return;
    }
    const vk::ImageMemoryBarrier2 to_copy{
        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask = vk::AccessFlagBits2::eNone,
        .dstStageMask = vk::PipelineStageFlagBits2::eCopy,
        .dstAccessMask = vk::AccessFlagBits2::eTransferWrite,
        .oldLayout = vk::ImageLayout::eUndefined,
        .newLayout = vk::ImageLayout::eGeneral,
        .image = vk::Image(snapshot),
        .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
    };
    const vk::MemoryBarrier2 source{
        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask = vk::AccessFlagBits2::eMemoryWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eCopy,
        .dstAccessMask = vk::AccessFlagBits2::eTransferRead,
    };
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1,
                             .pMemoryBarriers = &source,
                             .imageMemoryBarrierCount = 1,
                             .pImageMemoryBarriers = &to_copy});
    const vk::ImageCopy region{
        .srcSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
        .dstSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
        .extent = {snapshot_width, snapshot_height, 1},
    };
    cmdbuf.copyImage(frame, vk::ImageLayout::eGeneral, vk::Image(snapshot),
                     vk::ImageLayout::eGeneral, region);
    const vk::MemoryBarrier2 copied{
        .srcStageMask = vk::PipelineStageFlagBits2::eCopy,
        .srcAccessMask = vk::AccessFlagBits2::eTransferWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .dstAccessMask = vk::AccessFlagBits2::eMemoryRead,
    };
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &copied});
    snapshot_taken = true;
    scene_w = scene_width;
    scene_h = scene_height;
}

bool NativeHdr::Stamp(vk::ImageView frame) {
    const bool ready = written && snapshot_taken && image && snapshot;
    written = false;
    snapshot_taken = false;
    if (!ready) {
        return false;
    }
    EnsurePipeline();
    layout = vk::ImageLayout::eShaderReadOnlyOptimal;
    // The scene fills the top-left of the game's targets.
    const std::array<float, 4> push{float(scene_w) / float(image_width),
                                    float(scene_h) / float(image_height),
                                    1.0f / float(snapshot_width), 1.0f / float(snapshot_height)};
    scheduler.Record([frame, push, gain_image = vk::Image(image), gain_view = *view,
                      before = *snapshot_view, sampler = *sampler, layout = *pipeline_layout,
                      pipeline = *pipeline, width = snapshot_width,
                      height = snapshot_height](vk::CommandBuffer cmdbuf) {
        const vk::ImageMemoryBarrier2 to_read{
            .srcStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
            .srcAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite,
            .dstStageMask = vk::PipelineStageFlagBits2::eComputeShader,
            .dstAccessMask = vk::AccessFlagBits2::eShaderRead,
            .oldLayout = vk::ImageLayout::eColorAttachmentOptimal,
            .newLayout = vk::ImageLayout::eShaderReadOnlyOptimal,
            .image = gain_image,
            .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
        };
        const vk::MemoryBarrier2 ui_done{
            .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
            .srcAccessMask = vk::AccessFlagBits2::eMemoryWrite,
            .dstStageMask = vk::PipelineStageFlagBits2::eComputeShader,
            .dstAccessMask = vk::AccessFlagBits2::eShaderRead | vk::AccessFlagBits2::eShaderWrite,
        };
        cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1,
                                 .pMemoryBarriers = &ui_done,
                                 .imageMemoryBarrierCount = 1,
                                 .pImageMemoryBarriers = &to_read});
        const vk::DescriptorImageInfo gain_info{.sampler = sampler,
                                                .imageView = gain_view,
                                                .imageLayout =
                                                    vk::ImageLayout::eShaderReadOnlyOptimal};
        const vk::DescriptorImageInfo frame_info{.imageView = frame,
                                                 .imageLayout = vk::ImageLayout::eGeneral};
        const vk::DescriptorImageInfo before_info{.imageView = before,
                                                  .imageLayout = vk::ImageLayout::eGeneral};
        const std::array writes{
            vk::WriteDescriptorSet{.dstBinding = 0,
                                   .descriptorCount = 1,
                                   .descriptorType = vk::DescriptorType::eCombinedImageSampler,
                                   .pImageInfo = &gain_info},
            vk::WriteDescriptorSet{.dstBinding = 1,
                                   .descriptorCount = 1,
                                   .descriptorType = vk::DescriptorType::eStorageImage,
                                   .pImageInfo = &frame_info},
            vk::WriteDescriptorSet{.dstBinding = 2,
                                   .descriptorCount = 1,
                                   .descriptorType = vk::DescriptorType::eStorageImage,
                                   .pImageInfo = &before_info},
        };
        cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, pipeline);
        cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, layout, 0, writes);
        cmdbuf.pushConstants(layout, vk::ShaderStageFlagBits::eCompute, 0, sizeof(push),
                             push.data());
        cmdbuf.dispatch((width + 7) / 8, (height + 7) / 8, 1);
        const vk::MemoryBarrier2 after{
            .srcStageMask = vk::PipelineStageFlagBits2::eComputeShader,
            .srcAccessMask = vk::AccessFlagBits2::eShaderWrite,
            .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
            .dstAccessMask = vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
        };
        cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &after});
    });
    return true;
}

NativeHdrCarry::NativeHdrCarry(const Instance& instance_) : instance{instance_} {}

NativeHdrCarry::~NativeHdrCarry() = default;

void NativeHdrCarry::CopyAlpha(vk::CommandBuffer cmdbuf, Scheduler& scheduler, vk::Image source,
                               vk::Format source_format, vk::ImageView frame_view, u32 width,
                               u32 height) {
    const auto device = instance.GetDevice();
    if (!alpha_pipeline) {
        alpha_sampler = Check(device.createSamplerUnique({
            .magFilter = vk::Filter::eLinear,
            .minFilter = vk::Filter::eLinear,
            .addressModeU = vk::SamplerAddressMode::eClampToEdge,
            .addressModeV = vk::SamplerAddressMode::eClampToEdge,
            .addressModeW = vk::SamplerAddressMode::eClampToEdge,
        }));
        const std::array bindings{
            vk::DescriptorSetLayoutBinding{
                .binding = 0,
                .descriptorType = vk::DescriptorType::eCombinedImageSampler,
                .descriptorCount = 1,
                .stageFlags = vk::ShaderStageFlagBits::eCompute},
            vk::DescriptorSetLayoutBinding{.binding = 1,
                                           .descriptorType = vk::DescriptorType::eStorageImage,
                                           .descriptorCount = 1,
                                           .stageFlags = vk::ShaderStageFlagBits::eCompute},
        };
        alpha_set_layout = Check(device.createDescriptorSetLayoutUnique({
            .flags = vk::DescriptorSetLayoutCreateFlagBits::ePushDescriptorKHR,
            .bindingCount = u32(bindings.size()),
            .pBindings = bindings.data(),
        }));
        const vk::PushConstantRange range{.stageFlags = vk::ShaderStageFlagBits::eCompute,
                                          .size = 2 * sizeof(float)};
        alpha_pipeline_layout = Check(device.createPipelineLayoutUnique({
            .setLayoutCount = 1,
            .pSetLayouts = &*alpha_set_layout,
            .pushConstantRangeCount = 1,
            .pPushConstantRanges = &range,
        }));
        const auto module = CompileSPV(NATIVE_HDR_ALPHA_COMP, device);
        alpha_pipeline = Check(device.createComputePipelineUnique(
            {}, vk::ComputePipelineCreateInfo{
                    .stage = {.stage = vk::ShaderStageFlagBits::eCompute,
                              .module = module,
                              .pName = "main"},
                    .layout = *alpha_pipeline_layout,
                }));
        device.destroyShaderModule(module);
    }
    // Not the presenter's view of the picture: that one forces alpha to 1.
    const auto source_view = Check(device.createImageView({
        .image = source,
        .viewType = vk::ImageViewType::e2D,
        .format = source_format,
        .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
    }));
    scheduler.DeferOperation([device, source_view] { device.destroyImageView(source_view); });
    const vk::MemoryBarrier2 before{
        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask = vk::AccessFlagBits2::eMemoryWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eComputeShader,
        .dstAccessMask = vk::AccessFlagBits2::eShaderRead | vk::AccessFlagBits2::eShaderWrite,
    };
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &before});
    const vk::DescriptorImageInfo source_info{.sampler = *alpha_sampler,
                                              .imageView = source_view,
                                              .imageLayout =
                                                  vk::ImageLayout::eShaderReadOnlyOptimal};
    const vk::DescriptorImageInfo frame_info{.imageView = frame_view,
                                             .imageLayout = vk::ImageLayout::eGeneral};
    const std::array writes{
        vk::WriteDescriptorSet{.dstBinding = 0,
                               .descriptorCount = 1,
                               .descriptorType = vk::DescriptorType::eCombinedImageSampler,
                               .pImageInfo = &source_info},
        vk::WriteDescriptorSet{.dstBinding = 1,
                               .descriptorCount = 1,
                               .descriptorType = vk::DescriptorType::eStorageImage,
                               .pImageInfo = &frame_info},
    };
    const std::array<float, 2> push{1.0f / float(width), 1.0f / float(height)};
    cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, *alpha_pipeline);
    cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *alpha_pipeline_layout, 0, writes);
    cmdbuf.pushConstants(*alpha_pipeline_layout, vk::ShaderStageFlagBits::eCompute, 0, sizeof(push),
                         push.data());
    cmdbuf.dispatch((width + 7) / 8, (height + 7) / 8, 1);
    const vk::MemoryBarrier2 after{
        .srcStageMask = vk::PipelineStageFlagBits2::eComputeShader,
        .srcAccessMask = vk::AccessFlagBits2::eShaderWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .dstAccessMask = vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
    };
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &after});
}

void NativeHdrCarry::EnsureHistory(Scheduler& scheduler, u32 width, u32 height) {
    if (history && history_width == width && history_height == height) {
        return;
    }
    // A single image: the previous frames' commands may still read the old one.
    scheduler.WaitSubmitted();
    history_view.reset();
    history = VideoCore::UniqueImage(instance.GetDevice(), instance.GetAllocator());
    history.Create(vk::ImageCreateInfo{
        .imageType = vk::ImageType::e2D,
        .format = vk::Format::eR8G8B8A8Unorm,
        .extent = {width, height, 1},
        .mipLevels = 1,
        .arrayLayers = 1,
        .samples = vk::SampleCountFlagBits::e1,
        .tiling = vk::ImageTiling::eOptimal,
        .usage = vk::ImageUsageFlagBits::eTransferDst | vk::ImageUsageFlagBits::eStorage,
        .initialLayout = vk::ImageLayout::eUndefined,
    });
    history_view = Check(instance.GetDevice().createImageViewUnique({
        .image = vk::Image(history),
        .viewType = vk::ImageViewType::e2D,
        .format = vk::Format::eR8G8B8A8Unorm,
        .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
    }));
    history_width = width;
    history_height = height;
    history_stamped = false;
}

void NativeHdrCarry::EnsurePipeline() {
    if (pipeline) {
        return;
    }
    const auto device = instance.GetDevice();
    const std::array bindings{
        vk::DescriptorSetLayoutBinding{.binding = 0,
                                       .descriptorType = vk::DescriptorType::eStorageImage,
                                       .descriptorCount = 1,
                                       .stageFlags = vk::ShaderStageFlagBits::eCompute},
        vk::DescriptorSetLayoutBinding{.binding = 1,
                                       .descriptorType = vk::DescriptorType::eSampledImage,
                                       .descriptorCount = 1,
                                       .stageFlags = vk::ShaderStageFlagBits::eCompute},
        vk::DescriptorSetLayoutBinding{.binding = 2,
                                       .descriptorType = vk::DescriptorType::eStorageImage,
                                       .descriptorCount = 1,
                                       .stageFlags = vk::ShaderStageFlagBits::eCompute},
    };
    set_layout = Check(device.createDescriptorSetLayoutUnique({
        .flags = vk::DescriptorSetLayoutCreateFlagBits::ePushDescriptorKHR,
        .bindingCount = u32(bindings.size()),
        .pBindings = bindings.data(),
    }));
    const vk::PushConstantRange range{.stageFlags = vk::ShaderStageFlagBits::eCompute,
                                      .size = 3 * sizeof(s32)};
    pipeline_layout = Check(device.createPipelineLayoutUnique({
        .setLayoutCount = 1,
        .pSetLayouts = &*set_layout,
        .pushConstantRangeCount = 1,
        .pPushConstantRanges = &range,
    }));
    const auto module = CompileSPV(NATIVE_HDR_GENERATED_COMP, device);
    pipeline = Check(device.createComputePipelineUnique(
        {}, vk::ComputePipelineCreateInfo{
                .stage = {.stage = vk::ShaderStageFlagBits::eCompute,
                          .module = module,
                          .pName = "main"},
                .layout = *pipeline_layout,
            }));
    device.destroyShaderModule(module);
}

void NativeHdrCarry::Run(vk::CommandBuffer cmdbuf, Scheduler& scheduler, vk::Image frame,
                         vk::ImageView frame_view, std::span<const vk::ImageView> generated,
                         u32 width, u32 height, bool stamped) {
    EnsureHistory(scheduler, width, height);
    const vk::MemoryBarrier2 written{
        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask = vk::AccessFlagBits2::eMemoryWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .dstAccessMask = vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
    };
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &written});
    if (stamped && !generated.empty()) {
        EnsurePipeline();
        const std::array<s32, 3> push{s32(width), s32(height), history_stamped ? 1 : 0};
        const vk::DescriptorImageInfo frame_info{.imageView = frame_view,
                                                 .imageLayout = vk::ImageLayout::eGeneral};
        const vk::DescriptorImageInfo before_info{.imageView = *history_view,
                                                  .imageLayout = vk::ImageLayout::eGeneral};
        cmdbuf.bindPipeline(vk::PipelineBindPoint::eCompute, *pipeline);
        cmdbuf.pushConstants(*pipeline_layout, vk::ShaderStageFlagBits::eCompute, 0, sizeof(push),
                             push.data());
        for (const vk::ImageView view : generated) {
            const vk::DescriptorImageInfo output_info{.imageView = view,
                                                      .imageLayout = vk::ImageLayout::eGeneral};
            const std::array writes{
                vk::WriteDescriptorSet{.dstBinding = 0,
                                       .descriptorCount = 1,
                                       .descriptorType = vk::DescriptorType::eStorageImage,
                                       .pImageInfo = &output_info},
                vk::WriteDescriptorSet{.dstBinding = 1,
                                       .descriptorCount = 1,
                                       .descriptorType = vk::DescriptorType::eSampledImage,
                                       .pImageInfo = &frame_info},
                vk::WriteDescriptorSet{.dstBinding = 2,
                                       .descriptorCount = 1,
                                       .descriptorType = vk::DescriptorType::eStorageImage,
                                       .pImageInfo = &before_info},
            };
            cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eCompute, *pipeline_layout, 0,
                                        writes);
            cmdbuf.dispatch((width + 7) / 8, (height + 7) / 8, 1);
        }
        cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &written});
    }
    // This frame is the next generated frames' "before".
    const vk::ImageMemoryBarrier2 to_copy{
        .srcStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .srcAccessMask = vk::AccessFlagBits2::eNone,
        .dstStageMask = vk::PipelineStageFlagBits2::eCopy,
        .dstAccessMask = vk::AccessFlagBits2::eTransferWrite,
        .oldLayout = vk::ImageLayout::eUndefined,
        .newLayout = vk::ImageLayout::eGeneral,
        .image = vk::Image(history),
        .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1},
    };
    cmdbuf.pipelineBarrier2({.imageMemoryBarrierCount = 1, .pImageMemoryBarriers = &to_copy});
    const vk::ImageCopy region{
        .srcSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
        .dstSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
        .extent = {width, height, 1},
    };
    cmdbuf.copyImage(frame, vk::ImageLayout::eGeneral, vk::Image(history),
                     vk::ImageLayout::eGeneral, region);
    cmdbuf.pipelineBarrier2({.memoryBarrierCount = 1, .pMemoryBarriers = &written});
    history_stamped = stamped;
}

} // namespace Vulkan
