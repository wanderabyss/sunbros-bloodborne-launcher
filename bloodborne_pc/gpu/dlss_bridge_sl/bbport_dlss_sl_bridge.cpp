// SPDX-FileCopyrightText: Copyright 2026 bbport contributors
// SPDX-License-Identifier: MIT
//
// bbport_dlss_sl.dll: the bridge interface of bbport_dlss.dll (../dlss_bridge/bbport_dlss_bridge.h,
// ABI 3) on NVIDIA Streamline instead of NGX directly (plans/dlss-roadmap.md A1). NVIDIA's DLSS 5
// route goes through Streamline (sl.dlss_nr); running DLSS 4.5 Super Resolution through it now
// makes that an added feature rather than a rewrite.
//
// The DLL lives in a streamline\ folder beside bb-probe.exe with NVIDIA's signed Streamline
// runtime (sl.interposer.dll, sl.common.dll, sl.dlss.dll, nvngx_dlss.dll), which it loads at run
// time. bb-probe.exe picks it with BB_DLSS_BACKEND=streamline; the NGX bridge stays the default.
//
// Manual hooking (Streamline's ProgrammingGuideManualHooking.md): slInit runs in Configure, before
// the Vulkan instance and device exist; the device gets the extensions Streamline asks for;
// slSetVulkanInfo follows device creation; and the renderer routes present, swapchain and device
// wait calls through Streamline's proxies (BbDlssHookedProc) so its per-frame present work runs.
//
// Here: Super Resolution, and DLSS 5 reported as Streamline reports kFeatureDLSS_NR (2.14.16
// ships no plugin for it, so unsupported). Frame Generation stays off on this backend
// (FrameGenMaxCount 0): sl.dlss_g presents frames itself from inside the swapchain hooks, which
// the port's own pacing, frame pairing and HDR10 conversion do today; the renderer falls back to
// FSR 3.1 frame generation, as it does without nvngx_dlssg.dll. Reflex stays on the port's own
// VK_NV_low_latency2 path; sl.reflex is not loaded.

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <windows.h>

#include <vulkan/vulkan.h>

#include <sl.h>
#include <sl_consts.h>
#include <sl_dlss.h>
#include <sl_helpers_vk.h>
#include <sl_hooks.h>

#include "../dlss_bridge/bbport_dlss_bridge.h"

namespace {

constexpr char ProjectId[] = "42359704-c9f3-4806-9fb5-d469000fdb8a";
constexpr char EngineVersion[] = "bbport-windows";

// Streamline's core functions, from sl.interposer.dll.
struct Sl {
    HMODULE module{};
    PFun_slInit* Init{};
    PFun_slShutdown* Shutdown{};
    PFun_slIsFeatureSupported* IsFeatureSupported{};
    PFun_slGetFeatureRequirements* GetFeatureRequirements{};
    PFun_slGetFeatureFunction* GetFeatureFunction{};
    PFun_slSetVulkanInfo* SetVulkanInfo{};
    PFun_slGetNewFrameToken* GetNewFrameToken{};
    PFun_slSetConstants* SetConstants{};
    PFun_slSetTagForFrame* SetTagForFrame{};
    PFun_slEvaluateFeature* EvaluateFeature{};
    PFun_slFreeResources* FreeResources{};
    PFun_slDLSSSetOptions* DLSSSetOptions{};
    PFN_vkGetInstanceProcAddr GetInstanceProcAddr{};
    PFN_vkGetDeviceProcAddr GetDeviceProcAddr{};
};

struct State {
    BbDlssLogFn log{};
    std::wstring dll_directory;
    std::wstring data_directory;
    const wchar_t* plugin_path{};
    Sl sl;
    std::vector<VkExtensionProperties> instance_extensions, device_extensions;
    VkInstance instance{};
    VkPhysicalDevice physical{};
    VkDevice device{};
    BbDlssFeature feature_desc{};
    uint32_t frame_index{};
    bool configured{}, initialized{}, feature{}, neural_render{};
} state;

template <typename... Args>
void Log(int warning, const char* format, Args... args) {
    if (!state.log)
        return;
    std::array<char, 1024> text{};
    std::snprintf(text.data(), text.size(), format, args...);
    state.log(warning, text.data());
}

bool Check(const char* operation, sl::Result result) {
    if (result != sl::Result::eOk) {
        Log(1, "Streamline %s failed: %d", operation, static_cast<int>(result));
        return false;
    }
    return true;
}

// Streamline's own messages: warnings and errors always, the rest with BB_DLSS_SL_LOG=1.
void SlLog(sl::LogType type, const char* message) {
    static const bool verbose = [] {
        const char* env = std::getenv("BB_DLSS_SL_LOG");
        return env && env[0] == '1';
    }();
    if (!message || (type == sl::LogType::eInfo && !verbose))
        return;
    std::string text{message};
    while (!text.empty() && (text.back() == '\n' || text.back() == '\r'))
        text.pop_back();
    Log(type != sl::LogType::eInfo, "Streamline: %s", text.c_str());
}

template <typename T>
bool Load(T*& function, const char* name) {
    function = reinterpret_cast<T*>(GetProcAddress(state.sl.module, name));
    if (!function)
        Log(1, "sl.interposer.dll has no %s", name);
    return function != nullptr;
}

constexpr std::array Features{sl::kFeatureDLSS, sl::kFeatureDLSS_NR};

int32_t Configure(const wchar_t* dll_directory, const wchar_t* data_directory, BbDlssLogFn log) {
    state.log = log;
    state.dll_directory = dll_directory ? dll_directory : L".";
    state.data_directory = data_directory ? data_directory : L".";
    const std::wstring interposer = state.dll_directory + L"\\sl.interposer.dll";
    state.sl.module = LoadLibraryExW(interposer.c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!state.sl.module) {
        Log(1, "sl.interposer.dll could not be loaded from the streamline folder");
        return 0;
    }
    auto& sl = state.sl;
    if (!Load(sl.Init, "slInit") || !Load(sl.Shutdown, "slShutdown") ||
        !Load(sl.IsFeatureSupported, "slIsFeatureSupported") ||
        !Load(sl.GetFeatureRequirements, "slGetFeatureRequirements") ||
        !Load(sl.GetFeatureFunction, "slGetFeatureFunction") ||
        !Load(sl.SetVulkanInfo, "slSetVulkanInfo") ||
        !Load(sl.GetNewFrameToken, "slGetNewFrameToken") ||
        !Load(sl.SetConstants, "slSetConstants") ||
        !Load(sl.SetTagForFrame, "slSetTagForFrame") ||
        !Load(sl.EvaluateFeature, "slEvaluateFeature") ||
        !Load(sl.FreeResources, "slFreeResources")) {
        return 0;
    }
    sl.GetInstanceProcAddr = reinterpret_cast<PFN_vkGetInstanceProcAddr>(
        GetProcAddress(sl.module, "vkGetInstanceProcAddr"));
    sl.GetDeviceProcAddr = reinterpret_cast<PFN_vkGetDeviceProcAddr>(
        GetProcAddress(sl.module, "vkGetDeviceProcAddr"));
    if (!sl.GetInstanceProcAddr || !sl.GetDeviceProcAddr) {
        Log(1, "sl.interposer.dll has no Vulkan proxies");
        return 0;
    }

    state.plugin_path = state.dll_directory.c_str();
    sl::Preferences preferences{};
    preferences.showConsole = false;
    preferences.logLevel = sl::LogLevel::eDefault;
    preferences.logMessageCallback = SlLog;
    preferences.pathsToPlugins = &state.plugin_path;
    preferences.numPathsToPlugins = 1;
    preferences.pathToLogsAndData = state.data_directory.c_str();
    // No over-the-air plugin updates: the shipped, signed DLLs are what was tested.
    // Frame-based tags: each evaluation tags its own images (slSetTagForFrame).
    preferences.flags = sl::PreferenceFlags::eDisableCLStateTracking |
                        sl::PreferenceFlags::eUseManualHooking |
                        sl::PreferenceFlags::eUseFrameBasedResourceTagging;
    preferences.featuresToLoad = Features.data();
    preferences.numFeaturesToLoad = static_cast<uint32_t>(Features.size());
    preferences.engine = sl::EngineType::eCustom;
    preferences.engineVersion = EngineVersion;
    preferences.projectId = ProjectId;
    preferences.renderAPI = sl::RenderAPI::eVulkan;
    if (!Check("initialization", sl.Init(preferences, sl::kSDKVersion)))
        return 0;
    Log(0, "backend Streamline %d.%d.%d", SL_VERSION_MAJOR, SL_VERSION_MINOR, SL_VERSION_PATCH);
    state.configured = true;
    return 1;
}

void Merge(std::vector<VkExtensionProperties>& into, const char* const* names, uint32_t count) {
    for (uint32_t i = 0; i < count; ++i) {
        if (std::none_of(into.begin(), into.end(), [&](const VkExtensionProperties& known) {
                return std::strcmp(known.extensionName, names[i]) == 0;
            })) {
            VkExtensionProperties extension{};
            std::snprintf(extension.extensionName, sizeof(extension.extensionName), "%s",
                          names[i]);
            into.push_back(extension);
        }
    }
}

// Super Resolution's requirements. It asks for no queues of its own; if a later Streamline does,
// this backend declines (the renderer creates its queues without the bridge).
bool Requirements(sl::FeatureRequirements& requirements) {
    if (!Check("DLSS requirements",
               state.sl.GetFeatureRequirements(sl::kFeatureDLSS, requirements)))
        return false;
    if (!(requirements.flags & sl::FeatureRequirementFlags::eVulkanSupported)) {
        Log(1, "Streamline DLSS does not support Vulkan here");
        return false;
    }
    if (requirements.vkNumComputeQueuesRequired || requirements.vkNumGraphicsQueuesRequired) {
        Log(1, "Streamline DLSS asks for extra queues (%u compute, %u graphics)",
            requirements.vkNumComputeQueuesRequired, requirements.vkNumGraphicsQueuesRequired);
        return false;
    }
    return true;
}

int32_t InstanceExtensions(uint32_t* count, const VkExtensionProperties** extensions) {
    sl::FeatureRequirements requirements{};
    if (!state.configured || !count || !extensions || !Requirements(requirements))
        return 0;
    state.instance_extensions.clear();
    Merge(state.instance_extensions, requirements.vkInstanceExtensions,
          requirements.vkNumInstanceExtensions);
    *count = static_cast<uint32_t>(state.instance_extensions.size());
    *extensions = state.instance_extensions.data();
    return 1;
}

int32_t DeviceExtensions(VkInstance, VkPhysicalDevice, uint32_t* count,
                         const VkExtensionProperties** extensions) {
    sl::FeatureRequirements requirements{};
    if (!state.configured || !count || !extensions || !Requirements(requirements))
        return 0;
    state.device_extensions.clear();
    Merge(state.device_extensions, requirements.vkDeviceExtensions,
          requirements.vkNumDeviceExtensions);
    *count = static_cast<uint32_t>(state.device_extensions.size());
    *extensions = state.device_extensions.data();
    return 1;
}

int32_t Initialize(VkInstance instance, VkPhysicalDevice physical, VkDevice device,
                   PFN_vkGetInstanceProcAddr, PFN_vkGetDeviceProcAddr) {
    if (!state.configured || state.initialized)
        return 0;
    sl::VulkanInfo info{};
    info.instance = instance;
    info.physicalDevice = physical;
    info.device = device;
    if (!Check("device setup", state.sl.SetVulkanInfo(info)))
        return 0;
    state.instance = instance;
    state.physical = physical;
    state.device = device;
    sl::AdapterInfo adapter{};
    adapter.vkPhysicalDevice = physical;
    const auto supported = state.sl.IsFeatureSupported(sl::kFeatureDLSS, adapter);
    if (supported != sl::Result::eOk) {
        Log(1, "DLSS Super Resolution is not available through Streamline (%d)",
            static_cast<int>(supported));
        return 0;
    }
    void* set_options{};
    if (!Check("DLSS options function",
               state.sl.GetFeatureFunction(sl::kFeatureDLSS, "slDLSSSetOptions", set_options)))
        return 0;
    state.sl.DLSSSetOptions = reinterpret_cast<PFun_slDLSSSetOptions*>(set_options);
    state.neural_render = state.sl.IsFeatureSupported(sl::kFeatureDLSS_NR, adapter) ==
                          sl::Result::eOk;
    Log(0, "neural rendering (DLSS 5) through Streamline: %s",
        state.neural_render ? "supported" : "not available on this system");
    state.initialized = true;
    return 1;
}

const sl::ViewportHandle Viewport{0u};

void ReleaseFeature() {
    if (state.feature) {
        state.sl.FreeResources(sl::kFeatureDLSS, Viewport);
        state.feature = false;
    }
}

int32_t CreateFeature(VkCommandBuffer, const BbDlssFeature* desc) {
    if (!state.initialized || !desc)
        return 0;
    ReleaseFeature();
    static constexpr std::array modes{sl::DLSSMode::eDLAA, sl::DLSSMode::eMaxQuality,
                                      sl::DLSSMode::eBalanced, sl::DLSSMode::eMaxPerformance,
                                      sl::DLSSMode::eUltraPerformance};
    const int quality = std::clamp(desc->quality, 0, 4);
    sl::DLSSOptions options{};
    options.mode = modes[quality];
    options.outputWidth = desc->output_width;
    options.outputHeight = desc->output_height;
    options.colorBuffersHDR = desc->hdr ? sl::Boolean::eTrue : sl::Boolean::eFalse;
    options.useAutoExposure = desc->hdr ? sl::Boolean::eTrue : sl::Boolean::eFalse;
    // The model only for this quality mode (DLSS-4, as the NGX bridge); the others stay the
    // driver's choice. The numbers are NGX's render preset values, which Streamline shares.
    const auto preset = static_cast<sl::DLSSPreset>(desc->preset);
    switch (quality) {
    case 0: options.dlaaPreset = preset; break;
    case 1: options.qualityPreset = preset; break;
    case 2: options.balancedPreset = preset; break;
    case 3: options.performancePreset = preset; break;
    default: options.ultraPerformancePreset = preset; break;
    }
    if (!Check("DLSS options", state.sl.DLSSSetOptions(Viewport, options)))
        return 0;
    state.feature_desc = *desc;
    state.feature = true;
    Log(0, "DLSS %ux%u -> %ux%u, quality %d, preset %u%s (Streamline)", desc->input_width,
        desc->input_height, desc->output_width, desc->output_height, desc->quality, desc->preset,
        desc->hdr ? ", HDR input" : "");
    return 1;
}

sl::Resource Wrap(const BbDlssImage& image, bool writable) {
    sl::Resource resource{sl::ResourceType::eTex2d, reinterpret_cast<void*>(image.image), nullptr,
                          reinterpret_cast<void*>(image.view),
                          static_cast<uint32_t>(VK_IMAGE_LAYOUT_GENERAL)};
    resource.width = image.width;
    resource.height = image.height;
    resource.nativeFormat = static_cast<uint32_t>(image.format);
    resource.mipLevels = 1;
    resource.arrayLayers = 1;
    resource.usage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT |
                     (writable ? VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT : 0);
    return resource;
}

void Identity(sl::float4x4& m) {
    m.setRow(0, {1.0f, 0.0f, 0.0f, 0.0f});
    m.setRow(1, {0.0f, 1.0f, 0.0f, 0.0f});
    m.setRow(2, {0.0f, 0.0f, 1.0f, 0.0f});
    m.setRow(3, {0.0f, 0.0f, 0.0f, 1.0f});
}

int32_t Evaluate(VkCommandBuffer command, const BbDlssEvaluate* evaluate) {
    if (!state.feature || !evaluate)
        return 0;
    sl::FrameToken* frame{};
    const uint32_t index = state.frame_index++;
    if (!Check("frame token", state.sl.GetNewFrameToken(frame, &index)) || !frame)
        return 0;

    // Super Resolution reads the jitter, the motion vector scale and the flags; the camera stays
    // at Streamline's "not provided" defaults apart from identity matrices it validates.
    sl::Constants constants{};
    Identity(constants.cameraViewToClip);
    Identity(constants.clipToCameraView);
    Identity(constants.clipToLensClip);
    Identity(constants.clipToPrevClip);
    Identity(constants.prevClipToClip);
    constants.jitterOffset = {evaluate->jitter_x, evaluate->jitter_y};
    // The port's motion vectors are render-resolution pixels (NGX's MV scale 1).
    constants.mvecScale = {1.0f / static_cast<float>(state.feature_desc.input_width),
                           1.0f / static_cast<float>(state.feature_desc.input_height)};
    constants.cameraPinholeOffset = {0.0f, 0.0f};
    constants.cameraPos = {0.0f, 0.0f, 0.0f};
    constants.cameraUp = {0.0f, 1.0f, 0.0f};
    constants.cameraRight = {1.0f, 0.0f, 0.0f};
    constants.cameraFwd = {0.0f, 0.0f, 1.0f};
    constants.cameraNear = 0.1f;
    constants.cameraFar = 3000.0f;
    constants.cameraFOV = 1.0f;
    constants.cameraAspectRatio = static_cast<float>(state.feature_desc.output_width) /
                                  static_cast<float>(state.feature_desc.output_height);
    constants.depthInverted =
        state.feature_desc.depth_inverted ? sl::Boolean::eTrue : sl::Boolean::eFalse;
    constants.cameraMotionIncluded = sl::Boolean::eTrue;
    constants.motionVectors3D = sl::Boolean::eFalse;
    constants.reset = evaluate->reset ? sl::Boolean::eTrue : sl::Boolean::eFalse;
    if (!Check("constants", state.sl.SetConstants(constants, *frame, Viewport)))
        return 0;

    sl::Resource color = Wrap(evaluate->color, false);
    sl::Resource depth = Wrap(evaluate->depth, false);
    sl::Resource motion = Wrap(evaluate->motion, false);
    sl::Resource output = Wrap(evaluate->output, true);
    const sl::Extent input_extent{0, 0, state.feature_desc.input_width,
                                  state.feature_desc.input_height};
    const sl::Extent output_extent{0, 0, state.feature_desc.output_width,
                                   state.feature_desc.output_height};
    const std::array tags{
        sl::ResourceTag{&color, sl::kBufferTypeScalingInputColor, sl::ResourceLifecycle::eValidUntilEvaluate, &input_extent},
        sl::ResourceTag{&depth, sl::kBufferTypeDepth, sl::ResourceLifecycle::eValidUntilEvaluate, &input_extent},
        sl::ResourceTag{&motion, sl::kBufferTypeMotionVectors, sl::ResourceLifecycle::eValidUntilEvaluate, &input_extent},
        sl::ResourceTag{&output, sl::kBufferTypeScalingOutputColor, sl::ResourceLifecycle::eValidUntilEvaluate, &output_extent},
    };
    auto* cmd = reinterpret_cast<sl::CommandBuffer*>(command);
    if (!Check("tags", state.sl.SetTagForFrame(*frame, Viewport, tags.data(),
                                               static_cast<uint32_t>(tags.size()), cmd)))
        return 0;
    const sl::BaseStructure* inputs[] = {&Viewport};
    return Check("DLSS evaluation",
                 state.sl.EvaluateFeature(sl::kFeatureDLSS, *frame, inputs, 1, cmd))
               ? 1
               : 0;
}

// Frame Generation stays on the NGX backend (see the top of this file).
int32_t FrameGenMaxCount() {
    return 0;
}

int32_t FrameGenCreate(VkCommandBuffer, const BbDlssgFeature*) {
    return 0;
}

int32_t FrameGenEvaluate(VkCommandBuffer, const BbDlssgEvaluate*) {
    return 0;
}

void FrameGenRelease() {}

// DLSS 5 (ABI 3): Streamline's answer for kFeatureDLSS_NR. Its options and tags are not in the
// public headers yet (2.14.16 has the feature id only), so a supported answer still creates
// nothing here; it is logged so the day a plugin ships is visible.
int32_t NeuralRenderSupported() {
    return 0;
}

int32_t NeuralRenderCreate(VkCommandBuffer, const BbDlssNrFeature*) {
    return 0;
}

int32_t NeuralRenderEvaluate(VkCommandBuffer, const BbDlssNrEvaluate*) {
    return 0;
}

void NeuralRenderRelease() {}

void Shutdown() {
    ReleaseFeature();
    if (state.configured) {
        state.sl.Shutdown();
        state.configured = state.initialized = false;
    }
}

const BbDlssApi api{BBPORT_DLSS_BRIDGE_ABI, Configure,        InstanceExtensions, DeviceExtensions,
                    Initialize,             CreateFeature,    Evaluate,           ReleaseFeature,
                    Shutdown,               FrameGenMaxCount, FrameGenCreate,     FrameGenEvaluate,
                    FrameGenRelease,        NeuralRenderSupported, NeuralRenderCreate,
                    NeuralRenderEvaluate,   NeuralRenderRelease};

} // namespace

extern "C" __declspec(dllexport) const BbDlssApi* BbDlssGetApi() {
    return &api;
}

// Streamline's proxy for a Vulkan function it intercepts (sl_hooks.h: present, swapchain
// creation, destruction, images and acquire, device wait idle, surface creation and
// destruction), or null. The renderer calls these instead of the loader's after Initialize.
extern "C" __declspec(dllexport) PFN_vkVoidFunction BbDlssHookedProc(const char* name) {
    if (!state.initialized || !name)
        return nullptr;
    static constexpr std::array<const char*, 6> device_functions{
        "vkQueuePresentKHR",       "vkCreateSwapchainKHR",  "vkDestroySwapchainKHR",
        "vkGetSwapchainImagesKHR", "vkAcquireNextImageKHR", "vkDeviceWaitIdle"};
    for (const char* function : device_functions) {
        if (std::strcmp(function, name) == 0)
            return state.sl.GetDeviceProcAddr(state.device, name);
    }
    if (std::strcmp(name, "vkCreateWin32SurfaceKHR") == 0 ||
        std::strcmp(name, "vkDestroySurfaceKHR") == 0)
        return state.sl.GetInstanceProcAddr(state.instance, name);
    return nullptr;
}
