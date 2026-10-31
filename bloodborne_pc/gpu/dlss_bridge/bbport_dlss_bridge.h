// SPDX-FileCopyrightText: Copyright 2026 IFreemz (shadps4_dlss bridge), bbport contributors
// SPDX-License-Identifier: MIT
//
// C interface between bbport and bbport_dlss.dll. The port contains no NVIDIA code: it loads the
// bridge at run time when it is present (next to bb-probe.exe, with nvngx_dlss.dll) and keeps
// its other upscalers when it is absent. Adapted from IFreemz/shadPS4-Bloodborne-DLSS-FSR.

#pragma once

#include <stdint.h>
#include <vulkan/vulkan.h>

#ifdef __cplusplus
extern "C" {
#endif

// 2: DLSS Frame Generation (the FrameGen* members; an ABI 1 bridge has DLSS only).
// 3: DLSS 5 neural rendering (the NeuralRender* members). This bridge reports it unsupported:
//    NVIDIA has no DLSS 5 runtime usable from Vulkan on GeForce RTX 40 yet; only the bridge body changes when one ships.
#define BBPORT_DLSS_BRIDGE_ABI 3

typedef void (*BbDlssLogFn)(int warning, const char* message);

typedef struct BbDlssImage {
    VkImage image;
    VkImageView view;
    VkImageSubresourceRange range;
    VkFormat format;
    uint32_t width;
    uint32_t height;
} BbDlssImage;

typedef struct BbDlssFeature {
    uint32_t input_width;
    uint32_t input_height;
    uint32_t output_width;
    uint32_t output_height;
    int32_t quality; // 0 DLAA, 1 Quality, 2 Balanced, 3 Performance, 4 Ultra Performance
    int32_t depth_inverted;
    uint32_t preset; // NVSDK_NGX_DLSS_Hint_Render_Preset value, 0 = driver default
    int32_t hdr;     // 1: linear HDR colour with automatic exposure, 0: tonemapped colour
} BbDlssFeature;

typedef struct BbDlssEvaluate {
    BbDlssImage color;  // sampled
    BbDlssImage depth;  // sampled, hardware depth
    BbDlssImage motion; // sampled, render-resolution pixels, current to previous
    BbDlssImage output; // storage, general layout
    float jitter_x;
    float jitter_y;
    int32_t reset;
    float frame_ms;
    float sharpness; // 0..1; 0 leaves the output unsharpened
} BbDlssEvaluate;

// DLSS Frame Generation (nvngx_dlssg.dll): frames between two finished frames.
typedef struct BbDlssgFeature {
    uint32_t width;         // backbuffer: input and output colour
    uint32_t height;
    VkFormat format;
    uint32_t render_width;  // depth and motion vectors
    uint32_t render_height;
} BbDlssgFeature;

typedef struct BbDlssgEvaluate {
    BbDlssImage backbuffer; // sampled, general layout: the finished frame (UI included)
    BbDlssImage depth;      // sampled, hardware depth values (a depth or R32F image)
    BbDlssImage motion;     // sampled, render-resolution pixels, current to previous
    BbDlssImage output;     // storage, general layout: the generated frame
    BbDlssImage hudless;    // sampled: the backbuffer before the UI; image null when none
    float jitter_x;         // render pixels
    float jitter_y;
    float camera_near;
    float camera_far;
    float camera_fov;       // vertical, radians
    int32_t depth_inverted;
    int32_t reset;
    uint32_t multi_frame_count; // frames generated for this pair (1: 2x .. 3: 4x)
    uint32_t multi_frame_index; // 1 .. multi_frame_count, in order
    // Row-major, row vectors (v * m), D3D clip space (y up, depth 0 at the near plane): the
    // projection, current clip to previous clip and back. has_matrices 0: a camera that stood
    // still and a projection from camera_fov is assumed.
    int32_t has_matrices;
    float view_to_clip[4][4];
    float clip_to_prev_clip[4][4];
    float prev_clip_to_clip[4][4];
} BbDlssgEvaluate;

// DLSS 5 neural rendering: repaints the upscaled frame in place, after super resolution and
// before sharpening, post-processing and the UI.
typedef struct BbDlssNrFeature {
    uint32_t width;         // the upscaled colour (output size)
    uint32_t height;
    VkFormat format;
    uint32_t render_width;  // depth and motion vectors
    uint32_t render_height;
    int32_t hdr;            // 1: linear HDR colour, 0: tonemapped colour
} BbDlssNrFeature;

typedef struct BbDlssNrEvaluate {
    BbDlssImage color;      // storage, general layout: read and written in place
    BbDlssImage depth;      // sampled, hardware depth values
    BbDlssImage motion;     // sampled, render-resolution pixels, current to previous
    BbDlssImage normals;    // sampled, optional (image null when none)
    BbDlssImage albedo;     // sampled, optional (image null when none)
    BbDlssImage mask;       // sampled, optional per-pixel strength 0..1 (image null: everywhere)
    float jitter_x;         // render pixels
    float jitter_y;
    float camera_near;
    float camera_far;
    float camera_fov;       // vertical, radians
    float exposure;         // colour scale to scene light; 1 for tonemapped colour
    float structure_intensity; // 0..1: fine detail
    float tone_intensity;      // 0..1: lighting and colour; 0 keeps the game's grading
    int32_t depth_inverted;
    int32_t reset;
    // As BbDlssgEvaluate: row-major, row vectors, D3D clip space; has_matrices 0: still camera.
    int32_t has_matrices;
    float view_to_clip[4][4];
    float clip_to_prev_clip[4][4];
    float prev_clip_to_clip[4][4];
} BbDlssNrEvaluate;

typedef struct BbDlssApi {
    uint32_t abi;
    // UTF-16 paths: the directory with nvngx_dlss.dll, and a writable data directory.
    int32_t (*Configure)(const wchar_t* dll_directory, const wchar_t* data_directory,
                         BbDlssLogFn log);
    // Vulkan extensions NGX needs (DLSS and, when the GPU has it, Frame Generation). The arrays
    // stay valid until Shutdown.
    int32_t (*InstanceExtensions)(uint32_t* count, const VkExtensionProperties** extensions);
    int32_t (*DeviceExtensions)(VkInstance instance, VkPhysicalDevice physical, uint32_t* count,
                                const VkExtensionProperties** extensions);
    int32_t (*Initialize)(VkInstance instance, VkPhysicalDevice physical, VkDevice device,
                          PFN_vkGetInstanceProcAddr get_instance_proc,
                          PFN_vkGetDeviceProcAddr get_device_proc);
    int32_t (*CreateFeature)(VkCommandBuffer command, const BbDlssFeature* feature);
    int32_t (*Evaluate)(VkCommandBuffer command, const BbDlssEvaluate* evaluate);
    // The caller must have waited for the GPU work that used the feature.
    void (*ReleaseFeature)(void);
    void (*Shutdown)(void);
    // ABI 2. Frames Frame Generation can make per pair of rendered frames after Initialize:
    // 0 unavailable, 1 (2x), 3 (up to 4x, GeForce RTX 50).
    int32_t (*FrameGenMaxCount)(void);
    int32_t (*FrameGenCreate)(VkCommandBuffer command, const BbDlssgFeature* feature);
    // Call multi_frame_count times per rendered frame, multi_frame_index 1, 2, ...
    int32_t (*FrameGenEvaluate)(VkCommandBuffer command, const BbDlssgEvaluate* evaluate);
    // The caller must have waited for the GPU work that used the feature.
    void (*FrameGenRelease)(void);
    // ABI 3. 1 when DLSS 5 neural rendering can run on this device after Initialize, else 0.
    int32_t (*NeuralRenderSupported)(void);
    int32_t (*NeuralRenderCreate)(VkCommandBuffer command, const BbDlssNrFeature* feature);
    int32_t (*NeuralRenderEvaluate)(VkCommandBuffer command, const BbDlssNrEvaluate* evaluate);
    // The caller must have waited for the GPU work that used the feature.
    void (*NeuralRenderRelease)(void);
} BbDlssApi;

typedef const BbDlssApi* (*BbDlssGetApiFn)(void);

#ifdef __cplusplus
}
#endif
