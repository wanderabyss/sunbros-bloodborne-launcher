// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_settings.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <chrono>
#include <initializer_list>
#include <string>
#include <tuple>

int main() {
    using namespace BbSettings;
    const auto path = std::filesystem::temp_directory_path() /
        ("bb-output-settings-" + std::to_string(
            std::chrono::steady_clock::now().time_since_epoch().count()) + ".ini");
#ifdef _WIN32
    _putenv_s("BB_CONFIG", path.string().c_str());
    _putenv_s("BB_RENDER_RES", "");
#else
    setenv("BB_CONFIG", path.string().c_str(), 1);
    unsetenv("BB_RENDER_RES");
#endif
    auto& settings = Get();
    for (const char* size : {"1920x1080", "1920x1200", "3840x1600", "5000x2000", "1080x1920", "1280x800"}) {
        FILE* file = std::fopen(path.string().c_str(), "w");
        assert(file);
        std::fprintf(file, "output_res=%s\n", size);
        std::fclose(file);
        Load();
        int w = 0, h = 0;
        assert(std::sscanf(size, "%dx%d", &w, &h) == 2);
        assert(OutputWidths[settings.output_res] == w && OutputHeights[settings.output_res] == h);
        Save();
        settings.output_res = OutputDefault;
        Load();
        assert(OutputWidths[settings.output_res] == w && OutputHeights[settings.output_res] == h);
    }
    // Custom 16:9 sizes outside the list, and odd sides rounded down to even (3682x2071 fell
    // back to 1080p: upscaler output and window), as patches.py output_size does.
    for (const auto& [text, w, h] : {std::tuple{"3200x1800", 3200, 1800},
                                     std::tuple{"2880x1620", 2880, 1620},
                                     std::tuple{"3682x2071", 3682, 2070},
                                     std::tuple{"2561x1441", 2560, 1440}}) {
        FILE* file = std::fopen(path.string().c_str(), "w");
        assert(file);
        std::fprintf(file, "output_res=%s\n", text);
        std::fclose(file);
        settings.output_res = OutputDefault;
        Load();
        assert(OutputWidths[settings.output_res] == w && OutputHeights[settings.output_res] == h);
        // A listed size takes its own index; the window (WindowedSize) reads this slot.
        assert((settings.output_res == OutputCustom) == (w != 2560));
    }
#ifdef _WIN32
    _putenv_s("BB_OUTPUT_RES", "3200x1800");
#else
    setenv("BB_OUTPUT_RES", "3200x1800", 1);
#endif
    Load(); // BB_OUTPUT_RES over the file's 2561x1441
    assert(OutputWidths[settings.output_res] == 3200 && OutputHeights[settings.output_res] == 1800);
#ifdef _WIN32
    _putenv_s("BB_OUTPUT_RES", "");
#else
    unsetenv("BB_OUTPUT_RES");
#endif
    for (const char* bad : {"999999999999999999999x1080", "0x0", "254x1080", "1920x143",
                           "hello", "1920x1080junk", "+1920x1080", "1920x1080x2"}) {
        FILE* file = std::fopen(path.string().c_str(), "w");
        assert(file);
        std::fprintf(file, "output_res=%s\n", bad);
        std::fclose(file);
        settings.output_res = OutputDefault;
        Load();
        assert(settings.output_res == OutputDefault);
    }
    settings.startup_output_res = OutputDefault;
    settings.output_res = 2; // 2560x1440, same aspect as the startup output.
    assert(!AspectNeedsRestart() && !ResolutionNeedsRestart());
    settings.output_res = 12; // 1920x1200: the in-game 16:10 choice needs a restart.
    assert(OutputWidths[settings.output_res] == 1920 && OutputHeights[settings.output_res] == 1200);
    assert(AspectNeedsRestart() && ResolutionNeedsRestart());
    settings.output_res = 6; // 3440x1440, different camera and HUD aspect.
    assert(AspectNeedsRestart() && ResolutionNeedsRestart());
    // Present upscale (bbport.ini present_upscale / present_rcas, BB_PRESENT_UPSCALE /
    // BB_PRESENT_RCAS): the defaults, the file, malformed values, the environment and Save.
    const auto write = [&](const char* text) {
        FILE* file = std::fopen(path.string().c_str(), "w");
        assert(file);
        std::fputs(text, file);
        std::fclose(file);
        Load();
    };
    const auto close_to = [](float a, float b) { return a > b - 1e-4f && a < b + 1e-4f; };
    settings.present_upscale = PresentUpscaleLinear;
    settings.present_rcas = 3.0f;
    write("output_res=2560x1440\n");
    assert(settings.present_upscale == PresentUpscaleEasu);
    assert(close_to(settings.present_rcas, PresentRcasDefault) && PresentRcasDefault == 0.0f);
    assert(!PresentUsesRcas(PresentRcasDefault)); // EASU alone unless present_rcas asks for RCAS
    write("present_upscale=linear\npresent_rcas=0\n");
    assert(settings.present_upscale == PresentUpscaleLinear && settings.present_rcas == 0.0f);
    assert(!PresentUsesRcas(settings.present_rcas));
    write("present_upscale=easu\npresent_rcas=0.5\n");
    assert(settings.present_upscale == PresentUpscaleEasu && close_to(settings.present_rcas, 0.5f));
    write("present_upscale=bilinear\npresent_rcas=off\n");
    assert(settings.present_upscale == PresentUpscaleLinear && settings.present_rcas == 0.0f);
    write("present_upscale=fsr1\npresent_rcas=-1\n");
    assert(settings.present_upscale == PresentUpscaleEasu && settings.present_rcas == 0.0f);
    write("present_upscale=sharp\npresent_rcas=lots\n"); // malformed: the defaults
    assert(settings.present_upscale == PresentUpscaleEasu);
    assert(close_to(settings.present_rcas, PresentRcasDefault));
    write("present_rcas=99\n");
    assert(close_to(settings.present_rcas, PresentRcasMax));
    write("present_upscale=linear\npresent_rcas=1.5\n");
    Save(); // keeps the user's lines as they are
    settings.present_upscale = PresentUpscaleEasu;
    settings.present_rcas = PresentRcasDefault;
    Load();
    assert(settings.present_upscale == PresentUpscaleLinear && close_to(settings.present_rcas, 1.5f));
#ifdef _WIN32
    _putenv_s("BB_PRESENT_UPSCALE", "easu");
    _putenv_s("BB_PRESENT_RCAS", "0");
#else
    setenv("BB_PRESENT_UPSCALE", "easu", 1);
    setenv("BB_PRESENT_RCAS", "0", 1);
#endif
    Load(); // the environment over the file
    assert(settings.present_upscale == PresentUpscaleEasu && settings.present_rcas == 0.0f);
#ifdef _WIN32
    _putenv_s("BB_PRESENT_UPSCALE", "");
    _putenv_s("BB_PRESENT_RCAS", "");
#else
    unsetenv("BB_PRESENT_UPSCALE");
    unsetenv("BB_PRESENT_RCAS");
#endif
    assert(std::string{PresentUpscaleName(PresentUpscaleEasu)} == "easu");
    assert(std::string{PresentUpscaleName(PresentUpscaleLinear)} == "linear");
    // EASU only for a real upscale: 1440p and 1080p to a 4K frame, not equal sizes, not a
    // downscale (5K to 4K), not one axis larger, not with linear chosen.
    assert(PresentUsesEasu(PresentUpscaleEasu, 2560, 1440, 3840, 2160));
    assert(PresentUsesEasu(PresentUpscaleEasu, 1920, 1080, 3840, 2160));
    assert(PresentUsesEasu(PresentUpscaleEasu, 3840, 1600, 3840, 2160));
    assert(!PresentUsesEasu(PresentUpscaleEasu, 3840, 2160, 3840, 2160));
    assert(!PresentUsesEasu(PresentUpscaleEasu, 5120, 2880, 3840, 2160));
    assert(!PresentUsesEasu(PresentUpscaleEasu, 3440, 2400, 3840, 2160));
    assert(!PresentUsesEasu(PresentUpscaleLinear, 2560, 1440, 3840, 2160));
    assert(!PresentUsesEasu(PresentUpscaleEasu, 0, 0, 3840, 2160));
    assert(PresentUsesRcas(0.2f) && !PresentUsesRcas(0.0f) && !PresentUsesRcas(-1.0f));
    std::filesystem::remove(path);
    std::puts("Custom output settings: save/load and malformed input rejection PASS");
    std::puts("Present upscale settings: defaults, file, environment and EASU choice PASS");
}
