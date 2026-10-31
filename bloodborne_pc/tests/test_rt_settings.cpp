// SPDX-License-Identifier: GPL-2.0-or-later
// bbport.ini ray tracing keys (vk_ray_tracing.h): ray_tracing, rt_ao_quality, rt_shadow_quality,
// rt_ao_strength - names, ranges, what the levels and tiers trace, files from before the tiers
// and where Custom starts (with the launcher's test: tests/data/rt_settings.txt), the
// environment over the file, the in-game menu's units, single keys in Save(), and that ray
// tracing is wanted only for the choices made at start.
#include "bbport_settings.h"
#include <algorithm>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <sstream>
#include <string>

extern "C" void bbgpu_setting_set(const char* key, int value);
extern "C" int bbgpu_setting_get(const char* key, int* value);

namespace {

int Count(const std::filesystem::path& path, const std::string& key) {
    std::ifstream in(path);
    int n = 0;
    for (std::string line; std::getline(in, line);) {
        n += line.rfind(key + "=", 0) == 0;
    }
    return n;
}

void Write(const std::filesystem::path& path, const std::string& text) {
    FILE* file = std::fopen(path.string().c_str(), "w");
    assert(file);
    std::fputs(text.c_str(), file);
    std::fclose(file);
}

} // namespace

int main() {
    using namespace BbSettings;
    const auto path = std::filesystem::temp_directory_path() /
        ("bb-rt-settings-" + std::to_string(
            std::chrono::steady_clock::now().time_since_epoch().count()) + ".ini");
#ifdef _WIN32
    _putenv_s("BB_CONFIG", path.string().c_str());
#else
    setenv("BB_CONFIG", path.string().c_str(), 1);
#endif
    auto& settings = Get();

    // Defaults: the game's own effects, no ray tracing.
    Write(path, "");
    Load();
    assert(settings.rt_ao_quality == TierOff && settings.rt_shadow_quality == TierOff);
    assert(settings.ray_tracing == RtOff && !RayTracingWanted());

    // Tier names; anything else leaves the choice as it was. Without a level, a traced effect
    // is Custom.
    const char* tiers[] = {"off", "low", "medium", "high", "ultra"};
    for (int t = 0; t < TierCount; ++t) {
        Write(path, "rt_ao_quality=" + std::string(tiers[t]) + "\nrt_shadow_quality=" + tiers[t] + "\n");
        Load();
        assert(settings.rt_ao_quality == t && settings.rt_shadow_quality == t);
        assert(std::string(RtTierName(t)) == tiers[t]);
        assert(settings.ray_tracing == (t == TierOff ? RtOff : RtCustom));
    }
    for (const char* bad : {"1", "on", "Ultra", "", "maximum"}) {
        Write(path, "rt_ao_quality=" + std::string(bad) + "\nrt_shadow_quality=" + bad + "\n");
        Load();
        assert(settings.rt_ao_quality == TierUltra && settings.rt_shadow_quality == TierUltra);
    }

    // Strength 0..2.
    Write(path, "rt_ao_strength=2\n");
    Load();
    assert(settings.rt_ao_strength == 2.0f);
    Write(path, "rt_ao_strength=3\n");
    Load();
    assert(settings.rt_ao_strength == 2.0f);
    Write(path, "rt_ao_strength=-1\n");
    Load();
    assert(settings.rt_ao_strength == 0.0f);

    // ray_tracing: names; "maximum" (before Ultra) is Ultra; anything else as without the key.
    const char* levels[] = {"off", "low", "medium", "high", "ultra", "custom"};
    for (int q = 0; q < RtQualityCount; ++q) {
        Write(path, "ray_tracing=" + std::string(levels[q]) + "\n");
        Load();
        assert(settings.ray_tracing == q && std::string(RayTracingName(q)) == levels[q]);
    }
    Write(path, "ray_tracing=maximum\n");
    Load();
    assert(settings.ray_tracing == RtUltra && RayTracingWanted());
    Write(path, "ray_tracing=epic\nrt_ao_quality=low\n");
    Load();
    assert(settings.ray_tracing == RtCustom);

    // The levels trace what they did before the tiers (their measured GPU time); a level
    // ignores the Custom keys but the AO strength (every level).
    Write(path, "ray_tracing=low\nrt_ao_quality=off\nrt_shadow_quality=ultra\nrt_ao_strength=0.3\n"
                "rt_ao_combine=1\nrt_ao_reach=wider\nrt_ao_full=1\nrt_ao_direct=0.5\n"
                "rt_shadow_replace=1\n");
    Load();
    auto e = RayTracingEffective();
    assert(e.ao && !e.shadows && e.ao_rays == 1 && e.ao_radius == 1.0f);
    assert(std::abs(e.ao_strength - 0.3f) < 1e-4f);
    assert(!e.ao_combine && !e.ao_full && e.ao_direct == 0.0f && !e.shadow_replace);
    settings.ray_tracing = RtMedium;
    e = RayTracingEffective();
    assert(e.ao && e.shadows && e.shadow_half && e.shadow_reach == 6.0f && e.ao_rays == 1);
    settings.ray_tracing = RtHigh;
    e = RayTracingEffective();
    assert(e.shadows && e.shadow_half && e.shadow_reach == 15.0f && e.shadow_rays == 1);
    settings.ray_tracing = RtUltra;
    e = RayTracingEffective();
    assert(e.ao_rays == 2 && e.ao_radius == 1.25f && !e.shadow_half && e.shadow_rays == 1 &&
           e.shadow_reach == 40.0f);
    settings.ray_tracing = RtOff;
    e = RayTracingEffective();
    assert(!e.ao && !e.shadows);
    // Off's shadow entries are what BB_RT_SHADOWS=1 traces: full size, 4 m, as before the tiers.
    assert(!e.shadow_half && e.shadow_reach == 4.0f);
    // Custom: the tiers and the strength.
    settings.ray_tracing = RtCustom;
    e = RayTracingEffective();
    assert(!e.ao && e.shadows && !e.shadow_half && e.shadow_reach == 40.0f);
    assert(std::abs(e.ao_strength - 0.3f) < 1e-4f);
    // Custom: the AO's options (reach wider: 4 m, at least 2 rays; with the AO on).
    settings.rt_ao_quality = TierMedium;
    e = RayTracingEffective();
    assert(e.ao_combine && e.ao_full && std::abs(e.ao_direct - 0.5f) < 1e-4f && e.shadow_replace);
    assert(e.ao_radius == 4.0f && e.ao_rays == 2);
    assert(settings.rt_ao_reach == AoReachWider && std::string(AoReachName(AoReachWide)) == "wide");
    settings.rt_ao_quality = TierOff;
    settings.rt_ao_reach = AoReachTier;
    const struct {
        float radius;
        int rays;
    } ao_tiers[] = {{0.75f, 1}, {1.0f, 1}, {1.0f, 2}, {1.25f, 2}};
    const struct {
        bool half;
        float reach;
    } shadow_tiers[] = {{true, 6.0f}, {true, 15.0f}, {false, 15.0f}, {false, 40.0f}};
    for (int t = TierLow; t < TierCount; ++t) {
        settings.rt_ao_quality = t;
        settings.rt_shadow_quality = t;
        e = RayTracingEffective();
        assert(e.ao && e.ao_radius == ao_tiers[t - 1].radius && e.ao_rays == ao_tiers[t - 1].rays);
        assert(e.shadows && e.shadow_half == shadow_tiers[t - 1].half &&
               e.shadow_reach == shadow_tiers[t - 1].reach);
    }
    // RayTracingTiers: what the menu's Custom starts from.
    int ao = -1, shadows = -1;
    RayTracingTiers(RtHigh, ao, shadows);
    assert(ao == TierMedium && shadows == TierMedium);
    RayTracingTiers(RtUltra, ao, shadows);
    assert(ao == TierUltra && shadows == TierUltra);

    // Files from before the tiers, the levels' tiers and where Custom starts: the cases the
    // launcher's test reads too (tests/data/rt_settings.txt). Each file is loaded from the
    // launcher's defaults, as the launcher reads it.
    const auto tier_of = [&](const std::string& name) {
        for (int t = 0; t < TierCount; ++t) {
            if (name == RtTierName(t)) return t;
        }
        assert(!"unknown tier");
        return 0;
    };
    const auto level_of = [&](const std::string& name) {
        for (int q = 0; q < RtQualityCount; ++q) {
            if (name == RayTracingName(q)) return q;
        }
        assert(!"unknown level");
        return 0;
    };
    int cases = 0;
    std::ifstream table(BB_TEST_DATA "/rt_settings.txt");
    assert(table);
    for (std::string line; std::getline(table, line);) {
        if (line.empty() || line[0] == '#') continue;
        const auto bar1 = line.find('|'), bar2 = line.find('|', bar1 + 1);
        assert(bar1 != std::string::npos && bar2 != std::string::npos);
        const auto trim = [](std::string s) {
            s.erase(0, s.find_first_not_of(' '));
            s.erase(s.find_last_not_of(' ') + 1);
            return s;
        };
        const std::string kind = trim(line.substr(0, bar1));
        const std::string input = trim(line.substr(bar1 + 1, bar2 - bar1 - 1));
        std::istringstream in(input), out(trim(line.substr(bar2 + 1)));
        if (kind == "migrate") {
            std::string text = input;
            std::replace(text.begin(), text.end(), ';', '\n');
            Write(path, text + "\n");
            settings.ray_tracing = RtOff;
            settings.rt_ao_quality = TierOff;
            settings.rt_shadow_quality = TierOff;
            Load();
            std::string level, ao, shadows;
            out >> level >> ao >> shadows;
            if (settings.ray_tracing != level_of(level) || settings.rt_ao_quality != tier_of(ao) ||
                settings.rt_shadow_quality != tier_of(shadows)) {
                std::printf("migrate %s: got %s %s %s\n", input.c_str(),
                            RayTracingName(settings.ray_tracing), RtTierName(settings.rt_ao_quality),
                            RtTierName(settings.rt_shadow_quality));
                assert(!"migration case");
            }
        } else if (kind == "level") {
            std::string ao, shadows;
            out >> ao >> shadows;
            int a = -1, s = -1;
            RayTracingTiers(level_of(input), a, s);
            assert(a == tier_of(ao) && s == tier_of(shadows));
        } else if (kind == "custom") {
            std::string from, ao, shadows, want_ao, want_shadows;
            float strength = 0.0f, want_strength = 0.0f;
            in >> from >> ao >> shadows >> strength;
            out >> want_ao >> want_shadows >> want_strength;
            int a = tier_of(ao), s = tier_of(shadows);
            const bool changed = CustomStart(level_of(from), a, s, strength);
            assert(a == tier_of(want_ao) && s == tier_of(want_shadows));
            assert(std::abs(strength - want_strength) < 1e-4f);
            assert(changed == (ao != want_ao || shadows != want_shadows));
        } else {
            assert(!"unknown case kind");
        }
        ++cases;
    }
    assert(cases >= 30);
    // Dropped on save: below, after the menu writes the file.

    // The environment over the file: a tier or level it can read; otherwise the file's. The
    // variables for the keys before the tiers count only for files without tiers.
    const auto env = [](const char* name, const char* value) {
#ifdef _WIN32
        _putenv_s(name, value ? value : "");
#else
        value ? setenv(name, value, 1) : unsetenv(name);
#endif
    };
    Write(path, "ray_tracing=low\nrt_ao_quality=low\nrt_shadow_quality=low\n");
    env("BB_RT_AO_QUALITY", "high");
    env("BB_RAY_TRACING", "ultra");
    Load();
    assert(settings.rt_ao_quality == TierHigh && settings.ray_tracing == RtUltra);
    env("BB_RT_AO_QUALITY", "High");
    env("BB_RAY_TRACING", "max");
    Load();
    assert(settings.rt_ao_quality == TierLow && settings.ray_tracing == RtLow);
    env("BB_RT_AO_QUALITY", nullptr);
    env("BB_RAY_TRACING", nullptr);
    env("BB_SHADOWS", "game");
    Load();
    assert(settings.rt_shadow_quality == TierLow); // retired: the file's tier stays
    env("BB_SHADOWS", nullptr);
    Write(path, "shadows=raytraced\nrt_shadow_reach=4\n");
    env("BB_RT_SHADOW_REACH", "20");
    Load();
    assert(settings.rt_shadow_quality == TierHigh); // no tiers in the file: it counts
    env("BB_RT_SHADOW_REACH", nullptr);

    // The menu: tiers as their index, strength in tenths; written once, old keys dropped.
    Write(path, "ambient_occlusion=raytraced\nrt_ao_rays=2\nshadows=raytraced\nrt_shadow_reach=4\n");
    Load();
    bbgpu_setting_set("rt_ao_quality", TierLow);
    bbgpu_setting_set("rt_ao_quality", TierHigh);
    bbgpu_setting_set("rt_shadow_quality", TierUltra);
    bbgpu_setting_set("rt_ao_strength", 7); // 0.7
    int value = -1;
    assert(bbgpu_setting_get("rt_ao_quality", &value) == 1 && value == TierHigh);
    assert(bbgpu_setting_get("rt_shadow_quality", &value) == 1 && value == TierUltra);
    assert(bbgpu_setting_get("rt_ao_strength", &value) == 1 && value == 7);
    for (const char* key : {"ray_tracing", "rt_ao_quality", "rt_shadow_quality", "rt_ao_strength"}) {
        assert(Count(path, key) == 1);
    }
    for (const char* key : {"ambient_occlusion", "shadows", "rt_ao_radius", "rt_ao_rays",
                            "rt_shadow_reach"}) {
        assert(Count(path, key) == 0);
    }
    settings.rt_ao_quality = TierOff;
    Load();
    assert(settings.rt_ao_quality == TierHigh && settings.rt_shadow_quality == TierUltra);
    assert(std::abs(settings.rt_ao_strength - 0.7f) < 1e-4f);

    // The level from the menu: index in, name in the file, written once; wanted at start once
    // Load sees it.
    bbgpu_setting_set("ray_tracing", RtOff);
    Load();
    assert(!RayTracingWanted());
    bbgpu_setting_set("ray_tracing", RtUltra);
    assert(bbgpu_setting_get("ray_tracing", &value) == 1 && value == RtUltra);
    assert(Count(path, "ray_tracing") == 1);
    {
        std::ifstream in(path);
        std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        assert(text.find("ray_tracing=ultra\n") != std::string::npos);
    }
    assert(!RayTracingWanted()); // a restart away
    Load();
    assert(settings.ray_tracing == RtUltra && RayTracingWanted());

    // ShadowTierReach helper: default distances per tier.
    assert(ShadowTierReach(TierOff) == 4.0f);
    assert(ShadowTierReach(TierLow) == 6.0f);
    assert(ShadowTierReach(TierMedium) == 15.0f);
    assert(ShadowTierReach(TierHigh) == 15.0f);
    assert(ShadowTierReach(TierUltra) == 40.0f);
    assert(ShadowTierReach(-1) == 4.0f);
    assert(ShadowTierReach(999) == 4.0f);

    // rt_shadow_reach_custom: parsed and clamped [0.0, 150.0].
    settings.rt_shadow_reach_custom = 0.0f;
    Write(path, "ray_tracing=custom\nrt_shadow_quality=medium\nrt_shadow_reach_custom=25.5\n");
    Load();
    assert(std::abs(settings.rt_shadow_reach_custom.load() - 25.5f) < 1e-4f);
    Write(path, "rt_shadow_reach_custom=200.0\n");
    Load();
    assert(settings.rt_shadow_reach_custom.load() == 150.0f);
    Write(path, "rt_shadow_reach_custom=-10.0\n");
    Load();
    assert(settings.rt_shadow_reach_custom.load() == 0.0f);

    // Tier defaults strictly preserved for non-custom tiers even if custom reach is set.
    settings.rt_shadow_reach_custom = 50.0f;
    for (int lvl = RtOff; lvl <= RtUltra; ++lvl) {
        settings.ray_tracing = lvl;
        auto eff = RayTracingEffective();
        if (lvl == RtLow) {
            // Low ray_tracing has shadows Off
            assert(!eff.shadows && eff.shadow_reach == 4.0f);
        } else if (lvl == RtMedium) {
            // Medium ray_tracing uses TierLow shadows (6 m)
            assert(eff.shadows && eff.shadow_reach == 6.0f);
        } else if (lvl == RtHigh) {
            // High ray_tracing uses TierMedium shadows (15 m)
            assert(eff.shadows && eff.shadow_reach == 15.0f);
        } else if (lvl == RtUltra) {
            // Ultra ray_tracing uses TierUltra shadows (40 m)
            assert(eff.shadows && eff.shadow_reach == 40.0f);
        }
    }

    // Custom tier: when rt_shadow_reach_custom <= 0, uses shadow tier default.
    settings.ray_tracing = RtCustom;
    settings.rt_shadow_quality = TierMedium;
    settings.rt_shadow_reach_custom = 0.0f;
    assert(RayTracingEffective().shadow_reach == 15.0f);
    settings.rt_shadow_quality = TierUltra;
    assert(RayTracingEffective().shadow_reach == 40.0f);

    // Custom tier: when rt_shadow_reach_custom > 0, overrides tier reach.
    settings.rt_shadow_reach_custom = 30.0f;
    assert(RayTracingEffective().shadow_reach == 30.0f);
    settings.rt_shadow_reach_custom = 0.5f; // clamped min 1.0f in RayTracingEffective
    assert(RayTracingEffective().shadow_reach == 1.0f);

    // Persistence: only saved when RtCustom and > 0.0f.
    settings.ray_tracing = RtCustom;
    settings.rt_shadow_reach_custom = 42.0f;
    Save();
    assert(Count(path, "rt_shadow_reach_custom") == 1);
    settings.rt_shadow_reach_custom = 0.0f;
    Load();
    assert(std::abs(settings.rt_shadow_reach_custom.load() - 42.0f) < 1e-4f);

    // Non-custom tier omits rt_shadow_reach_custom on Save.
    settings.ray_tracing = RtHigh;
    Save();
    assert(Count(path, "rt_shadow_reach_custom") == 0);

    // BB_RT_SHADOW_REACH_CUSTOM environment override.
#ifdef _WIN32
    _putenv_s("BB_RT_SHADOW_REACH_CUSTOM", "75.0");
#else
    setenv("BB_RT_SHADOW_REACH_CUSTOM", "75.0", 1);
#endif
    Write(path, "ray_tracing=custom\nrt_shadow_quality=high\nrt_shadow_reach_custom=10.0\n");
    Load();
    assert(std::abs(settings.rt_shadow_reach_custom.load() - 75.0f) < 1e-4f);
#ifdef _WIN32
    _putenv_s("BB_RT_SHADOW_REACH_CUSTOM", "");
#else
    unsetenv("BB_RT_SHADOW_REACH_CUSTOM");
#endif
    Load();
    assert(std::abs(settings.rt_shadow_reach_custom.load() - 10.0f) < 1e-4f);

    std::filesystem::remove(path);
    std::puts("Ray tracing settings: names, tiers, levels, migration, custom reach, menu and single keys PASS");
}
