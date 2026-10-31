// SPDX-License-Identifier: GPL-2.0-or-later
// Offscreen GPU test of the actual presentation shaders. No window, game or NGX required.
#include <vulkan/vulkan.h>
#include "video_core/host_shaders/fs_tri_vert.h"
#include "video_core/host_shaders/post_process_frag.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr uint32_t Width = 8;
std::atomic<unsigned> validation_errors{0};
VKAPI_ATTR VkBool32 VKAPI_CALL Validation(VkDebugUtilsMessageSeverityFlagBitsEXT severity,
    VkDebugUtilsMessageTypeFlagsEXT, const VkDebugUtilsMessengerCallbackDataEXT* data, void*) {
    if (severity & VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT) {
        ++validation_errors;
        std::fprintf(stderr, "Vulkan validation: %s\n", data->pMessage);
    }
    return VK_FALSE;
}
void Check(VkResult result) {
    if (result != VK_SUCCESS) throw std::runtime_error("Vulkan call failed: " + std::to_string(result));
}
void Require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
struct Image { VkImage image{}; VkDeviceMemory memory{}; VkImageView view{}; };
struct Gpu {
    VkInstance instance{};
    VkDebugUtilsMessengerEXT messenger{};
    VkDevice device{};
    VkPhysicalDevice physical{};
    VkQueue queue{};
    uint32_t family{};
    VkCommandPool pool{};
    VkDescriptorSetLayout set_layout{};
    VkDescriptorPool descriptors{};
    VkPipelineLayout layout{};
    VkSampler sampler{};
    VkBuffer buffer{};
    VkDeviceMemory buffer_memory{};
    std::vector<Image> images;
    std::vector<VkPipeline> pipelines;
    std::vector<VkShaderModule> shaders;
    ~Gpu() {
        if (device) {
            vkDeviceWaitIdle(device);
            for (auto p : pipelines) vkDestroyPipeline(device, p, nullptr);
            for (auto s : shaders) vkDestroyShaderModule(device, s, nullptr);
            if (layout) vkDestroyPipelineLayout(device, layout, nullptr);
            if (sampler) vkDestroySampler(device, sampler, nullptr);
            if (descriptors) vkDestroyDescriptorPool(device, descriptors, nullptr);
            if (set_layout) vkDestroyDescriptorSetLayout(device, set_layout, nullptr);
            for (auto i : images) {
                vkDestroyImageView(device, i.view, nullptr);
                vkDestroyImage(device, i.image, nullptr);
                vkFreeMemory(device, i.memory, nullptr);
            }
            if (buffer) vkDestroyBuffer(device, buffer, nullptr);
            if (buffer_memory) vkFreeMemory(device, buffer_memory, nullptr);
            if (pool) vkDestroyCommandPool(device, pool, nullptr);
            vkDestroyDevice(device, nullptr);
        }
        if (messenger) {
            const auto destroy = reinterpret_cast<PFN_vkDestroyDebugUtilsMessengerEXT>(
                vkGetInstanceProcAddr(instance, "vkDestroyDebugUtilsMessengerEXT"));
            destroy(instance, messenger, nullptr);
        }
        if (instance) vkDestroyInstance(instance, nullptr);
    }
    uint32_t Memory(uint32_t bits, VkMemoryPropertyFlags flags) {
        VkPhysicalDeviceMemoryProperties props{};
        vkGetPhysicalDeviceMemoryProperties(physical, &props);
        for (uint32_t i = 0; i < props.memoryTypeCount; ++i)
            if ((bits & (1u << i)) && (props.memoryTypes[i].propertyFlags & flags) == flags) return i;
        throw std::runtime_error("Required memory type missing");
    }
    Image MakeImage(VkFormat format, VkImageUsageFlags usage) {
        Image image;
        VkImageCreateInfo ci{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
        ci.imageType = VK_IMAGE_TYPE_2D; ci.format = format; ci.extent = {Width, 1, 1};
        ci.mipLevels = ci.arrayLayers = 1; ci.samples = VK_SAMPLE_COUNT_1_BIT; ci.usage = usage;
        Check(vkCreateImage(device, &ci, nullptr, &image.image));
        VkMemoryRequirements req{}; vkGetImageMemoryRequirements(device, image.image, &req);
        VkMemoryAllocateInfo alloc{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
        alloc.allocationSize = req.size; alloc.memoryTypeIndex = Memory(req.memoryTypeBits, 0);
        Check(vkAllocateMemory(device, &alloc, nullptr, &image.memory));
        Check(vkBindImageMemory(device, image.image, image.memory, 0));
        VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
        vi.image = image.image; vi.viewType = VK_IMAGE_VIEW_TYPE_2D; vi.format = format;
        vi.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
        Check(vkCreateImageView(device, &vi, nullptr, &image.view));
        images.push_back(image);
        return image;
    }
    VkShaderModule Shader(const uint32_t* code, size_t size) {
        VkShaderModuleCreateInfo ci{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
        ci.codeSize = size; ci.pCode = code;
        VkShaderModule module{}; Check(vkCreateShaderModule(device, &ci, nullptr, &module));
        shaders.push_back(module); return module;
    }
    VkPipeline Pipeline(VkFormat format) {
        VkPipelineShaderStageCreateInfo stages[2]{};
        stages[0] = {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO};
        stages[0].stage = VK_SHADER_STAGE_VERTEX_BIT; stages[0].pName = "main";
        stages[0].module = Shader(FS_TRI_VERT, sizeof(FS_TRI_VERT));
        stages[1] = {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO};
        stages[1].stage = VK_SHADER_STAGE_FRAGMENT_BIT; stages[1].pName = "main";
        stages[1].module = Shader(POST_PROCESS_FRAG, sizeof(POST_PROCESS_FRAG));
        VkPipelineVertexInputStateCreateInfo vertex{VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
        VkPipelineInputAssemblyStateCreateInfo assembly{VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO};
        assembly.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
        VkViewport viewport{0, 0, float(Width), 1, 0, 1}; VkRect2D scissor{{0, 0}, {Width, 1}};
        VkPipelineViewportStateCreateInfo vp{VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO};
        vp.viewportCount = vp.scissorCount = 1; vp.pViewports = &viewport; vp.pScissors = &scissor;
        VkPipelineRasterizationStateCreateInfo raster{VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO};
        raster.polygonMode = VK_POLYGON_MODE_FILL; raster.lineWidth = 1; raster.cullMode = VK_CULL_MODE_NONE;
        VkPipelineMultisampleStateCreateInfo ms{VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO};
        ms.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;
        VkPipelineColorBlendAttachmentState attachment{}; attachment.colorWriteMask = 15;
        VkPipelineColorBlendStateCreateInfo blend{VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO};
        blend.attachmentCount = 1; blend.pAttachments = &attachment;
        VkPipelineRenderingCreateInfo rendering{VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO};
        rendering.colorAttachmentCount = 1; rendering.pColorAttachmentFormats = &format;
        VkGraphicsPipelineCreateInfo ci{VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO};
        ci.pNext = &rendering; ci.stageCount = 2; ci.pStages = stages;
        ci.pVertexInputState = &vertex; ci.pInputAssemblyState = &assembly; ci.pViewportState = &vp;
        ci.pRasterizationState = &raster; ci.pMultisampleState = &ms; ci.pColorBlendState = &blend;
        ci.layout = layout;
        VkPipeline pipeline{}; Check(vkCreateGraphicsPipelines(device, {}, 1, &ci, nullptr, &pipeline));
        pipelines.push_back(pipeline); return pipeline;
    }
};
void Barrier(VkCommandBuffer cmd, VkImage image, VkImageLayout before, VkImageLayout after,
             VkAccessFlags src, VkAccessFlags dst) {
    VkImageMemoryBarrier b{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
    b.srcAccessMask = src; b.dstAccessMask = dst; b.oldLayout = before; b.newLayout = after;
    b.srcQueueFamilyIndex = b.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    b.image = image; b.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                         0, 0, nullptr, 0, nullptr, 1, &b);
}
double DecodeNits(double pq) { // independent inverse: verify physical output, not shader arithmetic
    const double p = std::pow(pq, 1.0 / 78.84375);
    return 10000 * std::pow(std::max(p - 0.8359375, 0.0) / (18.8515625 - 18.6875 * p), 1.0 / 0.1593017578125);
}
} // namespace

int main() try {
    Gpu g;
    VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO}; app.apiVersion = VK_API_VERSION_1_3;
    VkInstanceCreateInfo ici{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO}; ici.pApplicationInfo = &app;
    uint32_t layer_count{}; Check(vkEnumerateInstanceLayerProperties(&layer_count, nullptr));
    std::vector<VkLayerProperties> layers(layer_count);
    Check(vkEnumerateInstanceLayerProperties(&layer_count, layers.data()));
    const char* layer = "VK_LAYER_KHRONOS_validation";
    const char* debug_extension = VK_EXT_DEBUG_UTILS_EXTENSION_NAME;
    const bool validation = std::any_of(layers.begin(), layers.end(), [&](const auto& l) {
        return std::strcmp(l.layerName, layer) == 0;
    });
    if (validation) {
        ici.enabledLayerCount = ici.enabledExtensionCount = 1;
        ici.ppEnabledLayerNames = &layer; ici.ppEnabledExtensionNames = &debug_extension;
    }
    Check(vkCreateInstance(&ici, nullptr, &g.instance));
    if (validation) {
        const auto create = reinterpret_cast<PFN_vkCreateDebugUtilsMessengerEXT>(
            vkGetInstanceProcAddr(g.instance, "vkCreateDebugUtilsMessengerEXT"));
        VkDebugUtilsMessengerCreateInfoEXT mi{VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT};
        mi.messageSeverity = VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT;
        mi.messageType = VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT |
                         VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT |
                         VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT;
        mi.pfnUserCallback = Validation;
        Check(create(g.instance, &mi, nullptr, &g.messenger));
    }
    std::printf("Validation layer: %s\n", validation ? "enabled" : "not installed");
    uint32_t count{}; Check(vkEnumeratePhysicalDevices(g.instance, &count, nullptr));
    if (!count) { std::puts("SKIP: Vulkan GPU required"); return 77; }
    std::vector<VkPhysicalDevice> devices(count); Check(vkEnumeratePhysicalDevices(g.instance, &count, devices.data()));
    g.physical = devices[0];
    VkPhysicalDeviceProperties gpu_properties{};
    vkGetPhysicalDeviceProperties(g.physical, &gpu_properties);
    std::printf("GPU: %s\n", gpu_properties.deviceName);
    VkPhysicalDeviceVulkan13Features f13{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES};
    VkPhysicalDeviceFeatures2 features{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2}; features.pNext = &f13;
    vkGetPhysicalDeviceFeatures2(g.physical, &features);
    if (!f13.dynamicRendering) { std::puts("SKIP: Vulkan dynamic rendering required"); return 77; }
    uint32_t families{}; vkGetPhysicalDeviceQueueFamilyProperties(g.physical, &families, nullptr);
    std::vector<VkQueueFamilyProperties> props(families); vkGetPhysicalDeviceQueueFamilyProperties(g.physical, &families, props.data());
    for (; g.family < families; ++g.family) if (props[g.family].queueFlags & VK_QUEUE_GRAPHICS_BIT) break;
    Require(g.family < families, "No graphics queue");
    float priority = 1;
    VkDeviceQueueCreateInfo qci{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
    qci.queueFamilyIndex = g.family; qci.queueCount = 1; qci.pQueuePriorities = &priority;
    VkPhysicalDeviceVulkan13Features enabled{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES}; enabled.dynamicRendering = true;
    VkDeviceCreateInfo dci{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO}; dci.pNext = &enabled; dci.queueCreateInfoCount = 1; dci.pQueueCreateInfos = &qci;
    Check(vkCreateDevice(g.physical, &dci, nullptr, &g.device)); vkGetDeviceQueue(g.device, g.family, 0, &g.queue);
    VkCommandPoolCreateInfo pci{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO}; pci.queueFamilyIndex = g.family;
    Check(vkCreateCommandPool(g.device, &pci, nullptr, &g.pool));
    VkDescriptorSetLayoutBinding binding{0, VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1, VK_SHADER_STAGE_FRAGMENT_BIT, nullptr};
    VkDescriptorSetLayoutCreateInfo sl{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO}; sl.bindingCount = 1; sl.pBindings = &binding;
    Check(vkCreateDescriptorSetLayout(g.device, &sl, nullptr, &g.set_layout));
    VkPushConstantRange push{VK_SHADER_STAGE_FRAGMENT_BIT, 0, 28};
    VkPipelineLayoutCreateInfo pl{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO}; pl.setLayoutCount = 1; pl.pSetLayouts = &g.set_layout; pl.pushConstantRangeCount = 1; pl.pPushConstantRanges = &push;
    Check(vkCreatePipelineLayout(g.device, &pl, nullptr, &g.layout));
    VkSamplerCreateInfo sci{VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};
    sci.magFilter = sci.minFilter = VK_FILTER_NEAREST; sci.addressModeU = sci.addressModeV = sci.addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    Check(vkCreateSampler(g.device, &sci, nullptr, &g.sampler));
    const auto input = g.MakeImage(VK_FORMAT_R8G8B8A8_UNORM, VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT);
    const auto input_bgra = g.MakeImage(VK_FORMAT_B8G8R8A8_UNORM, VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT);
    const auto hdr = g.MakeImage(VK_FORMAT_A2B10G10R10_UNORM_PACK32, VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT);
    const auto sdr = g.MakeImage(VK_FORMAT_R8G8B8A8_UNORM, VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT);
    VkBufferCreateInfo bci{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO}; bci.size = 1024; bci.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT;
    Check(vkCreateBuffer(g.device, &bci, nullptr, &g.buffer));
    VkMemoryRequirements req{}; vkGetBufferMemoryRequirements(g.device, g.buffer, &req);
    VkMemoryAllocateInfo alloc{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; alloc.allocationSize = req.size;
    alloc.memoryTypeIndex = g.Memory(req.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    Check(vkAllocateMemory(g.device, &alloc, nullptr, &g.buffer_memory)); Check(vkBindBufferMemory(g.device, g.buffer, g.buffer_memory, 0));
    const std::array<uint32_t, Width> pixels{0xff000000,0xff404040,0xff808080,0xffbfbfbf,0xffffffff,0xff0000ff,0xff00ff00,0xffff0000};
    void* mapped{}; Check(vkMapMemory(g.device, g.buffer_memory, 0, VK_WHOLE_SIZE, 0, &mapped));
    std::memcpy(mapped, pixels.data(), sizeof(pixels)); vkUnmapMemory(g.device, g.buffer_memory);
    std::array<uint32_t, Width> bgra{};
    for (uint32_t i = 0; i < Width; ++i) {
        bgra[i] = (pixels[i] & 0xff00ff00u) | ((pixels[i] & 255u) << 16) | ((pixels[i] >> 16) & 255u);
    }
    Check(vkMapMemory(g.device, g.buffer_memory, 0, VK_WHOLE_SIZE, 0, &mapped));
    std::memcpy(static_cast<char*>(mapped) + 64, bgra.data(), sizeof(bgra));
    vkUnmapMemory(g.device, g.buffer_memory);
    VkDescriptorPoolSize size{VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 2};
    VkDescriptorPoolCreateInfo dp{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO}; dp.maxSets = 2; dp.poolSizeCount = 1; dp.pPoolSizes = &size;
    Check(vkCreateDescriptorPool(g.device, &dp, nullptr, &g.descriptors));
    VkDescriptorSetAllocateInfo sa{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO}; sa.descriptorPool = g.descriptors; sa.descriptorSetCount = 1; sa.pSetLayouts = &g.set_layout;
    VkDescriptorSet set{}; Check(vkAllocateDescriptorSets(g.device, &sa, &set));
    VkDescriptorImageInfo ii{g.sampler, input.view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    VkWriteDescriptorSet write{VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET}; write.dstSet = set; write.dstBinding = 0; write.descriptorCount = 1; write.descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER; write.pImageInfo = &ii;
    vkUpdateDescriptorSets(g.device, 1, &write, 0, nullptr);
    VkDescriptorSet bgra_set{}; Check(vkAllocateDescriptorSets(g.device, &sa, &bgra_set));
    VkDescriptorImageInfo bgra_info{g.sampler, input_bgra.view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
    write.dstSet = bgra_set; write.pImageInfo = &bgra_info;
    vkUpdateDescriptorSets(g.device, 1, &write, 0, nullptr);
    const auto hp = g.Pipeline(VK_FORMAT_A2B10G10R10_UNORM_PACK32);
    const auto sp = g.Pipeline(VK_FORMAT_R8G8B8A8_UNORM);
    VkCommandBufferAllocateInfo ca{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO}; ca.commandPool = g.pool; ca.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY; ca.commandBufferCount = 1;
    VkCommandBuffer cmd{}; Check(vkAllocateCommandBuffers(g.device, &ca, &cmd));
    VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO}; Check(vkBeginCommandBuffer(cmd, &begin));
    Barrier(cmd,input.image,VK_IMAGE_LAYOUT_UNDEFINED,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,0,VK_ACCESS_TRANSFER_WRITE_BIT);
    VkBufferImageCopy copy{}; copy.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT,0,0,1}; copy.imageExtent = {Width,1,1};
    vkCmdCopyBufferToImage(cmd,g.buffer,input.image,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&copy);
    Barrier(cmd,input.image,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,VK_ACCESS_TRANSFER_WRITE_BIT,VK_ACCESS_SHADER_READ_BIT);
    Barrier(cmd,input_bgra.image,VK_IMAGE_LAYOUT_UNDEFINED,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,0,VK_ACCESS_TRANSFER_WRITE_BIT);
    copy.bufferOffset = 64;
    vkCmdCopyBufferToImage(cmd,g.buffer,input_bgra.image,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&copy);
    Barrier(cmd,input_bgra.image,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,VK_ACCESS_TRANSFER_WRITE_BIT,VK_ACCESS_SHADER_READ_BIT);
    // Same SDR input represents a real or generated picture. Alternate HDR/SDR output without
    // modifying it, then verify identical HDR results and an unchanged SDR round trip.
    // Passes 5 and 6: the HDR brightness settings (white 200 / peak 600; no highlight boost).
    constexpr uint32_t Passes = 7;
    for (uint32_t pass = 0; pass < Passes; ++pass) {
        const bool is_hdr = pass != 1 && pass != 4; const auto target = is_hdr ? hdr : sdr;
        Barrier(cmd,target.image,pass >= 2 ? VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL : VK_IMAGE_LAYOUT_UNDEFINED,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,pass >= 2 ? VK_ACCESS_TRANSFER_READ_BIT : 0,VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT);
        VkRenderingAttachmentInfo att{VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO}; att.imageView = target.view; att.imageLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL; att.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR; att.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
        VkRenderingInfo rendering{VK_STRUCTURE_TYPE_RENDERING_INFO}; rendering.renderArea = {{0,0},{Width,1}}; rendering.layerCount = 1; rendering.colorAttachmentCount = 1; rendering.pColorAttachments = &att;
        vkCmdBeginRendering(cmd,&rendering);
        vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,is_hdr ? hp : sp);
        const auto source_set = pass == 3 ? bgra_set : set;
        vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,g.layout,0,1,&source_set,0,nullptr);
        struct Settings { float gamma; uint32_t hdr, srgb, desktop_hdr; float white, peak, boost; } settings{
            1,is_hdr ? 1u : 0u,1,pass == 4 ? 1u : 0u,pass == 5 ? 200.0f : 120.0f,pass == 5 ? 600.0f : 1000.0f,
            pass == 6 ? 0.0f : 1.0f};
        vkCmdPushConstants(cmd,g.layout,VK_SHADER_STAGE_FRAGMENT_BIT,0,sizeof(settings),&settings);
        vkCmdDraw(cmd,3,1,0,0); vkCmdEndRendering(cmd);
        Barrier(cmd,target.image,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT,VK_ACCESS_TRANSFER_READ_BIT);
        copy.bufferOffset = 128 + pass * sizeof(pixels);
        vkCmdCopyImageToBuffer(cmd,target.image,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,g.buffer,1,&copy);
    }
    VkMemoryBarrier host{VK_STRUCTURE_TYPE_MEMORY_BARRIER}; host.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT; host.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&host,0,nullptr,0,nullptr);
    Check(vkEndCommandBuffer(cmd));
    VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO}; submit.commandBufferCount = 1; submit.pCommandBuffers = &cmd;
    Check(vkQueueSubmit(g.queue,1,&submit,{})); Check(vkQueueWaitIdle(g.queue));
    Check(vkMapMemory(g.device,g.buffer_memory,0,VK_WHOLE_SIZE,0,&mapped));
    std::array<std::array<uint32_t,Width>,Passes> output{}; std::memcpy(output.data(),static_cast<char*>(mapped)+128,sizeof(output));
    vkUnmapMemory(g.device,g.buffer_memory);
    Require(output[0] == output[2], "HDR output changed across real/generated or HDR/SDR switch");
    Require(output[0] == output[3], "BGRA composition input changed HDR colors");
    for (uint32_t i=0;i<Width;++i) for (uint32_t c=0;c<3;++c)
        Require(std::abs(int((output[1][i]>>(8*c))&255)-int((pixels[i]>>(8*c))&255))<=1,"SDR was double-gamma/PQ encoded");
    double previous = -1;
    for (uint32_t i=0;i<5;++i) {
        const double nits=DecodeNits(double(output[0][i]&1023)/1023);
        Require(std::isfinite(nits) && nits >= previous && nits <= 1001,"HDR grayscale non-monotonic or above ceiling");
        previous=nits;
        if (i==0) Require(nits<0.001,"HDR black lifted");
        if (i==2) Require(nits>24 && nits<28,"Mid-gray was double decoded/encoded");
        if (i==4) Require(nits>730 && nits<760,"HDR shoulder/white reference mismatch");
        std::printf("gray %u: %.3f nits\n",i,nits);
    }
    Require((output[0][5]&1023)>((output[0][5]>>20)&1023),"Rec.2020 red/blue channel order incorrect");
    for (uint32_t i=0;i<5;++i) {
        const double bright=DecodeNits(double(output[5][i]&1023)/1023);
        const double flat=DecodeNits(double(output[6][i]&1023)/1023);
        std::printf("gray %u: white 200/peak 600 %.3f nits, no boost %.3f nits\n",i,bright,flat);
        Require(std::isfinite(bright) && bright <= 601,"HDR peak setting not respected");
        if (i==2) Require(bright>40 && bright<47,"HDR white setting does not scale mid-gray");
        if (i==4) Require(flat>115 && flat<125,"HDR highlight boost off still expands white");
    }
    const double compensated = double(output[4][1]&255)/255;
    const double desktop_linear = compensated <= 0.04045 ? compensated/12.92 : std::pow((compensated+0.055)/1.055,2.4);
    Require(std::abs(desktop_linear-std::pow(64.0/255,2.2))<0.002,"SDR desktop HDR compensation regressed");
    Require(validation_errors == 0, "Vulkan validation errors detected");
    std::puts("HDR presentation GPU PASS: PQ10, grayscale, RGBA/BGRA, real/generated equality, HDR/SDR transition, SDR round trip, desktop compensation, white/peak/boost settings");
    return 0;
} catch (const std::exception& e) {
    std::fprintf(stderr,"HDR presentation GPU FAIL: %s\n",e.what()); return 1;
}
