// SPDX-License-Identifier: GPL-2.0-or-later
// Saved FSR 4 choices must be safe before the first rendered frame on older GPUs.
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <initializer_list>
#include <string>
#include "bbport_settings.h"

namespace {

// POSIX setenv/unsetenv, also on Windows (MSYS2 CLANG64 has neither).
void setenv(const char* name, const char* value, int) {
#ifdef _WIN32
    _putenv_s(name, value);
#else
    ::setenv(name, value, 1);
#endif
}

void unsetenv(const char* name) {
#ifdef _WIN32
    _putenv_s(name, "");
#else
    ::unsetenv(name);
#endif
}

} // namespace

int main() {
    using namespace BbSettings;
    const std::string config_path =
        (std::filesystem::temp_directory_path() /
         ("bbport-upscaler-test-" +
          std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) + ".ini"))
            .string();
    const char* path = config_path.c_str();
    std::fclose(std::fopen(path, "w"));
    setenv("BB_CONFIG", path, 1);
    unsetenv("BB_UPSCALER");
    unsetenv("BB_UPSCALE_PRESET");
    unsetenv("BB_RENDER_RES");
    auto& s = Get();
    s.upscaler = UpscalerTaa;
    s.preset = Performance;
    assert(RenderPreset() == NativeAA && s.preset == Performance);
    Save();
    s.upscaler = UpscalerOff;
    Load();
    assert(s.upscaler == UpscalerTaa && s.preset == Performance);
    assert(RenderPreset() == NativeAA && !ResolutionNeedsRestart());
    s.upscaler = UpscalerFsr3;
    assert(RenderPreset() == Performance);
    for (bool fsr4 : {false, true}) {
        for (bool fsr411 : {false, true}) {
            for (int requested = 0; requested < UpscalerCount; ++requested) {
                FILE* config = std::fopen(path, "w");
                assert(config);
                std::fprintf(config, "upscaler=%s\npreset=3\noutput_res=2560x1440\n",
                             UpscalerName(requested));
                std::fclose(config);
                s.fsr4_problem = nullptr;
                Load();
                assert(s.upscaler == requested);
                ConfigureUpscalerSupport(fsr4, fsr411);
                const bool unsupported = (requested == UpscalerFsr4 && !fsr4) ||
                    (requested == UpscalerFsr411 && !(fsr4 && fsr411));
                assert(s.upscaler == (unsupported ? UpscalerFsr3 : requested));
                assert(s.fsr4_supported == fsr4);
                assert(s.fsr411_supported == (fsr4 && fsr411));
                assert(bool(s.fsr4_problem.load()) == unsupported);
                assert(s.preset == Performance && s.output_res == 2);
                // Startup patch settings still describe the already applied guest patches.
                assert(s.startup_upscaler == requested);
                ConfigureUpscalerSupport(fsr4, fsr411);
                assert(s.upscaler == (unsupported ? UpscalerFsr3 : requested));
            }
        }
    }
    s.startup_preset = Quality;
    s.startup_upscaler = UpscalerFsr3;
    s.upscaler = UpscalerFsr3;
    s.preset = Performance;
    assert(RenderPreset() == Performance && !ResolutionNeedsRestart());
    // BB_RENDER_RES is read by Load, not every frame (FixedRenderSession caches it): reload,
    // keeping the session state this test sets up.
    const auto reread = [&s](const char* render_res) {
        setenv("BB_RENDER_RES", render_res, 1);
        const int startup_preset = s.startup_preset, startup_upscaler = s.startup_upscaler,
                  startup_output = s.startup_output_res, upscaler = s.upscaler,
                  preset = s.preset, output = s.output_res;
        Load();
        s.startup_preset = startup_preset;
        s.startup_upscaler = startup_upscaler;
        s.startup_output_res = startup_output;
        s.upscaler = upscaler;
        s.preset = preset;
        s.output_res = output;
    };
    reread("1706x960");
    assert(RenderPreset() == Quality && ResolutionNeedsRestart());
    s.preset = Quality;
    assert(!ResolutionNeedsRestart());
    s.upscaler = UpscalerOff;
    assert(ResolutionNeedsRestart());
    s.upscaler = UpscalerFsr4;
    assert(!ResolutionNeedsRestart()); // provider change at the same patched size is live
    s.upscaler = UpscalerTaa;          // TAA needs native guest targets
    assert(ResolutionNeedsRestart());
    s.upscaler = UpscalerFsr4;
    const int output = s.startup_output_res;
    s.output_res = (output + 1) % OutputCount;
    assert(ResolutionNeedsRestart());
    s.output_res = output;
    reread("");
    assert(!FixedRenderSession() && !ResolutionNeedsRestart());
    unsetenv("BB_RENDER_RES");
    // A failed optional DLSS device must fall back before rendering and keep the saved
    // choice so fixing CUDA/UVM restores DLSS on the next launch.
    {
        FILE* config = std::fopen(path, "w");
        assert(config);
        std::fputs("upscaler=dlss\npreset=3\noutput_res=2560x1440\n", config);
        std::fclose(config);
        Load();
        ConfigureDlssSupport(false, "Vulkan device creation failed with DLSS extensions");
        assert(s.upscaler == UpscalerFsr3 && !s.dlss_supported);
        assert(s.dlss_problem.load() && s.startup_upscaler == UpscalerDlss);
        assert(s.preset == Performance && s.output_res == 2);
        Load();
        assert(s.upscaler == UpscalerDlss);
        ConfigureDlssSupport(true, nullptr);
        assert(s.upscaler == UpscalerDlss && s.dlss_supported && !s.dlss_problem.load());
    }
    std::remove(path);
    std::puts("Upscaler support: saved choices and FSR 3.1 fallback PASS");
}
