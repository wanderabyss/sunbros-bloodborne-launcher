// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: user settings changed at run time from the in-game menu (bbport_overlay.h) and kept
// in bbport.ini (BB_CONFIG overrides the path). Environment variables override the file at
// start. Readers load the atomics every frame; writers are the menu and Load().

#pragma once

#include <atomic>
#include <cstddef>
#include <chrono>
#include <cstdint>

#include "bbport_dlss_models.h"

namespace BbSettings {

enum Upscaler : int { UpscalerOff = 0, UpscalerFsr3 = 1, UpscalerFsr4 = 2, UpscalerFsr411 = 3,
                      UpscalerTaa = 4, UpscalerDlss = 5, UpscalerCount };
/// FSR 4 v07 or FSR 4.1.1: the same inputs, settings and placement in the frame.
inline bool IsFsr4(int upscaler) {
    return upscaler == UpscalerFsr4 || upscaler == UpscalerFsr411;
}
enum Preset : int { NativeAA = 0, Quality, Balanced, Performance, UltraPerformance, PresetCount };
/// The ray tracing views (vk_rt_effects.h DrawDebugView) need ray tracing on: its AO term and
/// moon light as the game lights with them, what it changed in them, and its scene.
enum DebugView : int { DebugNone = 0, DebugReactive = 1, DebugMotion = 2, DebugRtAo = 3,
                       DebugRtShadow = 4, DebugRtChange = 5, DebugRtScene = 6, DebugViewCount };
inline bool IsRtView(int view) {
    return view >= DebugRtAo && view <= DebugRtScene;
}
/// Frame generation (vk_frame_generation.h): frames generated between two of the game's.
enum FrameGen : int { FrameGenOff = 0, FrameGenFsr3 = 1, FrameGenDlss = 2, FrameGenCount };
// DLSS model (enum DlssModel, DlssModelPresets, the menu's labels and order): bbport_dlss_models.h,
// generated from scripts/dlss_models.tsv with the launcher's copy. Auto (the default) is what the
// card runs best per quality mode (bbport_nvidia_gpu.h BbDlssAutoPreset).
/// NVIDIA Reflex Low Latency (vk_reflex.h, VK_NV_low_latency2): off, on, on with boost (the GPU
/// keeps its clocks up).
enum ReflexMode : int { ReflexOff = 0, ReflexOn, ReflexBoost, ReflexModeCount };
/// What runs DLSS 5 (neural rendering, experimental): nothing; the community bridge (route A:
/// ReShade with dlss5-bridge, run.py sets BB_DLSS5_ROUTE_A=1); NVIDIA's own (route B, later).
enum Dlss5Backend : int { Dlss5None = 0, Dlss5Bridge, Dlss5Native };

/// Effective Reflex mode: DLSS Frame Generation requires Reflex On minimum.
inline int EffectiveReflexMode(int requested_reflex, int requested_or_active_fg) {
    if (requested_or_active_fg == FrameGenDlss) {
        return requested_reflex == ReflexBoost ? ReflexBoost : ReflexOn;
    }
    return requested_reflex;
}
/// A ray-traced effect's quality (bbport.ini rt_ao_quality, rt_shadow_quality): Off keeps the
/// game's own (SSAO, the shadow map). What each tier traces: bbport_settings.cpp AoTiers,
/// ShadowTiers.
enum RtTier : int { TierOff = 0, TierLow, TierMedium, TierHigh, TierUltra, TierCount };
/// The one ray tracing setting (bbport.ini ray_tracing), as Elden Ring's *Ray Tracing Quality*:
/// Off; Low (AO Medium); Medium (AO Medium, moon shadows Low); High (AO Medium, moon shadows
/// Medium); Ultra (both Ultra); Custom (rt_ao_quality, rt_shadow_quality, rt_ao_strength). It
/// applies at the next frame.
enum RayTracingQuality : int { RtOff = 0, RtLow, RtMedium, RtHigh, RtUltra, RtCustom, RtQualityCount };
/// How far ray-traced AO looks (bbport.ini rt_ao_reach; Custom): the tier's own reach, or wide
/// (2.5 m) or wider (4 m) for large shapes - under bridges, eaves, alleys, doorways - with at
/// least 2 rays a pixel.
enum AoReach : int { AoReachTier = 0, AoReachWide, AoReachWider, AoReachCount };
/// What a ray_tracing level turns on (RayTracingEffective).
struct RayTracingEffect {
    bool ao = false;
    float ao_radius = 1.0f; ///< metres
    int ao_rays = 1;
    float ao_strength = 1.0f; ///< 0..2: above 1 the AO is raised to that power (darker)
    bool ao_combine = false;  ///< multiplied with the game's SSAO instead of replacing it
    bool ao_full = false;     ///< traced at the render size (else half, as the game's SSAO)
    float ao_direct = 0.0f;   ///< share of the AO also on the moon's light, 0..1
    bool shadows = false;
    bool shadow_replace = false; ///< ray traced only: replaces the game's (else multiplies it)
    float shadow_reach = 4.0f; ///< metres
    int shadow_rays = 1;
    bool shadow_half = false;  ///< traced at half size, upsampled
    bool secondary_lights = false; ///< dynamic secondary point lights (torches & lanterns)
    bool reflections = false;      ///< screen-space / ray-traced water & puddle reflections
};

/// Game effects switched by the community patches at start (patches.py EFFECTS): ini key,
/// menu label, default (the game's own behaviour).
struct Effect {
    const char* key;
    const char* label;
    bool default_on;
};
inline constexpr Effect Effects[] = {
    {"effect_chromatic_aberration", "Chromatic aberration", true},
    {"effect_dof", "Depth of field (DoF)", true},
    {"effect_motion_blur", "Motion blur", true},
    {"effect_ssao", "Ambient occlusion (SSAO)", true},
    {"effect_game_aa", "Game anti-aliasing", true},
    {"effect_dynamic_shadows", "Dynamic shadows", true},
    {"effect_ssr", "Screen-space reflections (SSR)", false},
    {"skip_intro", "Skip intro logos and movie", false},
    {"debug_camera", "Free camera (Cross + L3)", false},
    {"debug_menu", "Debug menu (requires font files)", false},
    {"cheat_no_death", "Cheat: never die (minimum 1 HP)", false},
    {"cheat_stealth", "Cheat: enemies cannot see you", false},
    {"cheat_silent", "Cheat: enemies cannot hear you", false},
    {"cheat_rally_no_decay", "Cheat: Rally never decays", false},
    {"cheat_enemy_control", "Cheat: control targeted enemy (R3 / L3)", false},
    {"cheat_no_stamina", "Cheat: no stamina use", false},
    {"cheat_stamina_out_of_combat", "Cheat: no stamina use out of combat", false},
    {"tweak_no_rally", "Disable Rally (health recovery)", false},
    {"tweak_camera_distance", "Increase camera distance", false},
    {"tweak_no_camera_rotation", "Disable automatic camera rotation", false},
    {"tweak_easy_run", "Run with less stick tilt", false},
    {"tweak_ragdoll", "Dark Souls-style ragdoll physics", false},
    // PC enhancements (scripts/enhancements.py, after bbhost): game files made at start. Off
    // keeps the game as it shipped. Kept last: the menu lists them in their own section.
    {"pc_mirror_appearance", "Hunter's Dream mirror: change appearance", false},
    {"pc_two_invaders", "Two invaders in the late areas (every player needs it)", false},
    {"pc_rebirth", "Rebirth in the Nightmare at the Altar of Despair", false},
    {"pc_enhanced_lamps", "Lamps: Level Up and Storage at every lit lamp", false},
};
inline constexpr int EffectCount = int(sizeof(Effects) / sizeof(Effects[0]));
inline constexpr int EnhancementCount = 4;
inline constexpr int FirstEnhancement = EffectCount - EnhancementCount;
/// Live output resolutions: the upscaler's output and the UI host targets.
// Last slot retains a validated custom resolution loaded from the launcher/ini.
// Wider than 16:9 (2560x1080 .. 5120x1440, 3840x1600, 3840x1080): camera and HUD patched at start
// (patches.py ultrawide_writes); src/pc_menu.c names them by index.
inline int OutputWidths[] = {1280,1920,2560,3840,1280,2560,3440,5120,5120,1080,3840,3840,1920,1920};
inline int OutputHeights[] = {720,1080,1440,2160,800,1080,1440,1440,2160,1920,1600,1080,1200,1080};
inline constexpr int OutputCount = sizeof(OutputWidths) / sizeof(OutputWidths[0]);
inline constexpr int OutputCustom = OutputCount - 1;
inline constexpr int OutputDefault = 1; ///< 1920x1080, the game's own size
/// DLSS 5 neural rendering runs at the output size: above 1.5x the pixels of 2560x1440 (4K and
/// up) it costs 14-16 ms a frame on an RTX 4090 and 60 FPS is out of reach whatever the upscaling
/// preset or ray tracing (the launcher's dlss5_output_warning uses the same line).
inline bool Dlss5OutputTooLarge(int output_res) {
    if (output_res < 0 || output_res >= OutputCount) {
        return false;
    }
    return static_cast<long long>(OutputWidths[output_res]) * OutputHeights[output_res] >
           2560LL * 1440 * 3 / 2;
}

/// How the presenter scales the finished output-resolution picture to the display's size
/// (bbport.ini present_upscale = easu | linear, BB_PRESENT_UPSCALE). EASU is AMD FidelityFX
/// FSR 1's edge-adaptive upscale, only used when the picture is smaller than the display;
/// equal sizes keep the plain path and larger pictures (downscaling) the bilinear one.
enum PresentUpscale : int { PresentUpscaleEasu = 0, PresentUpscaleLinear, PresentUpscaleCount };
inline const char* PresentUpscaleName(int mode) {
    return mode == PresentUpscaleLinear ? "linear" : "easu";
}
/// FSR 1 RCAS after EASU, in FSR's stops (bbport.ini present_rcas, BB_PRESENT_RCAS): each stop
/// halves the sharpening. 0 here switches RCAS off (FSR's own 0, its maximum, is about 0.01).
/// Off by default: the upscaler's own sharpening already ran, and RCAS 0.2 on top of it looked
/// over-sharpened in the DLSS 5 A/B.
inline constexpr float PresentRcasDefault = 0.0f;
inline constexpr float PresentRcasMax = 4.0f;
/// DLSS texture mip offset by default: NVIDIA's DLSS guide asks for a scene LOD bias of
/// log2(render / output) - 1. In a 12-area A/B on an RTX 4090
/// -1 resolved finer texture detail with no measured GPU cost; 0 keeps the old, softer look.
inline constexpr float DlssMipOffsetDefault = -1.0f;
/// Whether the presenter upscales a `src` picture into a `dst` one with FSR 1 EASU: only for
/// a real upscale (no axis larger, one smaller) and only when EASU is chosen.
inline bool PresentUsesEasu(int mode, unsigned src_w, unsigned src_h, unsigned dst_w,
                            unsigned dst_h) {
    if (mode != PresentUpscaleEasu || !src_w || !src_h || !dst_w || !dst_h) {
        return false;
    }
    return src_w <= dst_w && src_h <= dst_h && (src_w < dst_w || src_h < dst_h);
}
/// Whether RCAS follows EASU for a present_rcas value (stops; 0 or less is off).
inline bool PresentUsesRcas(float stops) {
    return stops > 0.0f;
}

/// HDR output's brightness (post_process.frag ToneMapBloodborneHDR): the nits of the game's SDR
/// white (bbport.ini hdr_white_nits, BB_HDR_WHITE), the ceiling highlights roll off to
/// (hdr_peak_nits, BB_HDR_PEAK; the shoulder starts at 60% of it) and how far highlights above
/// half white are expanded (hdr_highlight_boost, BB_HDR_BOOST, 0..1 of the 6.5x expansion).
/// 0 for white or peak takes the display's (Windows' SDR content brightness, the display's
/// peak; WindowSDL::ReadHdrLevels). The defaults are the fixed values used before 3.4.1.
inline constexpr float HdrWhiteDefault = 120.0f, HdrWhiteMin = 80.0f, HdrWhiteMax = 400.0f;
inline constexpr float HdrPeakDefault = 1000.0f, HdrPeakMin = 400.0f, HdrPeakMax = 4000.0f;
inline constexpr float HdrBoostDefault = 1.0f;
struct HdrLevels {
    float white_nits, peak_nits, boost;
};
/// The levels the shader gets: the setting, or the display's for 0 (the default when the
/// display reports none), clamped; the peak is never below white.
inline HdrLevels ResolveHdrLevels(float white, float peak, float boost, float display_white,
                                  float display_peak) {
    auto clamp = [](float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; };
    float w = white > 0.0f ? white : display_white > 0.0f ? display_white : HdrWhiteDefault;
    float p = peak > 0.0f ? peak : display_peak > 0.0f ? display_peak : HdrPeakDefault;
    w = clamp(w, HdrWhiteMin, HdrWhiteMax);
    p = clamp(p, HdrPeakMin, HdrPeakMax);
    return {w, p < w ? w : p, clamp(boost, 0.0f, 1.0f)};
}

/// Bounded runtime status channel: actual upscaler, FG provider, fallback reason, HDR mode,
/// and measured rates. Defines disconnected/stale states (> 2000 ms since last presented tick).
struct RuntimeStatus {
    std::atomic<int64_t> last_update_ms{0};
    std::atomic<int> active_upscaler{UpscalerOff};
    std::atomic<int> active_preset{NativeAA};
    std::atomic<unsigned> active_dlss_preset{0};
    std::atomic<const char*> upscaler_problem{nullptr};
    std::atomic<int> active_frame_gen{FrameGenOff};
    std::atomic<int> active_frame_gen_multiplier{1};
    std::atomic<const char*> frame_gen_fallback_reason{nullptr};
    std::atomic<const char*> frame_gen_inactive_reason{nullptr};
    std::atomic<uint64_t> dlss_frame_gen_pairs{0};
    std::atomic<uint64_t> fsr_frame_gen_pairs{0};
    std::atomic<uint64_t> generated_frames{0};
    std::atomic<uint64_t> presented_generated_frames{0};
    std::atomic<int> effective_reflex{ReflexOff};
    std::atomic<bool> reflex_forced_by_fg{false};
    std::atomic<float> reflex_latency_ms{0.0f};
    std::atomic<bool> hdr_swapchain_active{false};
    std::atomic<float> measured_render_fps{0.0f};
    std::atomic<float> measured_present_fps{0.0f};
    std::atomic<float> measured_frame_time_ms{0.0f};

    // Called on the generation thread. Automatic fallback updates the observed selection
    // itself, so it is not mistaken for a new user request on the next frame.
    bool ObserveFrameGenRequest(int configured) noexcept {
        if (configured == observed_frame_gen) return false;
        observed_frame_gen = configured;
        frame_gen_fallback_reason.store(nullptr, std::memory_order_relaxed);
        ClearFrameGeneration("provider changed");
        return true;
    }

    void ClearFrameGeneration(const char* reason) noexcept {
        active_frame_gen.store(FrameGenOff, std::memory_order_relaxed);
        active_frame_gen_multiplier.store(1, std::memory_order_relaxed);
        frame_gen_inactive_reason.store(reason, std::memory_order_relaxed);
    }

    void FrameGenFallback(int next_provider, const char* reason) noexcept {
        observed_frame_gen = next_provider;
        frame_gen_fallback_reason.store(reason, std::memory_order_relaxed);
        // The fallback is only a selection until it successfully generates a pair.
        ClearFrameGeneration("provider failed; waiting for fallback");
    }

    bool RecordFrameGeneration(int provider, uint32_t count) noexcept {
        if (!count) {
            ClearFrameGeneration("no frames generated");
            return false;
        }
        active_frame_gen.store(provider, std::memory_order_relaxed);
        active_frame_gen_multiplier.store(int(count) + 1, std::memory_order_relaxed);
        frame_gen_inactive_reason.store(nullptr, std::memory_order_relaxed);
        if (provider == FrameGenDlss) {
            frame_gen_fallback_reason.store(nullptr, std::memory_order_relaxed);
        }
        generated_frames.fetch_add(count, std::memory_order_relaxed);
        auto& pairs = provider == FrameGenDlss ? dlss_frame_gen_pairs : fsr_frame_gen_pairs;
        return pairs.fetch_add(1, std::memory_order_relaxed) == 0;
    }

    [[nodiscard]] bool IsActive(int64_t now_ms = 0) const noexcept {
        const int64_t last = last_update_ms.load(std::memory_order_relaxed);
        if (last == 0) {
            return false;
        }
        if (now_ms == 0) {
            now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                         std::chrono::steady_clock::now().time_since_epoch())
                         .count();
        }
        return now_ms >= last && (now_ms - last) < 2000;
    }

private:
    int observed_frame_gen{-1}; // generation-thread owned; readers use the atomic status fields
};

struct Values {
    mutable RuntimeStatus status;
    std::atomic<int> upscaler{UpscalerFsr3};
    std::atomic<int> preset{NativeAA};
    std::atomic<bool> sharpen{true};
    std::atomic<float> sharpness{0.3f};
    std::atomic<bool> jitter{true};
    std::atomic<bool> reactive{false};
    std::atomic<bool> object_motion{true};
    std::atomic<float> reactive_scale{1.0f};
    std::atomic<float> reactive_threshold{0.2f};
    std::atomic<float> reactive_max{0.9f};
    std::atomic<int> debug_view{DebugNone};
    /// Ray tracing compare (menu; not saved): the left half of the screen keeps the game's own
    /// AO and moon shadows (vk_rt_effects.h).
    std::atomic<bool> rt_compare{false};
    std::atomic<bool> show_fps{false};
    /// The window (the launcher's setting, BB_FULLSCREEN): the in-game PC menu changes it live
    /// and writes it back to the launcher's settings.json, not bbport.ini.
    std::atomic<bool> fullscreen{false};
    // FSR 4 checks (menu): the provider's auto exposure, the jitter sign it is given.
    std::atomic<bool> fsr4_auto_exposure{true};
    std::atomic<bool> fsr4_invert_jitter{false};
    /// Mouse camera (src/mouse_camera.c): the mouse turns the camera directly, 1:1, while the
    /// game window holds it (a click captures it). Sensitivity in tenths: 10 = 900 counts per
    /// radian. BB_MOUSE_CAMERA=0 turns it off.
    std::atomic<bool> mouse_camera{true};
    std::atomic<int> mouse_sensitivity{10};
    std::atomic<bool> mouse_invert_y{false};
    /// Locked on, a sideways flick of this many mouse counts (decaying over ~0.1 s) switches
    /// targets; 0 turns flicks off.
    std::atomic<int> mouse_flick_threshold{300};
    /// Menu pointer (src/menu_pointer.c): the mouse points and clicks in the game's menus.
    /// BB_MOUSE_MENU=0 turns it off.
    std::atomic<bool> mouse_menu{true};
    /// The cursor stays hidden over the game window, menus included (#88: for mouse-to-pad
    /// tools); the guide menu, the map and text entry still show it.
    std::atomic<bool> mouse_hide_cursor{false};
    std::atomic<int> active_render_width{1920}, active_render_height{1080};
    /// Applied at start (patches.py); the menu shows when a restart is needed.
    std::atomic<bool> effects[EffectCount]{};
    std::atomic<int> model_lod{0}; ///< -2 highest .. 2 lowest, 0 the game's
    /// Anisotropic filtering forced on the game's mipmapped textures: 2, 4, 8 or 16 samples;
    /// 0 keeps the game's own (anisotropy only where it asks for it). Applies at start.
    std::atomic<int> anisotropy{16};
    std::atomic<int> output_res{OutputDefault}; ///< index into OutputWidths
    std::atomic<bool> hdr{false};
    std::atomic<bool> hdr_supported{false};
    /// HDR brightness (HdrLevels), applied at the next frame; 0: the display's.
    std::atomic<float> hdr_white_nits{HdrWhiteDefault};
    std::atomic<float> hdr_peak_nits{HdrPeakDefault};
    std::atomic<float> hdr_highlight_boost{HdrBoostDefault};
    /// Live resolution and preset changes (run.sh): 0 off by default (startup patch, fastest
    /// on the Steam Deck and older GPUs), -1 auto (strong discrete GPUs), 1 on. On restart.
    std::atomic<int> live_resolution{0};
    /// Why FSR 4 cannot run (assets, device features), or null. Set by the renderer.
    std::atomic<const char*> fsr4_problem{nullptr};
    std::atomic<bool> fsr4_supported{false}, fsr411_supported{false};
    /// DLSS (bbport_dlss.dll, NVIDIA RTX) is ready, or why not (null before the device exists).
    std::atomic<bool> dlss_supported{false};
    std::atomic<const char*> dlss_problem{nullptr};
    /// The NGX render preset DLSS runs now (11 K, 10 J, 13 M, 12 L, 0 the driver's), for the
    /// menu to show what Auto picked.
    std::atomic<unsigned> dlss_preset_now{0};
    /// bbport_nvidia_gpu.h BbNvidiaGeneration of this GPU (0 before the device exists).
    std::atomic<int> nvidia_generation{0};
    /// DlssModel; a change makes the next frame create the DLSS feature again. Auto by default
    /// (files that name a model keep it).
    std::atomic<int> dlss_model{DlssModelAuto};
    /// DLSS scene texture LOD mip offset (-2.0 .. 0.0, default DlssMipOffsetDefault), added to
    /// log2(render / output) under DLSS. Applied live in TemporalUpscaler::SceneMipBias.
    std::atomic<float> dlss_mip_offset{DlssMipOffsetDefault};
    /// ReflexMode (applied at the next frame), and whether this GPU and driver have it.
    std::atomic<int> reflex{ReflexOff};
    std::atomic<bool> reflex_supported{false};
    /// DLSS 5 neural rendering, experimental (bbport.ini dlss5 = off | on, BB_DLSS5): off by
    /// default; the menu asks once before the first on (dlss5_confirmed). Takes effect at the
    /// next start (route A).
    std::atomic<bool> dlss5{false};
    std::atomic<bool> dlss5_confirmed{false};
    /// DLSS 5's look (route B, Dlss5::Inputs; decision D6), 0..1, applied at the next frame:
    /// Detail is Structure Intensity (fine detail, default half; bbport.ini dlss5_detail,
    /// BB_DLSS5_DETAIL); Colour change is Tone Intensity (lighting and colour, default 0, which
    /// keeps Bloodborne's grading; dlss5_tone, BB_DLSS5_TONE).
    std::atomic<float> dlss5_detail{0.5f};
    std::atomic<float> dlss5_tone{0.0f};
    /// The presenter's scale to the display (PresentUpscale) and RCAS stops (0 = off). Read
    /// from the file and environment by Load; Save keeps the file's lines as they are.
    std::atomic<int> present_upscale{PresentUpscaleEasu};
    std::atomic<float> present_rcas{PresentRcasDefault};
    /// Runtime only: this GPU is offered it (BbDlss5Eligible, or BB_DLSS5_ANY_GPU=1 for tests),
    /// what runs it (Dlss5Backend), whether it runs now, run.py's reason it cannot
    /// (BB_DLSS5_PROBLEM: files missing, the last start crashed), and the game frames are slower
    /// than 60 FPS with it on (the guard).
    std::atomic<bool> dlss5_eligible{false};
    std::atomic<int> dlss5_backend{Dlss5None};
    std::atomic<bool> dlss5_active{false};
    std::atomic<const char*> dlss5_problem{nullptr};
    std::atomic<bool> dlss5_slow{false};
    /// Ray tracing (vk_ray_tracing.h): the quality level (RayTracingQuality), and for Custom the
    /// ambient occlusion and moon shadow tiers (RtTier) and the AO's options (RayTracingEffect:
    /// combine, reach, full size and the share on moonlight). The AO's strength (0..2) applies at
    /// every level. ray_tracing_supported: this GPU and driver can (set by the renderer).
    std::atomic<int> ray_tracing{RtOff};
    std::atomic<int> rt_ao_quality{TierOff};
    std::atomic<int> rt_shadow_quality{TierOff};
    std::atomic<float> rt_ao_strength{1.0f};
    std::atomic<bool> rt_ao_combine{false};
    std::atomic<int> rt_ao_reach{AoReachTier};
    std::atomic<bool> rt_ao_full{false};
    std::atomic<float> rt_ao_direct{0.0f};
    std::atomic<bool> rt_shadow_replace{false};
    std::atomic<int> rt_shadow_half{-1}; ///< -1 follow tier, 0 full resolution, 1 half resolution
    /// Custom ray-traced moon shadow reach in metres (>0 overrides tier default, 1.0 .. 150.0).
    std::atomic<float> rt_shadow_reach_custom{0.0f};
    std::atomic<bool> rt_secondary_lights{false}; ///< dynamic secondary point lights (torches & lanterns)
    std::atomic<bool> rt_reflections{false};      ///< screen-space / ray-traced water reflections
    std::atomic<bool> ray_tracing_supported{false};
    /// Object motion has less room than ray tracing needs (BB_MOTION_BUDGET set lower): busy
    /// scenes miss objects.
    std::atomic<bool> ray_tracing_small_budget{false};
    /// Frame generation and the frames per game frame (2x with FSR 3.1, up to 4x with DLSS on
    /// RTX 50). dlssg_max_multiplier: 1 without DLSS Frame Generation.
    std::atomic<int> frame_gen{FrameGenOff};
    std::atomic<int> frame_gen_multiplier{2};
    /// At most the frames the display shows between two of the game's (an uncapped game then
    /// gets fewer generated frames, none above half the refresh rate); off: the multiplier as
    /// chosen. On by default (files that say 0 keep it off).
    std::atomic<bool> frame_gen_fit_display{true};
    std::atomic<int> dlssg_max_multiplier{1};
    std::atomic<const char*> frame_gen_problem{nullptr};
    /// Generated frames per game frame the display has room for now (0: paused), and its
    /// refresh rate (the presenter's measure, for the menu).
    std::atomic<int> frame_gen_now{0};
    std::atomic<int> frame_gen_display_hz{0};
    /// The game's own frame rate (presenter, game frames only), shown beside the total when
    /// frame generation adds frames.
    std::atomic<float> game_fps{0.0f};
    /// The game's frame rate cap frame generation needs (VideoOut applies it), 0 for none: with
    /// FIFO presentation (V-Sync; AMD has no Mailbox) at most refresh / (generated + 1), or each
    /// extra frame waits for the display and generation pauses.
    std::atomic<int> frame_gen_flip_limit{0};

    /// Startup settings for the explicit BB_RENDER_RES compatibility patch only.
    int startup_preset = NativeAA;
    int startup_upscaler = UpscalerFsr3;
    bool startup_object_motion = true;
    bool startup_effects[EffectCount]{};
    int startup_model_lod = 0;
    int startup_anisotropy = 16;
    int startup_output_res = OutputDefault;
    int startup_live_resolution = 0;
    int startup_ray_tracing = RtOff;
    bool startup_dlss5 = false;
};

Values& Get();

/// Reads the file, then the environment overrides. Called once at start.
void Load();
/// Checks the loaded choice before the first frame; unsupported FSR 4 uses FSR 3.1.
void ConfigureUpscalerSupport(bool fsr4, bool fsr411);
/// After device creation: DLSS availability; a DLSS setting falls back to FSR 3.1 without it.
void ConfigureDlssSupport(bool available, const char* problem);
/// After device creation: whether this GPU (`gpu`, its name) is offered DLSS 5, and why not
/// (`reason`); reads BB_DLSS5_ANY_GPU, BB_DLSS5 (the bridge is set up) and BB_DLSS5_PROBLEM.
/// `native`: the DLSS bridge runs NVIDIA's own DLSS 5 (ABI 3, Dlss::NeuralRenderAvailable),
/// preferred over the community bridge. Logs the "DLSS 5:" line.
void ConfigureDlss5(bool eligible, const char* reason, const char* gpu, bool native = false);
/// Why DLSS 5 cannot be switched on now, in the menu's order (the GPU; DLSS as the upscaler; a
/// fixed 60 FPS, `fps` as run.py's BB_FPS; nothing to run it; run.py's problem), written into
/// `text`; false when it can.
bool Dlss5Unavailable(const Values& v, const char* gpu, const char* fps, char* text,
                      size_t size);
/// The GPU name ConfigureDlss5 was given.
const char* Dlss5Gpu();
/// Startup-patched scene dimensions cannot change until run.sh prepares a new image.
bool FixedRenderSession();
int RenderPreset();
bool ResolutionNeedsRestart();
/// Camera and HUD aspect changes require new guest patches on restart.
bool AspectNeedsRestart();
/// Writes the file (menu changes).
void Save();

/// Render resolution divisor of a preset (1.0 native, 1.5 quality, ...).
float PresetScale(int preset);
const char* PresetName(int preset);
const char* UpscalerName(int upscaler);
const char* FrameGenName(int frame_gen);
/// bbport.ini dlss_model= of a model (DlssModelIniNames: "default", "K", ..., "auto").
const char* DlssModelName(int model);
/// "off", "on", "boost" (bbport.ini reflex).
const char* ReflexName(int mode);
/// "off", "low", "medium", "high", "ultra" (bbport.ini rt_ao_quality, rt_shadow_quality).
const char* RtTierName(int tier);
/// "tier", "wide", "wider" (bbport.ini rt_ao_reach).
const char* AoReachName(int reach);
/// "off", "low", "medium", "high", "ultra", "custom" (bbport.ini ray_tracing; "maximum" is
/// read as ultra).
const char* RayTracingName(int quality);
/// The ambient occlusion and moon shadow tiers a ray_tracing level uses (Custom: its keys).
void RayTracingTiers(int quality, int& ao, int& shadows);
/// Switching to Custom from `level`, given the Custom choices (tiers and AO strength): with
/// both tiers Off, Custom starts from what the level traces at full strength; otherwise it keeps
/// them. True when it changed them. The launcher does the same (bbport_launcher_win.py
/// custom_start).
bool CustomStart(int level, int& ao, int& shadows, float& strength);
/// What the current ray_tracing level turns on.
RayTracingEffect RayTracingEffective();
/// Default shadow reach for a tier in metres (Low: 6.0, Medium/High: 15.0, Ultra: 40.0).
float ShadowTierReach(int tier);
/// Whether a ray-traced effect was chosen at start.
bool RayTracingWanted();

} // namespace BbSettings
