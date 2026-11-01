// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_settings.h"

#include <algorithm>
#include <cctype>
#include <charconv>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>
#include <filesystem>
#include <fstream>
#include <nlohmann/json.hpp>

namespace BbSettings {

namespace {

bool ray_tracing_seen = false; ///< Load: the file or environment set ray_tracing
/// BB_RENDER_RES is set: read by Load (or the first FixedRenderSession), not every frame.
std::atomic<int> fixed_render_session{-1};
bool ReadFixedRenderSession() {
    const char* size = std::getenv("BB_RENDER_RES");
    return size && size[0];
}

/// Load: the ray tracing keys before the tiers (ambient_occlusion, shadows, rt_ao_radius,
/// rt_ao_rays, rt_shadow_reach), turned into the nearest tier when the file has none.
struct LegacyRt {
    static constexpr float DefaultRadius = 1.0f, DefaultReach = 4.0f, DefaultRays = 1.0f;
    bool ao_tier_seen = false, shadow_tier_seen = false;
    int ao = -1, shadows = -1; ///< 1 raytraced, 0 game, -1 not set
    float ao_radius = DefaultRadius, shadow_reach = DefaultReach, ao_rays = DefaultRays;
} legacy_rt;

/// The number `value` holds when all of it is one, else `fallback`: a malformed value is the
/// default, as the launcher reads it (bbport_launcher_win.py migrate_ray_tracing).
float ParseNumber(const std::string& value, float fallback) {
    char* end = nullptr;
    const float number = std::strtof(value.c_str(), &end);
    return end != value.c_str() && *end == 0 ? number : fallback;
}

int ParseTier(const std::string& value, int fallback) {
    for (int t = 0; t < TierCount; ++t) {
        if (value == RtTierName(t)) {
            return t;
        }
    }
    return fallback;
}

const char* Path() {
    const char* env = std::getenv("BB_CONFIG");
    return env && env[0] ? env : "bbport.ini";
}

float Clamp(float v, float lo, float hi) {
    return std::clamp(v, lo, hi);
}

void Set(Values& v, const std::string& key, const std::string& value) {
    const float f = float(std::atof(value.c_str()));
    const int i = std::atoi(value.c_str());
    if (key == "upscaler") {
        for (int u = 0; u < UpscalerCount; ++u) {
            if (value == UpscalerName(u)) {
                v.upscaler = u;
            }
        }
    } else if (key == "frame_gen") {
        for (int g = 0; g < FrameGenCount; ++g) {
            if (value == FrameGenName(g) || value == std::to_string(g)) {
                v.frame_gen = g;
            }
        }
    } else if (key == "dlss_model") {
        for (int m = 0; m < DlssModelCount; ++m) {
            const char* name = DlssModelName(m);
            if (value.size() == std::strlen(name) &&
                std::equal(value.begin(), value.end(), name, [](char a, char b) {
                    return std::tolower(static_cast<unsigned char>(a)) ==
                           std::tolower(static_cast<unsigned char>(b));
                })) {
                v.dlss_model = m;
            }
        }
    } else if (key == "dlss_mip_offset" || key == "dlss_mip_bias") {
        v.dlss_mip_offset = Clamp(f, -2.0f, 0.0f);
    } else if (key == "reflex") {
        for (int m = 0; m < ReflexModeCount; ++m) {
            if (value == ReflexName(m)) {
                v.reflex = m;
            }
        }
    } else if (key == "dlss5") {
        if (value == "on" || value == "1") {
            v.dlss5 = true;
        } else if (value == "off" || value == "0") {
            v.dlss5 = false;
        }
    } else if (key == "dlss5_confirmed") {
        v.dlss5_confirmed = value == "1";
    } else if (key == "dlss5_detail") {
        v.dlss5_detail = Clamp(f, 0.0f, 1.0f);
    } else if (key == "dlss5_tone") {
        v.dlss5_tone = Clamp(f, 0.0f, 1.0f);
    } else if (key == "present_upscale") {
        if (value == "easu" || value == "fsr1" || value == "auto") {
            v.present_upscale = PresentUpscaleEasu;
        } else if (value == "linear" || value == "bilinear") {
            v.present_upscale = PresentUpscaleLinear;
        }
    } else if (key == "present_rcas") {
        if (value == "off") {
            v.present_rcas = 0.0f;
        } else {
            // A malformed value keeps the current one; 0 or less is off.
            const float stops = ParseNumber(value, v.present_rcas.load());
            v.present_rcas = stops > 0.0f ? std::min(stops, PresentRcasMax) : 0.0f;
        }
    } else if (key == "ray_tracing") {
        for (int m = 0; m < RtQualityCount; ++m) {
            if (value == RayTracingName(m) || (m == RtUltra && value == "maximum")) {
                v.ray_tracing = m;
                ray_tracing_seen = true;
            }
        }
    } else if (key == "rt_ao_quality") {
        v.rt_ao_quality = ParseTier(value, v.rt_ao_quality);
        legacy_rt.ao_tier_seen |= value == RtTierName(v.rt_ao_quality);
    } else if (key == "rt_shadow_quality") {
        v.rt_shadow_quality = ParseTier(value, v.rt_shadow_quality);
        legacy_rt.shadow_tier_seen |= value == RtTierName(v.rt_shadow_quality);
    } else if (key == "rt_shadow_half") {
        v.rt_shadow_half = i;
    } else if (key == "rt_shadow_reach_custom") {
        v.rt_shadow_reach_custom = Clamp(f, 0.0f, 150.0f);
    } else if (key == "rt_secondary_lights") {
        v.rt_secondary_lights = i != 0;
    } else if (key == "rt_reflections") {
        v.rt_reflections = i != 0;
    } else if (key == "hdr") {
        v.hdr = i != 0;
    } else if (key == "hdr_white_nits" || key == "hdr_peak_nits") {
        // "display" (or 0) follows the display; anything else is nits, clamped.
        const bool white = key == "hdr_white_nits";
        auto& level = white ? v.hdr_white_nits : v.hdr_peak_nits;
        float nits = value == "display" ? 0.0f : ParseNumber(value, level.load());
        nits = std::isnan(nits) ? level.load() : nits;
        level = nits <= 0.0f ? 0.0f
                : white      ? Clamp(nits, HdrWhiteMin, HdrWhiteMax)
                             : Clamp(nits, HdrPeakMin, HdrPeakMax);
    } else if (key == "hdr_highlight_boost") {
        v.hdr_highlight_boost = value == "off"      ? 0.0f
                                : value == "low"    ? 0.33f
                                : value == "medium" ? 0.67f
                                : value == "high"   ? 1.0f
                                                    : ParseNumber(value, v.hdr_highlight_boost.load());
        if (std::isnan(v.hdr_highlight_boost.load())) {
            v.hdr_highlight_boost = HdrBoostDefault;
        }
        v.hdr_highlight_boost = Clamp(v.hdr_highlight_boost.load(), 0.0f, 1.0f);
    } else if (key == "rt_ao_strength") {
        v.rt_ao_strength = Clamp(f, 0.0f, 2.0f);
    } else if (key == "rt_ao_combine") {
        v.rt_ao_combine = i != 0;
    } else if (key == "rt_ao_reach") {
        for (int r = 0; r < AoReachCount; ++r) {
            if (value == AoReachName(r)) {
                v.rt_ao_reach = r;
            }
        }
    } else if (key == "rt_ao_full") {
        v.rt_ao_full = i != 0;
    } else if (key == "rt_ao_direct") {
        v.rt_ao_direct = Clamp(f, 0.0f, 1.0f);
    } else if (key == "rt_shadow_replace") {
        v.rt_shadow_replace = i != 0;
    } else if (key == "ambient_occlusion" || key == "shadows") {
        int& mode = key == "shadows" ? legacy_rt.shadows : legacy_rt.ao;
        mode = value == "raytraced" ? 1 : value == "game" ? 0 : mode;
    } else if (key == "rt_ao_radius") {
        legacy_rt.ao_radius = ParseNumber(value, LegacyRt::DefaultRadius);
    } else if (key == "rt_ao_rays") {
        legacy_rt.ao_rays = ParseNumber(value, LegacyRt::DefaultRays);
    } else if (key == "rt_shadow_reach") {
        legacy_rt.shadow_reach = ParseNumber(value, LegacyRt::DefaultReach);
    } else if (key == "frame_gen_multiplier") {
        v.frame_gen_multiplier = std::clamp(i, 2, 4);
    } else if (key == "frame_gen_fit_display") {
        v.frame_gen_fit_display = i != 0;
    } else if (key == "preset") {
        v.preset = std::clamp(i, 0, PresetCount - 1);
    } else if (key == "sharpen") {
        v.sharpen = i != 0;
    } else if (key == "sharpness") {
        v.sharpness = Clamp(f, 0.0f, 2.0f);
    } else if (key == "jitter") {
        v.jitter = i != 0;
    } else if (key == "reactive") {
        v.reactive = i != 0;
    } else if (key == "object_motion") {
        v.object_motion = i != 0;
    } else if (key == "reactive_scale") {
        v.reactive_scale = Clamp(f, 0.0f, 16.0f);
    } else if (key == "reactive_threshold") {
        v.reactive_threshold = Clamp(f, 0.0f, 1.0f);
    } else if (key == "reactive_max") {
        v.reactive_max = Clamp(f, 0.0f, 1.0f);
    } else if (key == "debug_view") {
        v.debug_view = std::clamp(i, 0, DebugViewCount - 1);
    } else if (key == "show_fps") {
        v.show_fps = i != 0;
    } else if (key == "fsr4_auto_exposure") {
        v.fsr4_auto_exposure = i != 0;
    } else if (key == "fsr4_invert_jitter") {
        v.fsr4_invert_jitter = i != 0;
    } else if (key == "mouse_camera") {
        v.mouse_camera = i != 0;
    } else if (key == "mouse_sensitivity") {
        v.mouse_sensitivity = std::clamp(i, 1, 50);
    } else if (key == "mouse_invert_y") {
        v.mouse_invert_y = i != 0;
    } else if (key == "mouse_flick_threshold") {
        v.mouse_flick_threshold = std::clamp(i, 0, 10000);
    } else if (key == "mouse_menu") {
        v.mouse_menu = i != 0;
    } else if (key == "mouse_hide_cursor") {
        v.mouse_hide_cursor = i != 0;
    } else if (key == "model_lod") {
        v.model_lod = std::clamp(i, -2, 2);
    } else if (key == "anisotropic_filtering") {
        v.anisotropy = value == "game" ? 0 : i >= 16 ? 16 : i >= 8 ? 8 : i >= 4 ? 4 : i >= 2 ? 2 : 0;
    } else if (key == "live_resolution") {
        v.live_resolution = value == "auto" ? -1 : std::clamp(i, 0, 1);
    } else if (key == "output_res") {
        // Any WxH from 256x144 to 7680x4320 (a listed size takes its index, another the custom
        // slot). An odd side is rounded down to even, as patches.py output_size does: 3682x2071
        // used to be rejected here and in run.py, so game, upscaler and window stayed 1080p.
        const auto separator = value.find('x');
        if (separator == std::string::npos) return;
        int w = 0, h = 0;
        const char* begin = value.data();
        const char* split = begin + separator;
        const char* end = begin + value.size();
        const auto width = std::from_chars(begin, split, w);
        const auto height = std::from_chars(split + 1, end, h);
        if (width.ec != std::errc{} || width.ptr != split || height.ec != std::errc{} ||
            height.ptr != end) {
            return;
        }
        w &= ~1;
        h &= ~1;
        if (w < 256 || w > 7680 || h < 144 || h > 4320) return;
        for (int r = 0; r < OutputCustom; ++r) {
            if (OutputWidths[r] == w && OutputHeights[r] == h) {
                v.output_res = r;
                return;
            }
        }
        OutputWidths[OutputCustom] = w;
        OutputHeights[OutputCustom] = h;
        v.output_res = OutputCustom;
    } else {
        for (int e = 0; e < EffectCount; ++e) {
            if (key == Effects[e].key) {
                v.effects[e] = i != 0;
            }
        }
    }
}

} // namespace

Values& Get() {
    static Values values;
    return values;
}

void Load() {
    auto& v = Get();
    ray_tracing_seen = false;
    legacy_rt = {};
    for (int e = 0; e < EffectCount; ++e) {
        v.effects[e] = Effects[e].default_on;
    }
    // Not written by Save (or only when changed): a file without them means the defaults.
    v.present_upscale = PresentUpscaleEasu;
    v.present_rcas = PresentRcasDefault;
    v.dlss_mip_offset = DlssMipOffsetDefault;
    v.hdr_white_nits = HdrWhiteDefault;
    v.hdr_peak_nits = HdrPeakDefault;
    v.hdr_highlight_boost = HdrBoostDefault;
    if (FILE* file = std::fopen(Path(), "r")) {
        char line[256];
        while (std::fgets(line, sizeof(line), file)) {
            std::string text{line};
            text.erase(text.find_last_not_of(" \t\r\n") + 1);
            const auto eq = text.find('=');
            if (text.empty() || text[0] == '#' || eq == std::string::npos) {
                continue;
            }
            Set(v, text.substr(0, eq), text.substr(eq + 1));
        }
        std::fclose(file);
        std::printf("Settings: %s\n", Path());
    }
    // Environment overrides (scripts, A/B tests).
    if (const char* env = std::getenv("BB_UPSCALER")) {
        v.upscaler = UpscalerOff;
        for (int u = 0; u < UpscalerCount; ++u) {
            if (std::strcmp(env, UpscalerName(u)) == 0) v.upscaler = u;
        }
    }
    const std::pair<const char*, const char*> env_keys[] = {
        {"BB_FSR_SHARPNESS", "sharpness"},        {"BB_JITTER", "jitter"},
        {"BB_REACTIVE", "reactive"},              {"BB_REACTIVE_SCALE", "reactive_scale"},
        {"BB_REACTIVE_THRESHOLD", "reactive_threshold"}, {"BB_REACTIVE_MAX", "reactive_max"},
        {"BB_UPSCALE_PRESET", "preset"},            {"BB_OBJECT_MOTION", "object_motion"},
        {"BB_PC_MIRROR", "pc_mirror_appearance"},   {"BB_PC_TWO_INVADERS", "pc_two_invaders"},
        {"BB_PC_REBIRTH", "pc_rebirth"},           {"BB_MOUSE_CAMERA", "mouse_camera"},
        {"BB_PC_LAMPS", "pc_enhanced_lamps"},         {"BB_PC_SOJIN", "pc_sojin_chikage"},
        {"BB_OUTPUT_RES", "output_res"},            {"BB_ANISO", "anisotropic_filtering"},
        {"BB_MOUSE_MENU", "mouse_menu"},
        {"BB_FRAME_GEN", "frame_gen"},              {"BB_FRAME_GEN_MULTIPLIER", "frame_gen_multiplier"},
        {"BB_FRAME_GEN_FIT_DISPLAY", "frame_gen_fit_display"},
        {"BB_DLSS_MODEL", "dlss_model"},
        {"BB_DLSS_MIP_OFFSET", "dlss_mip_offset"},
        {"BB_REFLEX", "reflex"},
        {"BB_DLSS5", "dlss5"},
        {"BB_DLSS5_DETAIL", "dlss5_detail"},     {"BB_DLSS5_TONE", "dlss5_tone"},
        {"BB_PRESENT_UPSCALE", "present_upscale"}, {"BB_PRESENT_RCAS", "present_rcas"},
        {"BB_HDR_WHITE", "hdr_white_nits"},       {"BB_HDR_PEAK", "hdr_peak_nits"},
        {"BB_HDR_BOOST", "hdr_highlight_boost"},
        {"BB_RT_AO_QUALITY", "rt_ao_quality"},       {"BB_RT_SHADOW_QUALITY", "rt_shadow_quality"},
        {"BB_RT_AO_STRENGTH", "rt_ao_strength"},     {"BB_RAY_TRACING", "ray_tracing"},
        {"BB_RT_AO_COMBINE", "rt_ao_combine"},       {"BB_RT_AO_REACH", "rt_ao_reach"},
        {"BB_RT_AO_FULL", "rt_ao_full"},             {"BB_RT_AO_DIRECT", "rt_ao_direct"},
        {"BB_RT_SHADOW_REPLACE", "rt_shadow_replace"},
        {"BB_RT_SHADOW_REACH_CUSTOM", "rt_shadow_reach_custom"},
        // The keys before the tiers, as in a file.
        {"BB_AMBIENT_OCCLUSION", "ambient_occlusion"}, {"BB_SHADOWS", "shadows"},
        {"BB_RT_AO_RADIUS", "rt_ao_radius"},         {"BB_RT_AO_RAYS", "rt_ao_rays"},
        {"BB_RT_SHADOW_REACH", "rt_shadow_reach"},
    };
    for (const auto& [env, key] : env_keys) {
        if (const char* value = std::getenv(env)) {
            Set(v, key, value);
        }
    }
    // The window mode is the launcher's setting, passed at start.
    const char* fullscreen = std::getenv("BB_FULLSCREEN");
    v.fullscreen = fullscreen && fullscreen[0] == '1';
    v.startup_preset = v.preset;
    v.startup_upscaler = v.upscaler;
    v.startup_object_motion = v.object_motion;
    // Files from before the tiers: the nearest tier to the rays, reach and length they chose
    // (AoTiers, ShadowTiers). Their moon shadows were traced at full size: past 6 m the
    // full-size tiers (High 15 m, Ultra 40 m). The launcher does the same (migrate_ray_tracing,
    // tests/data/rt_settings.txt).
    const auto& old = legacy_rt;
    if (!old.ao_tier_seen && old.ao >= 0) {
        v.rt_ao_quality = old.ao == 0              ? TierOff
                          : old.ao_rays >= 2       ? (old.ao_radius >= 1.25f ? TierUltra : TierHigh)
                          : old.ao_radius < 1.0f   ? TierLow
                                                   : TierMedium;
    }
    if (!old.shadow_tier_seen && old.shadows >= 0) {
        v.rt_shadow_quality = old.shadows == 0              ? TierOff
                              : old.shadow_reach <= 6.0f    ? TierLow
                              : old.shadow_reach <= 27.5f   ? TierHigh
                                                            : TierUltra;
    }
    // The variables for those keys only count for files without tiers: say so when one is set.
    static constexpr std::pair<const char*, bool> retired_env[] = {
        {"BB_AMBIENT_OCCLUSION", true}, {"BB_RT_AO_RADIUS", true}, {"BB_RT_AO_RAYS", true},
        {"BB_SHADOWS", false},          {"BB_RT_SHADOW_REACH", false}};
    for (const auto& [env, ao] : retired_env) {
        if (std::getenv(env) && (ao ? old.ao_tier_seen : old.shadow_tier_seen)) {
            std::printf("Settings: %s is retired and ignored (%s is set); use %s\n", env,
                        ao ? "rt_ao_quality" : "rt_shadow_quality",
                        ao ? "BB_RT_AO_QUALITY" : "BB_RT_SHADOW_QUALITY");
        }
    }
    // Files from before the quality level: the effects they chose are Custom.
    if (!ray_tracing_seen) {
        v.ray_tracing = v.rt_ao_quality != TierOff || v.rt_shadow_quality != TierOff ? RtCustom
                                                                                     : RtOff;
    }
    v.startup_ray_tracing = v.ray_tracing;
    for (int e = 0; e < EffectCount; ++e) {
        v.startup_effects[e] = v.effects[e];
    }
    v.startup_model_lod = v.model_lod;
    v.startup_anisotropy = v.anisotropy;
    v.startup_output_res = v.output_res;
    v.startup_live_resolution = v.live_resolution;
    v.startup_dlss5 = v.dlss5;
    fixed_render_session = ReadFixedRenderSession() ? 1 : 0;
}

void ConfigureUpscalerSupport(bool fsr4, bool fsr411) {
    auto& v = Get();
    v.fsr4_supported = fsr4;
    v.fsr411_supported = fsr4 && fsr411;
    const int requested = v.upscaler;
    if ((requested == UpscalerFsr4 && !v.fsr4_supported) ||
        (requested == UpscalerFsr411 && !v.fsr411_supported)) {
        v.fsr4_problem = "GPU does not support the selected FSR 4 shaders; using FSR 3.1";
        std::printf("Upscaler: %s unsupported on this GPU; falling back to FSR 3.1 before the first frame\n",
                    UpscalerName(requested));
        v.upscaler = UpscalerFsr3;
    }
}

void ConfigureDlssSupport(bool available, const char* problem) {
    auto& v = Get();
    v.dlss_supported = available;
    static std::string kept;
    kept = problem ? problem : "";
    v.dlss_problem = available || kept.empty() ? nullptr : kept.c_str();
    if (v.upscaler == UpscalerDlss && !available) {
        std::printf("Upscaler: DLSS unavailable (%s); falling back to FSR 3.1\n",
                    kept.empty() ? "bbport_dlss.dll or nvngx_dlss.dll missing" : kept.c_str());
        v.upscaler = UpscalerFsr3;
    }
}

namespace {
std::string dlss5_gpu;     ///< ConfigureDlss5's GPU name
std::string dlss5_problem; ///< BB_DLSS5_PROBLEM, kept for dlss5_problem
} // namespace

void ConfigureDlss5(bool eligible, const char* reason, const char* gpu, bool native) {
    auto& v = Get();
    dlss5_gpu = gpu ? gpu : "";
    const char* any = std::getenv("BB_DLSS5_ANY_GPU");
    v.dlss5_eligible = eligible || (any && any[0] == '1');
    // NVIDIA's own (route B) through the DLSS bridge when it runs it; else the community bridge
    // (route A), which run.py announces with BB_DLSS5_ROUTE_A=1 only with its files in place.
    // BB_DLSS5 is only the dlss5 setting's override (Load).
    const char* bridge = std::getenv("BB_DLSS5_ROUTE_A");
    const char* problem = std::getenv("BB_DLSS5_PROBLEM");
    dlss5_problem = problem ? problem : "";
    v.dlss5_problem = dlss5_problem.empty() ? nullptr : dlss5_problem.c_str();
    v.dlss5_backend = !v.dlss5_eligible                 ? Dlss5None
                      : native                          ? Dlss5Native
                      : bridge && bridge[0] == '1'      ? Dlss5Bridge
                                                        : Dlss5None;
    v.dlss5_active = v.dlss5 && v.dlss5_backend != Dlss5None && v.upscaler == UpscalerDlss;
    if (!v.dlss5_eligible) {
        std::printf("DLSS 5: not offered (%s; %s)\n", reason ? reason : "this GPU",
                    dlss5_gpu.c_str());
    } else if (v.dlss5_active) {
        std::printf("DLSS 5: on (%s)\n",
                    v.dlss5_backend == Dlss5Native ? "NVIDIA" : "community bridge");
    } else {
        std::printf("DLSS 5: off%s%s\n", v.dlss5_problem.load() ? " - " : "",
                    v.dlss5_problem.load() ? v.dlss5_problem.load() : "");
    }
}

const char* Dlss5Gpu() {
    return dlss5_gpu.c_str();
}

bool Dlss5Unavailable(const Values& v, const char* gpu, const char* fps, char* text,
                      size_t size) {
    if (!v.dlss5_eligible) {
        std::snprintf(text, size, "needs an RTX 4080, 4090 or newer desktop card (this PC: %s)",
                      gpu && gpu[0] ? gpu : "another GPU");
    } else if (v.upscaler != UpscalerDlss) {
        std::snprintf(text, size, "needs DLSS as the upscaler");
    } else if (!fps || std::string_view{fps} != "60") {
        std::snprintf(text, size, "needs a fixed 60 FPS (now: %s)",
                      fps && fps[0] ? (std::string_view{fps} == "uncap" ? "uncapped" : fps)
                                    : "uncapped");
    } else if (const char* problem = v.dlss5_problem.load()) {
        std::snprintf(text, size, "%s", problem);
    } else if (v.dlss5_backend == Dlss5None) {
        // No setup guide is shipped while the community bridge (route A) is paused.
        std::snprintf(text, size,
                      "waiting for NVIDIA: no DLSS 5 for RTX 40 in this driver yet, and the "
                      "community bridge is paused in this build");
    } else {
        return false;
    }
    return true;
}

bool FixedRenderSession() {
    if (fixed_render_session.load(std::memory_order_relaxed) < 0) {
        fixed_render_session = ReadFixedRenderSession() ? 1 : 0;
    }
    return fixed_render_session.load(std::memory_order_relaxed) == 1;
}

int RenderPreset() {
    const auto& v = Get();
    return FixedRenderSession() ? v.startup_preset :
        v.upscaler == UpscalerTaa ? NativeAA : v.preset.load();
}

bool AspectNeedsRestart() {
    const auto& v = Get();
    const int a = v.output_res, b = v.startup_output_res;
    return int64_t(OutputWidths[a]) * OutputHeights[b] !=
           int64_t(OutputWidths[b]) * OutputHeights[a];
}

bool ResolutionNeedsRestart() {
    const auto& v = Get();
    // TAA needs the live path (native guest targets): run.sh selects it on restart.
    return AspectNeedsRestart() || (FixedRenderSession() &&
        (v.preset != v.startup_preset || v.output_res != v.startup_output_res ||
         (v.upscaler == UpscalerOff) != (v.startup_upscaler == UpscalerOff) ||
         (v.upscaler == UpscalerTaa) != (v.startup_upscaler == UpscalerTaa)));
}

void Save() {
    const auto& v = Get();
    // Lines this function does not write (keys other tools own, such as pc_menu) are kept.
    std::vector<std::string> kept;
    if (FILE* old = std::fopen(Path(), "r")) {
        char line[256];
        while (std::fgets(line, sizeof(line), old)) {
            std::string text{line};
            text.erase(text.find_last_not_of(" \t\r\n") + 1);
            const auto eq = text.find('=');
            if (text.empty() || text[0] == '#' || eq == std::string::npos) continue;
            const std::string key = text.substr(0, eq);
            bool ours = false;
            for (const char* name : {"upscaler", "preset", "sharpen", "sharpness", "jitter", "reactive",
                                     "object_motion", "reactive_scale", "reactive_threshold", "reactive_max",
                                     "debug_view", "show_fps", "fsr4_auto_exposure", "fsr4_invert_jitter",
                                     "model_lod", "anisotropic_filtering",
                                     "output_res", "live_resolution",
                                     "mouse_camera", "mouse_sensitivity", "mouse_invert_y", "mouse_menu",
                                     "mouse_hide_cursor", "mouse_flick_threshold",
                                     // Also written below. Left out of this list they were kept
                                     // and written again: one more frame_gen block per save.
                                     "frame_gen", "frame_gen_multiplier", "frame_gen_fit_display",
                                     "dlss_model", "dlss_mip_offset", "dlss_mip_bias", "reflex",
                                     "dlss5", "dlss5_confirmed", "dlss5_detail", "dlss5_tone",
                                     "ray_tracing", "rt_ao_quality",
                                     "rt_shadow_quality", "rt_ao_strength", "rt_ao_combine",
                                     "rt_ao_reach", "rt_ao_full", "rt_ao_direct",
                                     "rt_shadow_replace", "rt_shadow_half", "rt_shadow_reach_custom",
                                     "rt_secondary_lights", "rt_reflections", "hdr",
                                     "hdr_white_nits", "hdr_peak_nits", "hdr_highlight_boost",
                                     // Before the tiers: read by Load, dropped here.
                                     "ambient_occlusion", "shadows", "rt_ao_radius", "rt_ao_rays",
                                     "rt_shadow_reach",
                                     // The removed HDR pass's brightness: dropped here.
                                     "hdr_paper_white", "hdr_peak"}) {
                ours |= key == name;
            }
            for (int e = 0; e < EffectCount; ++e) ours |= key == Effects[e].key;
            if (!ours) kept.push_back(text);
        }
        std::fclose(old);
    }
    FILE* file = std::fopen(Path(), "w");
    if (!file) {
        std::printf("Settings: cannot write %s\n", Path());
        return;
    }
    std::fprintf(file,
                 "# bbport settings (in-game menu: Insert / L3+R3)\n"
                 "upscaler=%s\npreset=%d\nsharpen=%d\nsharpness=%.2f\njitter=%d\n"
                 "reactive=%d\nobject_motion=%d\nreactive_scale=%.2f\nreactive_threshold=%.2f\nreactive_max=%.2f\n"
                 "debug_view=%d\nshow_fps=%d\nfsr4_auto_exposure=%d\nfsr4_invert_jitter=%d\n",
                 UpscalerName(v.upscaler), v.preset.load(), int(v.sharpen.load()),
                 v.sharpness.load(), int(v.jitter.load()), int(v.reactive.load()),
                 int(v.object_motion.load()),
                 v.reactive_scale.load(), v.reactive_threshold.load(), v.reactive_max.load(),
                 v.debug_view.load(), int(v.show_fps.load()),
                 int(v.fsr4_auto_exposure.load()), int(v.fsr4_invert_jitter.load()));
    std::fprintf(file, "mouse_camera=%d\nmouse_sensitivity=%d\nmouse_invert_y=%d\nmouse_menu=%d\n"
                       "mouse_hide_cursor=%d\nmouse_flick_threshold=%d\n",
                 int(v.mouse_camera.load()), v.mouse_sensitivity.load(), int(v.mouse_invert_y.load()),
                 int(v.mouse_menu.load()), int(v.mouse_hide_cursor.load()), v.mouse_flick_threshold.load());
    // Read by patches.py at start.
    for (int e = 0; e < EffectCount; ++e) {
        std::fprintf(file, "%s=%d\n", Effects[e].key, int(v.effects[e].load()));
    }
    std::fprintf(file, "frame_gen=%s\nframe_gen_multiplier=%d\nframe_gen_fit_display=%d\n",
                 FrameGenName(v.frame_gen), v.frame_gen_multiplier.load(),
                 int(v.frame_gen_fit_display.load()));
    std::fprintf(file, "dlss_model=%s\nreflex=%s\ndlss5=%s\ndlss5_confirmed=%d\n",
                 DlssModelName(v.dlss_model), ReflexName(v.reflex), v.dlss5 ? "on" : "off",
                 int(v.dlss5_confirmed.load()));
    std::fprintf(file, "dlss5_detail=%.2f\ndlss5_tone=%.2f\n", v.dlss5_detail.load(),
                 v.dlss5_tone.load());
    // Written only when it differs from the default, so a file without it follows the default
    // (-1 since 3.4.1; an older file's explicit value, including 0, is kept).
    if (v.dlss_mip_offset.load() != DlssMipOffsetDefault) {
        std::fprintf(file, "dlss_mip_offset=%.2f\n", v.dlss_mip_offset.load());
    }
    std::fprintf(file, "ray_tracing=%s\nrt_ao_quality=%s\nrt_shadow_quality=%s\nrt_ao_strength=%.2f\n",
                 RayTracingName(v.ray_tracing), RtTierName(v.rt_ao_quality),
                 RtTierName(v.rt_shadow_quality), v.rt_ao_strength.load());
    std::fprintf(file,
                 "rt_ao_combine=%d\nrt_ao_reach=%s\nrt_ao_full=%d\nrt_ao_direct=%.2f\n"
                 "rt_shadow_replace=%d\n",
                 int(v.rt_ao_combine.load()), AoReachName(v.rt_ao_reach),
                 int(v.rt_ao_full.load()), v.rt_ao_direct.load(),
                 int(v.rt_shadow_replace.load()));
    if (v.rt_shadow_half >= 0) {
        std::fprintf(file, "rt_shadow_half=%d\n", v.rt_shadow_half.load());
    }
    if (v.rt_shadow_reach_custom.load() > 0.0f && v.ray_tracing == RtCustom) {
        std::fprintf(file, "rt_shadow_reach_custom=%.1f\n", v.rt_shadow_reach_custom.load());
    }
    std::fprintf(file, "rt_secondary_lights=%d\n", int(v.rt_secondary_lights.load()));
    std::fprintf(file, "rt_reflections=%d\n", int(v.rt_reflections.load()));
    std::fprintf(file, "hdr=%d\n", int(v.hdr.load()));
    // Written only when changed, so a file without them follows the defaults.
    if (v.hdr_white_nits.load() != HdrWhiteDefault) {
        std::fprintf(file, "hdr_white_nits=%.0f\n", v.hdr_white_nits.load());
    }
    if (v.hdr_peak_nits.load() != HdrPeakDefault) {
        std::fprintf(file, "hdr_peak_nits=%.0f\n", v.hdr_peak_nits.load());
    }
    if (v.hdr_highlight_boost.load() != HdrBoostDefault) {
        std::fprintf(file, "hdr_highlight_boost=%.2f\n", v.hdr_highlight_boost.load());
    }
    std::fprintf(file, "model_lod=%d\noutput_res=%dx%d\n", v.model_lod.load(),
                 OutputWidths[v.output_res], OutputHeights[v.output_res]);
    if (v.anisotropy.load() == 0) {
        std::fprintf(file, "anisotropic_filtering=game\n");
    } else {
        std::fprintf(file, "anisotropic_filtering=%d\n", v.anisotropy.load());
    }
    // Read by run.sh at start.
    std::fprintf(file, "live_resolution=%s\n", v.live_resolution < 0 ? "auto"
                                                  : v.live_resolution ? "1" : "0");
    for (const std::string& line : kept) {
        std::fprintf(file, "%s\n", line.c_str());
    }
    std::fclose(file);
}

// The in-game PC menu (src/pc_menu.c) reads and writes the same settings through these.
namespace {
// A setting as the in-game PC menu sees it: on/off as 0/1, the upscaler as its index, the
// output resolution as an index into OutputWidths, live resolution as -1 (auto), 0 or 1, the
// model detail as -2..2. False for a key the menu does not handle.
bool Read(const Values& v, const std::string& k, int& out) {
    if (k == "show_fps") out = v.show_fps.load();
    else if (k == "fullscreen") out = v.fullscreen.load();
    else if (k == "sharpen") out = v.sharpen.load();
    else if (k == "jitter") out = v.jitter.load();
    else if (k == "object_motion") out = v.object_motion.load();
    else if (k == "upscaler") out = v.upscaler.load();
    else if (k == "preset") out = v.preset.load();
    else if (k == "output_res") out = v.output_res.load();
    else if (k == "live_resolution") out = v.live_resolution.load();
    else if (k == "model_lod") out = v.model_lod.load();
    else if (k == "anisotropic_filtering") out = v.anisotropy.load();
    else if (k == "dlss_model") out = v.dlss_model.load();
    else if (k == "reflex") out = v.reflex.load();
    else if (k == "dlss5") out = v.dlss5.load();
    else if (k == "dlss5_confirmed") out = v.dlss5_confirmed.load();
    else if (k == "dlss5_detail") out = int(v.dlss5_detail.load() * 10.0f + 0.5f); // tenths
    else if (k == "dlss5_tone") out = int(v.dlss5_tone.load() * 10.0f + 0.5f);     // tenths
    else if (k == "ray_tracing") out = v.ray_tracing.load();
    else if (k == "rt_ao_quality") out = v.rt_ao_quality.load();
    else if (k == "rt_shadow_quality") out = v.rt_shadow_quality.load();
    else if (k == "rt_ao_strength") out = int(v.rt_ao_strength.load() * 10.0f + 0.5f); // tenths
    else if (k == "mouse_camera") out = v.mouse_camera.load();
    else if (k == "mouse_sensitivity") out = v.mouse_sensitivity.load();
    else if (k == "mouse_invert_y") out = v.mouse_invert_y.load();
    else if (k == "mouse_flick_threshold") out = v.mouse_flick_threshold.load();
    else if (k == "mouse_menu") out = v.mouse_menu.load();
    else if (k == "mouse_hide_cursor") out = v.mouse_hide_cursor.load();
    else {
        for (int e = 0; e < EffectCount; ++e) {
            if (k == Effects[e].key) {
                out = v.effects[e].load();
                return true;
            }
        }
        return false;
    }
    return true;
}
} // namespace

// The in-game PC menu (src/pc_menu.c) reads and writes the same settings through these.
extern "C" int bbgpu_setting_get(const char* key, int* value) {
    return Read(Get(), key, *value) ? 1 : 0;
}

extern "C" int bbgpu_setting_default(const char* key, int* value) {
    const std::string k = key;
    for (int e = 0; e < EffectCount; ++e) {
        if (k == Effects[e].key) {
            *value = Effects[e].default_on;
            return 1;
        }
    }
    static const Values defaults;
    return Read(defaults, k, *value) ? 1 : 0;
}

namespace {
// Fullscreen belongs to the launcher (settings.json, passed as BB_FULLSCREEN): the window
// follows the setting at once (window.cpp), a restart inherits the environment, and the
// launcher's file keeps it for the next start.
void SetFullscreen(bool on) {
    Get().fullscreen = on;
#ifdef _WIN32
    _putenv_s("BB_FULLSCREEN", on ? "1" : "0");
#else
    setenv("BB_FULLSCREEN", on ? "1" : "0", 1);
#endif
    // The launcher names its file (BB_LAUNCHER_SETTINGS: a custom build keeps its own).
    std::filesystem::path file;
    if (const char* named = std::getenv("BB_LAUNCHER_SETTINGS"); named && *named) {
        file = std::filesystem::path(named);
    } else if (const char* appdata = std::getenv("APPDATA")) {
        file = std::filesystem::path(appdata) / "bbport-launcher" / "settings.json";
    } else {
        return;
    }
    std::ifstream in(file);
    if (!in) return;
    nlohmann::json root = nlohmann::json::parse(in, nullptr, false);
    in.close();
    if (!root.is_object()) return;
    root["fullscreen"] = on;
    const auto part = file.string() + ".part";
    {
        std::ofstream out(part, std::ios::trunc);
        out << root.dump(2);
        if (!out) return;
    }
    std::error_code error;
    std::filesystem::rename(part, file, error);
}
} // namespace

extern "C" void bbgpu_setting_set(const char* key, int value) {
    const std::string k = key;
    if (k == "fullscreen") {
        SetFullscreen(value != 0);
        return;
    }
    std::string text = std::to_string(value);
    if (k == "upscaler") {
        text = UpscalerName(value);
    } else if (k == "frame_gen") {
        text = FrameGenName(value);
        if (value == FrameGenDlss && Get().reflex.load() == ReflexOff) {
            Get().reflex = ReflexOn;
        }
    } else if (k == "dlss_model") {
        text = DlssModelName(value);
    } else if (k == "reflex") {
        text = ReflexName(value);
    } else if (k == "dlss5") {
        text = value ? "on" : "off";
    } else if (k == "ray_tracing") {
        text = RayTracingName(value);
    } else if (k == "rt_ao_quality" || k == "rt_shadow_quality") {
        text = RtTierName(value);
    } else if (k == "rt_ao_strength" || k == "dlss5_detail" || k == "dlss5_tone") {
        text = std::to_string(float(value) / 10.0f);
    } else if (k == "output_res") {
        const int r = std::clamp(value, 0, OutputCount - 1);
        text = std::to_string(OutputWidths[r]) + "x" + std::to_string(OutputHeights[r]);
    } else if (k == "live_resolution" && value < 0) {
        text = "auto";
    }
    Set(Get(), k, text);
    Save();
}

// Whether this GPU runs an upscaler (the menu offers only those).
extern "C" int bbgpu_upscaler_supported(int upscaler) {
    const auto& v = Get();
    switch (upscaler) {
    case UpscalerFsr4: return v.fsr4_supported.load();
    case UpscalerFsr411: return v.fsr411_supported.load();
    case UpscalerDlss: return v.dlss_supported.load();
    default: return upscaler >= 0 && upscaler < UpscalerCount;
    }
}

float PresetScale(int preset) {
    static constexpr float scales[PresetCount] = {1.0f, 1.5f, 1.7f, 2.0f, 3.0f};
    return scales[std::clamp(preset, 0, PresetCount - 1)];
}

const char* PresetName(int preset) {
    static constexpr const char* names[PresetCount] = {"Native AA", "Quality", "Balanced",
                                                       "Performance", "Ultra Performance"};
    return names[std::clamp(preset, 0, PresetCount - 1)];
}

const char* FrameGenName(int frame_gen) {
    static constexpr const char* names[FrameGenCount] = {"off", "fsr3", "dlss"};
    return names[std::clamp(frame_gen, 0, FrameGenCount - 1)];
}

const char* UpscalerName(int upscaler) {
    static constexpr const char* names[UpscalerCount] = {"off", "fsr3", "fsr4", "fsr411", "taa", "dlss"};
    return names[std::clamp(upscaler, 0, UpscalerCount - 1)];
}

const char* DlssModelName(int model) {
    return DlssModelIniNames[std::clamp(model, 0, DlssModelCount - 1)];
}

const char* RtTierName(int tier) {
    static constexpr const char* names[TierCount] = {"off", "low", "medium", "high", "ultra"};
    return names[std::clamp(tier, 0, TierCount - 1)];
}

const char* AoReachName(int reach) {
    static constexpr const char* names[AoReachCount] = {"tier", "wide", "wider"};
    return names[std::clamp(reach, 0, AoReachCount - 1)];
}

const char* RayTracingName(int quality) {
    static constexpr const char* names[RtQualityCount] = {"off",  "low",   "medium",
                                                          "high", "ultra", "custom"};
    return names[std::clamp(quality, 0, RtQualityCount - 1)];
}

namespace {
// What a tier traces (index: RtTier). AO is traced at half size; rays a pixel lower its noise
// in motion (the temporal filter averages the rest), reach (metres) is how far an occluder
// darkens. Moon shadows at full size cost four times half size (1.6 ms against 0.4 ms at 15 m,
// 4K with DLSS Quality, RTX 4080 SUPER); the game's moon is not blocked by the world's large
// geometry (its shadows are baked), so long shadows shade whole streets. Off's entries are
// what BB_RT_SHADOWS=1 (vk_rt_effects.cpp) traces with the effect off: as before the tiers.
struct AoTier {
    float radius;
    int rays;
};
constexpr AoTier AoTiers[TierCount] = {{1.0f, 1}, {0.75f, 1}, {1.0f, 1}, {1.0f, 2}, {1.25f, 2}};
struct ShadowTier {
    bool half;
    float reach;
};
constexpr ShadowTier ShadowTiers[TierCount] = {
    {false, 4.0f}, {true, 6.0f}, {true, 15.0f}, {false, 15.0f}, {false, 40.0f}};
} // namespace

void RayTracingTiers(int quality, int& ao, int& shadows) {
    // The levels trace what they did before the tiers (their measured GPU time).
    switch (quality) {
    case RtLow: ao = TierMedium, shadows = TierOff; break;
    case RtMedium: ao = TierMedium, shadows = TierLow; break;
    case RtHigh: ao = TierMedium, shadows = TierMedium; break;
    case RtUltra: ao = TierUltra, shadows = TierUltra; break;
    case RtCustom:
        ao = std::clamp(Get().rt_ao_quality.load(), 0, TierCount - 1);
        shadows = std::clamp(Get().rt_shadow_quality.load(), 0, TierCount - 1);
        break;
    default: ao = shadows = TierOff; break;
    }
}

bool CustomStart(int level, int& ao, int& shadows, float& strength) {
    if (level == RtCustom || ao != TierOff || shadows != TierOff) {
        return false;
    }
    int level_ao, level_shadows;
    RayTracingTiers(level, level_ao, level_shadows);
    if (level_ao == TierOff && level_shadows == TierOff) {
        return false; // from Off: nothing to start from
    }
    ao = level_ao;
    shadows = level_shadows;
    strength = 1.0f;
    return true;
}

RayTracingEffect RayTracingEffective() {
    const auto& v = Get();
    const int quality = v.ray_tracing;
    int ao, shadows;
    RayTracingTiers(quality, ao, shadows);
    RayTracingEffect e;
    e.ao = ao != TierOff;
    e.ao_radius = AoTiers[ao].radius;
    e.ao_rays = AoTiers[ao].rays;
    e.ao_strength = v.rt_ao_strength;
    if (quality == RtCustom) {
        // The AO's options (bbport_overlay.cpp's Custom rows).
        e.ao_combine = v.rt_ao_combine;
        e.ao_full = v.rt_ao_full;
        e.ao_direct = v.rt_ao_direct;
        e.shadow_replace = v.rt_shadow_replace;
        const int reach = v.rt_ao_reach;
        if (reach != AoReachTier) {
            e.ao_radius = reach == AoReachWide ? 2.5f : 4.0f;
            e.ao_rays = std::max(e.ao_rays, 2);
        }
    }
    e.shadows = shadows != TierOff;
    e.shadow_half = (v.rt_shadow_half >= 0 && quality == RtCustom) ? (v.rt_shadow_half == 1) : ShadowTiers[shadows].half;
    float reach = ShadowTiers[shadows].reach;
    if (quality == RtCustom && v.rt_shadow_reach_custom.load() > 0.0f) {
        reach = std::clamp(v.rt_shadow_reach_custom.load(), 1.0f, 150.0f);
    }
    e.shadow_reach = reach;
    e.secondary_lights = v.rt_secondary_lights.load();
    e.reflections = v.rt_reflections.load();
    return e;
}

float ShadowTierReach(int tier) {
    if (tier < 0 || tier >= TierCount) return 4.0f;
    return ShadowTiers[tier].reach;
}

bool RayTracingWanted() {
    return Get().startup_ray_tracing != RtOff;
}

const char* ReflexName(int mode) {
    static constexpr const char* names[ReflexModeCount] = {"off", "on", "boost"};
    return names[std::clamp(mode, 0, ReflexModeCount - 1)];
}

} // namespace BbSettings
