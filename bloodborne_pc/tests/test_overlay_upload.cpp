// SPDX-License-Identifier: GPL-2.0-or-later
// Real offscreen GPU exercise of the patched backend, including its private
// upload buffers. No game, window, launcher or timing-dependent assertions.
#include <vulkan/vulkan.h>
#include "imgui.h"
#include "../gpu/third_party/imgui/backends/imgui_impl_vulkan.cpp"
#include "gpu/shadps4/video_core/renderer_vulkan/pipeline_cache_data.h"
#include <array>
#include <atomic>
#include <thread>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>

static void Check(VkResult r) {
    if (r != VK_SUCCESS) throw std::runtime_error("Vulkan error " + std::to_string(r));
}
static void Require(bool b, const char* why) { if (!b) throw std::runtime_error(why); }

int main() try {
    VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO}; app.apiVersion = VK_API_VERSION_1_1;
    VkInstanceCreateInfo ici{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO}; ici.pApplicationInfo=&app;
    VkInstance instance; Check(vkCreateInstance(&ici,nullptr,&instance));
    uint32_t count=0; Check(vkEnumeratePhysicalDevices(instance,&count,nullptr));
    Require(count>0,"No Vulkan device");
    std::vector<VkPhysicalDevice> physicals(count); Check(vkEnumeratePhysicalDevices(instance,&count,physicals.data()));
    auto physical=physicals[0]; VkPhysicalDeviceProperties props{}; vkGetPhysicalDeviceProperties(physical,&props);
    vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,nullptr);
    std::vector<VkQueueFamilyProperties> families(count); vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,families.data());
    uint32_t family=0; while(family<count && !(families[family].queueFlags&VK_QUEUE_GRAPHICS_BIT))++family;
    Require(family<count,"No graphics queue");
    float priority=1; VkDeviceQueueCreateInfo qi{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
    qi.queueFamilyIndex=family; qi.queueCount=1; qi.pQueuePriorities=&priority;
    VkDeviceCreateInfo dci{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO}; dci.queueCreateInfoCount=1; dci.pQueueCreateInfos=&qi;
    VkDevice device; Check(vkCreateDevice(physical,&dci,nullptr,&device));
    VkQueue queue; vkGetDeviceQueue(device,family,0,&queue);
    VkCommandPoolCreateInfo pci{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO}; pci.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT; pci.queueFamilyIndex=family;
    VkCommandPool pool; Check(vkCreateCommandPool(device,&pci,nullptr,&pool));
    VkCommandBufferAllocateInfo cai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO}; cai.commandPool=pool; cai.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY; cai.commandBufferCount=1;
    VkCommandBuffer cmd; Check(vkAllocateCommandBuffers(device,&cai,&cmd));
    VkImageCreateInfo image_info{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO}; image_info.imageType=VK_IMAGE_TYPE_2D;
    image_info.format=VK_FORMAT_R8G8B8A8_UNORM; image_info.extent={128,128,1}; image_info.mipLevels=1; image_info.arrayLayers=1;
    image_info.samples=VK_SAMPLE_COUNT_1_BIT; image_info.tiling=VK_IMAGE_TILING_OPTIMAL; image_info.usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
    VkImage image; Check(vkCreateImage(device,&image_info,nullptr,&image));
    VkMemoryRequirements req; vkGetImageMemoryRequirements(device,image,&req);
    VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(physical,&mp);
    uint32_t memory_type=0; while(memory_type<mp.memoryTypeCount && !(req.memoryTypeBits&(1u<<memory_type)))++memory_type;
    Require(memory_type<mp.memoryTypeCount,"No image memory");
    VkMemoryAllocateInfo mai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; mai.allocationSize=req.size; mai.memoryTypeIndex=memory_type;
    VkDeviceMemory memory; Check(vkAllocateMemory(device,&mai,nullptr,&memory)); Check(vkBindImageMemory(device,image,memory,0));
    VkImageViewCreateInfo vci{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO}; vci.image=image; vci.viewType=VK_IMAGE_VIEW_TYPE_2D; vci.format=image_info.format;
    vci.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
    VkImageView view; Check(vkCreateImageView(device,&vci,nullptr,&view));
    VkAttachmentDescription attachment{}; attachment.format=image_info.format; attachment.samples=VK_SAMPLE_COUNT_1_BIT;
    attachment.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR; attachment.storeOp=VK_ATTACHMENT_STORE_OP_STORE;
    attachment.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED; attachment.finalLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
    VkAttachmentReference reference{0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
    VkSubpassDescription subpass{}; subpass.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS; subpass.colorAttachmentCount=1; subpass.pColorAttachments=&reference;
    VkRenderPassCreateInfo rpci{VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO}; rpci.attachmentCount=1; rpci.pAttachments=&attachment; rpci.subpassCount=1; rpci.pSubpasses=&subpass;
    VkRenderPass pass; Check(vkCreateRenderPass(device,&rpci,nullptr,&pass));
    VkFramebufferCreateInfo fci{VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO}; fci.renderPass=pass; fci.attachmentCount=1; fci.pAttachments=&view; fci.width=128; fci.height=128; fci.layers=1;
    VkFramebuffer framebuffer; Check(vkCreateFramebuffer(device,&fci,nullptr,&framebuffer));

    VkPipelineCacheCreateInfo cache_info{VK_STRUCTURE_TYPE_PIPELINE_CACHE_CREATE_INFO};
    VkPipelineCache cache; Check(vkCreatePipelineCache(device,&cache_info,nullptr,&cache));
    ImGui::CreateContext(); auto& io=ImGui::GetIO(); io.DisplaySize={128,128}; io.DeltaTime=1.0f/60; io.IniFilename=nullptr;
    ImGui_ImplVulkan_InitInfo init{}; init.ApiVersion=app.apiVersion; init.Instance=instance; init.PhysicalDevice=physical; init.Device=device;
    init.PipelineCache=cache;
    init.QueueFamily=family; init.Queue=queue; init.DescriptorPoolSize=32; init.MinImageCount=3; init.ImageCount=3;
    init.PipelineInfoMain.RenderPass=pass; init.CheckVkResultFn=Check;
    Require(ImGui_ImplVulkan_Init(&init),"Backend init failed");
    std::atomic<unsigned> snapshots{0}, snapshot_errors{0};
    std::array<uint8_t,16> uuid;std::memcpy(uuid.data(),props.pipelineCacheUUID,16);
    std::jthread reader([&](std::stop_token stop) {
        while(!stop.stop_requested()) {
            size_t bytes=0;
            if(vkGetPipelineCacheData(device,cache,&bytes,nullptr)!=VK_SUCCESS || bytes<32 || bytes>(256u<<20)) {
                ++snapshot_errors; break;
            }
            std::vector<uint8_t> blob(bytes);
            const auto r=vkGetPipelineCacheData(device,cache,&bytes,blob.data());
            if(r!=VK_SUCCESS && r!=VK_INCOMPLETE) {++snapshot_errors;break;}
            blob.resize(bytes);
            if(!Vulkan::CompatiblePipelineData(blob,props.vendorID,props.deviceID,uuid)) ++snapshot_errors;
            ++snapshots;
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    });
    unsigned reused=0,grown=0;
    for(int frame=0;frame<24;++frame) {
        // Cover every ring slot repeatedly, with growth and later smaller draws.
        const int rects=frame<3?8:frame<6?800:frame<9?3000:frame<12?6000:100;
        // Previous submission is complete: safely rebuild a pipeline while the
        // background snapshot reads the default internally synchronized cache.
        if(frame%4==0) ImGui_ImplVulkan_CreateMainPipeline(&init.PipelineInfoMain);
        ImGui_ImplVulkan_NewFrame(); ImGui::NewFrame();
        auto* draw=ImGui::GetBackgroundDrawList();
        for(int i=0;i<rects;++i) {float x=float(i%64);draw->AddRectFilled({x,x},{x+2,x+3},IM_COL32(20,40,60,255));}
        ImGui::Render(); auto* data=ImGui::GetDrawData(); Require(data->TotalVtxCount>0,"No draw data");
        auto& buffers=ImGui_ImplVulkan_GetBackendData()->MainWindowRenderBuffers;
        ImGui_ImplVulkan_FrameRenderBuffers before{};
        if(buffers.Count) before=buffers.FrameRenderBuffers[(buffers.Index+1)%buffers.Count];
        Check(vkResetCommandBuffer(cmd,0)); VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO}; Check(vkBeginCommandBuffer(cmd,&begin));
        VkClearValue clear{}; VkRenderPassBeginInfo rp{VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO}; rp.renderPass=pass; rp.framebuffer=framebuffer;
        rp.renderArea={{0,0},{128,128}}; rp.clearValueCount=1; rp.pClearValues=&clear;
        vkCmdBeginRenderPass(cmd,&rp,VK_SUBPASS_CONTENTS_INLINE); ImGui_ImplVulkan_RenderDrawData(data,cmd); vkCmdEndRenderPass(cmd);
        auto& rb=buffers.FrameRenderBuffers[buffers.Index]; Require(rb.VertexMapped && rb.IndexMapped,"Uploads not mapped");
        if(before.VertexBuffer && before.VertexBufferSize>=VkDeviceSize(data->TotalVtxCount*sizeof(ImDrawVert))) {
            Require(before.VertexBufferMemory==rb.VertexBufferMemory && before.VertexMapped==rb.VertexMapped,"Reusable vertex memory replaced");++reused;
        } else ++grown;
        size_t vo=0,ioffset=0;
        for(auto* list:data->CmdLists) {
            const size_t vb=list->VtxBuffer.size_in_bytes(),ib=list->IdxBuffer.size_in_bytes();
            Require(std::memcmp(static_cast<char*>(rb.VertexMapped)+vo,list->VtxBuffer.Data,vb)==0,"Vertex payload mismatch");
            Require(std::memcmp(static_cast<char*>(rb.IndexMapped)+ioffset,list->IdxBuffer.Data,ib)==0,"Index payload mismatch");vo+=vb;ioffset+=ib;
        }
        Check(vkEndCommandBuffer(cmd)); VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO}; submit.commandBufferCount=1; submit.pCommandBuffers=&cmd;
        Check(vkQueueSubmit(queue,1,&submit,VK_NULL_HANDLE)); Check(vkQueueWaitIdle(queue));
    }
    reader.request_stop(); reader.join();
    Require(snapshots>0 && snapshot_errors==0,"Concurrent driver-cache snapshot failed");
    Require(reused && grown,"Ring reuse/growth not covered");
    ImGui_ImplVulkan_Shutdown(); ImGui::DestroyContext();
    size_t bytes=0; Check(vkGetPipelineCacheData(device,cache,&bytes,nullptr));
    std::vector<uint8_t> blob(bytes); Check(vkGetPipelineCacheData(device,cache,&bytes,blob.data())); blob.resize(bytes);
    Require(Vulkan::CompatiblePipelineData(blob,props.vendorID,props.deviceID,uuid),"Driver cache header rejected");
    cache_info.initialDataSize=blob.size();cache_info.pInitialData=blob.data(); VkPipelineCache restored;
    Check(vkCreatePipelineCache(device,&cache_info,nullptr,&restored)); vkDestroyPipelineCache(device,restored,nullptr);vkDestroyPipelineCache(device,cache,nullptr);
    vkDestroyFramebuffer(device,framebuffer,nullptr);vkDestroyRenderPass(device,pass,nullptr);vkDestroyImageView(device,view,nullptr);
    vkDestroyImage(device,image,nullptr);vkFreeMemory(device,memory,nullptr);vkDestroyCommandPool(device,pool,nullptr);vkDestroyDevice(device,nullptr);vkDestroyInstance(instance,nullptr);
    std::printf("Overlay upload GPU: PASS on %s (%u reused, %u grown; payloads, shutdown, concurrent driver cache roundtrip)\n",props.deviceName,reused,grown);
    return 0;
} catch(const std::exception& e) {std::fprintf(stderr,"Overlay upload GPU: FAIL: %s\n",e.what());return 1;}
