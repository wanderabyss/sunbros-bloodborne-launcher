// SPDX-License-Identifier: GPL-2.0-or-later
// bbport.ini dlss_model (the DLSS render preset hint) and the keys Save() writes exactly once.
#include "bbport_settings.h"
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

extern "C" void bbgpu_setting_set(const char* key, int value);
extern "C" int bbgpu_setting_get(const char* key, int* value);
extern "C" int bbgpu_setting_default(const char* key, int* value);

namespace {

int Count(const std::filesystem::path& path, const std::string& key) {
    std::ifstream in(path);
    int n = 0;
    for (std::string line; std::getline(in, line);) {
        n += line.rfind(key + "=", 0) == 0;
    }
    return n;
}

// Sets (or, with null, removes) an environment variable.
void SetEnv(const char* name, const char* value) {
#ifdef _WIN32
    _putenv_s(name, value ? value : "");
#else
    if (value) {
        setenv(name, value, 1);
    } else {
        unsetenv(name);
    }
#endif
}

void Write(const std::filesystem::path& path, const char* text) {
    FILE* file = std::fopen(path.string().c_str(), "w");
    assert(file);
    std::fputs(text, file);
    std::fclose(file);
}

} // namespace

int main() {
    using namespace BbSettings;
    const auto path = std::filesystem::temp_directory_path() /
        ("bb-dlss-model-" + std::to_string(
            std::chrono::steady_clock::now().time_since_epoch().count()) + ".ini");
#ifdef _WIN32
    _putenv_s("BB_CONFIG", path.string().c_str());
#else
    setenv("BB_CONFIG", path.string().c_str(), 1);
#endif
    auto& settings = Get();
    // New settings get Auto (decision 6): the model for the card (bbport_nvidia_gpu.h).
    assert(settings.dlss_model == DlssModelAuto && std::string{DlssModelName(DlssModelAuto)} == "auto");

    // Names (any case) -> the NGX preset values of DLSS 310: K 11, J 10, M 13, L 12, default 0.
    const struct { const char* text; int model; unsigned preset; } names[] = {
        {"default", DlssModelDefault, 0}, {"K", DlssModelK, 11}, {"k", DlssModelK, 11},
        {"J", DlssModelJ, 10}, {"M", DlssModelM, 13}, {"l", DlssModelL, 12},
        {"auto", DlssModelAuto, 0}, {"Auto", DlssModelAuto, 0}};
    for (const auto& n : names) {
        settings.dlss_model = DlssModelDefault;
        Write(path, ("dlss_model=" + std::string(n.text) + "\n").c_str());
        Load();
        assert(settings.dlss_model == n.model);
        assert(DlssModelPresets[settings.dlss_model] == n.preset);
    }
    // Deprecated, "do not use" and malformed values leave the model as it was.
    for (const char* bad : {"E", "F", "G", "N", "11", "", "KK", "transformer", "automatic"}) {
        settings.dlss_model = DlssModelM;
        Write(path, ("dlss_model=" + std::string(bad) + "\n").c_str());
        Load();
        assert(settings.dlss_model == DlssModelM);
    }

    // Save writes every key it owns once: frame_gen used to be added again at every save.
    Write(path, "frame_gen=dlss\nframe_gen_multiplier=2\nframe_gen_fit_display=0\n"
                "frame_gen=dlss\nframe_gen_multiplier=2\nframe_gen_fit_display=0\n"
                "dlss_model=K\npc_menu=1\n");
    Load();
    Save();
    Save();
    for (const char* key : {"frame_gen", "frame_gen_multiplier", "frame_gen_fit_display", "dlss_model",
                            "upscaler", "pc_menu"}) {
        assert(Count(path, key) == 1);
    }
    settings.dlss_model = DlssModelDefault;
    Load();
    assert(settings.dlss_model == DlssModelK && settings.frame_gen == FrameGenDlss);

    // The in-game menu: index in, name in the file, index out.
    bbgpu_setting_set("dlss_model", DlssModelL);
    int value = -1;
    assert(bbgpu_setting_get("dlss_model", &value) == 1 && value == DlssModelL);
    assert(Count(path, "dlss_model") == 1);
    settings.dlss_model = DlssModelDefault;
    Load();
    assert(settings.dlss_model == DlssModelL);
    bbgpu_setting_set("dlss_model", DlssModelAuto);
    settings.dlss_model = DlssModelDefault;
    Load();
    assert(settings.dlss_model == DlssModelAuto && Count(path, "dlss_model") == 1);

    // reflex: off / on / boost; anything else leaves it as it was; written once; menu index.
    for (const auto& [text, mode] : {std::pair{"off", int(ReflexOff)}, std::pair{"on", int(ReflexOn)},
                                     std::pair{"boost", int(ReflexBoost)}}) {
        settings.reflex = ReflexOff;
        Write(path, ("reflex=" + std::string(text) + "\n").c_str());
        Load();
        assert(settings.reflex == mode);
    }
    for (const char* bad : {"1", "ON", "ultra", ""}) {
        settings.reflex = ReflexOn;
        Write(path, ("reflex=" + std::string(bad) + "\n").c_str());
        Load();
        assert(settings.reflex == ReflexOn);
    }
    bbgpu_setting_set("reflex", ReflexBoost);
    bbgpu_setting_set("reflex", ReflexOn);
    assert(Count(path, "reflex") == 1);
    assert(bbgpu_setting_get("reflex", &value) == 1 && value == ReflexOn);

    // dlss5: off by default; on / off (and 1 / 0); written once, with dlss5_confirmed; menu.
    assert(!settings.dlss5 && !settings.dlss5_confirmed);
    Write(path, "dlss5=on\ndlss5_confirmed=1\n");
    Load();
    assert(settings.dlss5 && settings.dlss5_confirmed);
    for (const bool was : {false, true}) {
        settings.dlss5 = was;
        Write(path, "dlss5=maybe\n");
        Load(); // a value it does not know leaves it as it was
        assert(settings.dlss5 == was);
    }
    bbgpu_setting_set("dlss5", 1);
    bbgpu_setting_set("dlss5_confirmed", 1);
    assert(Count(path, "dlss5") == 1 && Count(path, "dlss5_confirmed") == 1);
    settings.dlss5 = false;
    Load();
    assert(settings.dlss5 && settings.dlss5_confirmed);
    assert(bbgpu_setting_get("dlss5", &value) == 1 && value == 1);

    // HDR brightness: defaults are the old fixed 120 / 1000 nits and full boost, not saved
    // unless changed; "display" (0) follows the display; clamped; ResolveHdrLevels falls back.
    {
        Write(path, "hdr=1\n");
        Load();
        assert(settings.hdr_white_nits.load() == HdrWhiteDefault &&
               settings.hdr_peak_nits.load() == HdrPeakDefault &&
               settings.hdr_highlight_boost.load() == HdrBoostDefault);
        Save();
        assert(Count(path, "hdr_white_nits") == 0 && Count(path, "hdr_peak_nits") == 0 &&
               Count(path, "hdr_highlight_boost") == 0);
        Write(path, "hdr_white_nits=200\nhdr_peak_nits=display\nhdr_highlight_boost=low\n");
        Load();
        assert(settings.hdr_white_nits.load() == 200.0f && settings.hdr_peak_nits.load() == 0.0f &&
               std::abs(settings.hdr_highlight_boost.load() - 0.33f) < 1e-4f);
        Save();
        Save();
        assert(Count(path, "hdr_white_nits") == 1 && Count(path, "hdr_peak_nits") == 1 &&
               Count(path, "hdr_highlight_boost") == 1);
        Load();
        assert(settings.hdr_white_nits.load() == 200.0f && settings.hdr_peak_nits.load() == 0.0f &&
               std::abs(settings.hdr_highlight_boost.load() - 0.33f) < 1e-4f);
        Write(path, "hdr_white_nits=20\nhdr_peak_nits=99999\nhdr_highlight_boost=nan\n");
        Load();
        assert(settings.hdr_white_nits.load() == HdrWhiteMin &&
               settings.hdr_peak_nits.load() == HdrPeakMax &&
               settings.hdr_highlight_boost.load() == HdrBoostDefault);
        auto l = ResolveHdrLevels(0.0f, 0.0f, 0.5f, 240.0f, 800.0f);
        assert(l.white_nits == 240.0f && l.peak_nits == 800.0f && l.boost == 0.5f);
        l = ResolveHdrLevels(0.0f, 0.0f, 1.0f, 0.0f, 0.0f); // the display reports nothing
        assert(l.white_nits == HdrWhiteDefault && l.peak_nits == HdrPeakDefault);
        l = ResolveHdrLevels(400.0f, 400.0f, 2.0f, 0.0f, 0.0f);
        assert(l.peak_nits >= l.white_nits && l.boost == 1.0f);
        settings.hdr_white_nits = HdrWhiteDefault;
        settings.hdr_peak_nits = HdrPeakDefault;
        settings.hdr_highlight_boost = HdrBoostDefault;
    }

    // dlss5_detail (Structure Intensity) and dlss5_tone (Tone Intensity), decision D6: half
    // detail and no colour change by default; 0..1, clamped; saved once each; the menu sees
    // tenths; BB_DLSS5_DETAIL / BB_DLSS5_TONE override the file.
    {
        static const Values defaults;
        assert(defaults.dlss5_detail.load() == 0.5f && defaults.dlss5_tone.load() == 0.0f);
        int fallback = -1;
        assert(bbgpu_setting_default("dlss5_detail", &fallback) == 1 && fallback == 5);
        assert(bbgpu_setting_default("dlss5_tone", &fallback) == 1 && fallback == 0);
        Write(path, "dlss5_detail=0.8\ndlss5_tone=0.25\n");
        Load();
        assert(std::abs(settings.dlss5_detail.load() - 0.8f) < 1e-4f);
        assert(std::abs(settings.dlss5_tone.load() - 0.25f) < 1e-4f);
        Write(path, "dlss5_detail=1.5\ndlss5_tone=-1\n");
        Load();
        assert(settings.dlss5_detail.load() == 1.0f && settings.dlss5_tone.load() == 0.0f);
        Save();
        Save();
        assert(Count(path, "dlss5_detail") == 1 && Count(path, "dlss5_tone") == 1);
        bbgpu_setting_set("dlss5_detail", 3);
        bbgpu_setting_set("dlss5_tone", 7);
        assert(bbgpu_setting_get("dlss5_detail", &value) == 1 && value == 3);
        assert(bbgpu_setting_get("dlss5_tone", &value) == 1 && value == 7);
        settings.dlss5_detail = 0.5f;
        settings.dlss5_tone = 0.0f;
        Load(); // the menu's change was saved
        assert(std::abs(settings.dlss5_detail.load() - 0.3f) < 1e-4f);
        assert(std::abs(settings.dlss5_tone.load() - 0.7f) < 1e-4f);
        if (!std::getenv("BB_DLSS5_DETAIL") && !std::getenv("BB_DLSS5_TONE")) {
            SetEnv("BB_DLSS5_DETAIL", "0.9");
            SetEnv("BB_DLSS5_TONE", "0.1");
            Load();
            assert(std::abs(settings.dlss5_detail.load() - 0.9f) < 1e-4f);
            assert(std::abs(settings.dlss5_tone.load() - 0.1f) < 1e-4f);
            SetEnv("BB_DLSS5_DETAIL", nullptr);
            SetEnv("BB_DLSS5_TONE", nullptr);
            Load();
            assert(std::abs(settings.dlss5_detail.load() - 0.3f) < 1e-4f);
        }
        bbgpu_setting_set("dlss5_detail", 5);
        bbgpu_setting_set("dlss5_tone", 0);
        assert(settings.dlss5_detail.load() == 0.5f && settings.dlss5_tone.load() == 0.0f);
    }

    // Why it cannot be switched on, in the menu's order.
    char text[256];
    settings.dlss5_eligible = false;
    assert(Dlss5Unavailable(settings, "NVIDIA GeForce RTX 4070", "60", text, sizeof(text)));
    assert(std::string{text}.find("RTX 4070") != std::string::npos);
    settings.dlss5_eligible = true;
    settings.upscaler = UpscalerFsr3;
    assert(Dlss5Unavailable(settings, "", "60", text, sizeof(text)));
    assert(std::string{text} == "needs DLSS as the upscaler");
    settings.upscaler = UpscalerDlss;
    assert(Dlss5Unavailable(settings, "", "uncap", text, sizeof(text)));
    assert(std::string{text} == "needs a fixed 60 FPS (now: uncapped)");
    assert(Dlss5Unavailable(settings, "", "120", text, sizeof(text)));
    assert(std::string{text} == "needs a fixed 60 FPS (now: 120)");
    settings.dlss5_backend = Dlss5None;
    settings.dlss5_problem = "turned off because the last start with DLSS 5 crashed";
    assert(Dlss5Unavailable(settings, "", "60", text, sizeof(text)));
    assert(std::string{text}.find("crashed") != std::string::npos);
    settings.dlss5_problem = nullptr;
    assert(Dlss5Unavailable(settings, "", "60", text, sizeof(text)));
    assert(std::string{text}.rfind("waiting for NVIDIA", 0) == 0);
    // No setup guide ships while the community bridge is paused: the text must not name one.
    assert(std::string{text}.find("dlss5-setup") == std::string::npos);
    settings.dlss5_backend = Dlss5Bridge;
    assert(!Dlss5Unavailable(settings, "", "60", text, sizeof(text)));
    // Without run.py's BB_DLSS5_ROUTE_A=1 (which it never sets while the bridge is paused) an
    // eligible card with dlss5=on has no backend and is not reported active.
    if (!std::getenv("BB_DLSS5_ROUTE_A")) {
        settings.dlss5 = true;
        ConfigureDlss5(true, nullptr, "NVIDIA GeForce RTX 4090");
        assert(settings.dlss5_eligible && settings.dlss5_backend == Dlss5None &&
               !settings.dlss5_active);
        assert(Dlss5Unavailable(settings, "", "60", text, sizeof(text)));
    }
    // NVIDIA's own DLSS 5 through the DLSS bridge (ABI 3) is the backend when the bridge runs
    // it, also without BB_DLSS5_ROUTE_A; never on a card that is not offered it.
    {
        settings.dlss5 = true;
        settings.upscaler = UpscalerDlss;
        ConfigureDlss5(true, nullptr, "NVIDIA GeForce RTX 4090", true);
        assert(settings.dlss5_backend == Dlss5Native && settings.dlss5_active);
        assert(!Dlss5Unavailable(settings, "", "60", text, sizeof(text)));
        assert(Dlss5Unavailable(settings, "", "120", text, sizeof(text))); // still 60 FPS only
        if (!std::getenv("BB_DLSS5_ANY_GPU")) {
            ConfigureDlss5(false, "needs a GeForce RTX 4080, 4090 or newer",
                           "NVIDIA GeForce RTX 4070", true);
            assert(settings.dlss5_backend == Dlss5None && !settings.dlss5_active);
        }
        settings.dlss5 = false;
        ConfigureDlss5(true, nullptr, "NVIDIA GeForce RTX 4090", true);
        assert(settings.dlss5_backend == Dlss5Native && !settings.dlss5_active); // off is off
    }

    // EffectiveReflexMode helper: DLSS FG requires Reflex On minimum, preserves Boost.
    assert(EffectiveReflexMode(ReflexOff, FrameGenOff) == ReflexOff);
    assert(EffectiveReflexMode(ReflexOn, FrameGenOff) == ReflexOn);
    assert(EffectiveReflexMode(ReflexBoost, FrameGenOff) == ReflexBoost);
    assert(EffectiveReflexMode(ReflexOff, FrameGenFsr3) == ReflexOff);
    assert(EffectiveReflexMode(ReflexOff, FrameGenDlss) == ReflexOn);
    assert(EffectiveReflexMode(ReflexOn, FrameGenDlss) == ReflexOn);
    assert(EffectiveReflexMode(ReflexBoost, FrameGenDlss) == ReflexBoost);

    // bbgpu_setting_set auto-promotion: choosing DLSS FG while Reflex is Off promotes it to On.
    settings.reflex = ReflexOff;
    bbgpu_setting_set("frame_gen", FrameGenDlss);
    assert(settings.reflex == ReflexOn);
    assert(settings.frame_gen == FrameGenDlss);

    // RuntimeStatus channel: staleness (>2000 ms), active provider and latency metrics.
    settings.status.last_update_ms = 0;
    assert(!settings.status.IsActive());
    const int64_t now_tick = std::chrono::duration_cast<std::chrono::milliseconds>(
                                 std::chrono::steady_clock::now().time_since_epoch())
                                 .count();
    settings.status.last_update_ms = now_tick;
    assert(settings.status.IsActive(now_tick));
    assert(settings.status.IsActive(now_tick + 1999));
    assert(!settings.status.IsActive(now_tick + 2000));
    assert(!settings.status.IsActive(now_tick + 5000));
    assert(!settings.status.IsActive(now_tick - 1));

    // Exercise the same transitions used by Generate(), Skip() and Fail(), rather than
    // assigning a provider directly. Presenting unrelated frames must not reactivate FG.
    RuntimeStatus fg;
    assert(fg.ObserveFrameGenRequest(FrameGenDlss));
    assert(fg.RecordFrameGeneration(FrameGenDlss, 1));
    assert(fg.active_frame_gen == FrameGenDlss);
    assert(fg.active_frame_gen_multiplier == 2);
    assert(fg.dlss_frame_gen_pairs == 1 && fg.generated_frames == 1);
    assert(fg.presented_generated_frames == 0);
    for (const char* reason : {"HDR output", "menu: no scene", "display limit", "no output"}) {
        fg.ClearFrameGeneration(reason);
        fg.last_update_ms = now_tick;
        assert(fg.IsActive(now_tick));
        assert(fg.active_frame_gen == FrameGenOff);
        assert(fg.active_frame_gen_multiplier == 1);
        assert(fg.frame_gen_inactive_reason.load() == reason);
    }

    // Both startup unavailability and a failed runtime evaluation select a fallback, but
    // cannot claim it is active before a successful pair. FSR success retains the cause.
    fg.FrameGenFallback(FrameGenFsr3, "DLSS unavailable");
    assert(!fg.ObserveFrameGenRequest(FrameGenFsr3));
    assert(fg.active_frame_gen == FrameGenOff);
    assert(!fg.RecordFrameGeneration(FrameGenFsr3, 0));
    assert(fg.fsr_frame_gen_pairs == 0);
    assert(fg.RecordFrameGeneration(FrameGenFsr3, 1));
    assert(fg.active_frame_gen == FrameGenFsr3);
    assert(std::string{fg.frame_gen_fallback_reason.load()} == "DLSS unavailable");
    assert(!fg.RecordFrameGeneration(FrameGenFsr3, 1));
    assert(fg.fsr_frame_gen_pairs == 2);
    fg.ClearFrameGeneration("HDR output");
    assert(std::string{fg.frame_gen_fallback_reason.load()} == "DLSS unavailable");

    // Explicit provider changes clear the old failure; a later DLSS recovery is counted.
    assert(fg.ObserveFrameGenRequest(FrameGenOff));
    assert(fg.frame_gen_fallback_reason.load() == nullptr);
    assert(fg.active_frame_gen == FrameGenOff);
    assert(fg.ObserveFrameGenRequest(FrameGenDlss));
    assert(!fg.RecordFrameGeneration(FrameGenDlss, 2)); // first pair was counted above
    assert(fg.active_frame_gen_multiplier == 3);
    assert(fg.dlss_frame_gen_pairs == 2);
    assert(fg.generated_frames == 5);
    assert(fg.presented_generated_frames == 0); // generation alone never proves presentation
    fg.FrameGenFallback(FrameGenOff, "FSR evaluation failed");
    assert(fg.active_frame_gen == FrameGenOff);
    assert(fg.active_frame_gen_multiplier == 1);
    assert(std::string{fg.frame_gen_fallback_reason.load()} == "FSR evaluation failed");

    settings.status.active_upscaler = UpscalerDlss;
    settings.status.effective_reflex = ReflexOn;
    settings.status.reflex_forced_by_fg = true;
    settings.status.reflex_latency_ms = 14.5f;
    settings.status.hdr_swapchain_active = true;
    settings.status.measured_render_fps = 60.0f;
    settings.status.measured_present_fps = 120.0f;
    assert(settings.status.active_upscaler == UpscalerDlss);
    assert(settings.status.effective_reflex == ReflexOn);
    assert(settings.status.reflex_forced_by_fg.load());
    assert(settings.status.reflex_latency_ms.load() == 14.5f);
    assert(settings.status.hdr_swapchain_active.load());
    assert(settings.status.measured_render_fps.load() == 60.0f);
    assert(settings.status.measured_present_fps.load() == 120.0f);

    // dlss_mip_offset / dlss_mip_bias: default -1 (NVIDIA's advice), parsed, clamped to
    // [-2.0, 0.0], saved once when it differs from the default.
    assert(BbSettings::DlssMipOffsetDefault == -1.0f);
    Write(path, "upscaler=dlss\n");
    Load();
    assert(settings.dlss_mip_offset.load() == -1.0f); // a file without the key: the default
    settings.dlss_mip_offset = 0.0f;
    Write(path, "dlss_mip_offset=-0.5\n");
    Load();
    assert(std::abs(settings.dlss_mip_offset.load() - (-0.5f)) < 1e-4f);
    Write(path, "dlss_mip_bias=-1.25\n");
    Load();
    assert(std::abs(settings.dlss_mip_offset.load() - (-1.25f)) < 1e-4f);
    Write(path, "dlss_mip_offset=-3.5\n");
    Load();
    assert(settings.dlss_mip_offset.load() == -2.0f);
    Write(path, "dlss_mip_offset=1.5\n");
    Load();
    assert(settings.dlss_mip_offset.load() == 0.0f);

    settings.dlss_mip_offset = -0.75f;
    Save();
    assert(Count(path, "dlss_mip_offset") == 1);
    assert(Count(path, "dlss_mip_bias") == 0);
    settings.dlss_mip_offset = 0.0f;
    Load();
    assert(std::abs(settings.dlss_mip_offset.load() - (-0.75f)) < 1e-4f);

    settings.dlss_mip_offset = -1.0f; // the default is not written
    Save();
    assert(Count(path, "dlss_mip_offset") == 0);
    settings.dlss_mip_offset = 0.0f; // the old look, chosen explicitly, is kept
    Save();
    assert(Count(path, "dlss_mip_offset") == 1);
    settings.dlss_mip_offset = -1.0f;
    Load();
    assert(settings.dlss_mip_offset.load() == 0.0f);

    // BB_DLSS_MIP_OFFSET environment variable precedence.
#ifdef _WIN32
    _putenv_s("BB_DLSS_MIP_OFFSET", "-1.50");
#else
    setenv("BB_DLSS_MIP_OFFSET", "-1.50", 1);
#endif
    Write(path, "dlss_mip_offset=-0.25\n");
    Load();
    assert(std::abs(settings.dlss_mip_offset.load() - (-1.50f)) < 1e-4f);
#ifdef _WIN32
    _putenv_s("BB_DLSS_MIP_OFFSET", "");
#else
    unsetenv("BB_DLSS_MIP_OFFSET");
#endif
    Load();
    assert(std::abs(settings.dlss_mip_offset.load() - (-0.25f)) < 1e-4f);

    std::filesystem::remove(path);
    std::puts("DLSS model, Reflex coupling, DLSS 5, mip offset and RuntimeStatus channel PASS");
}
