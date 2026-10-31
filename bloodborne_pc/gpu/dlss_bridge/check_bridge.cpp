#include <windows.h>
#include <cstdio>
#include <filesystem>
#include "bbport_dlss_bridge.h"

int wmain(int argc, wchar_t** argv) {
    if (argc != 2) {
        std::fprintf(stderr, "Usage: bbport-dlss-check <bbport_dlss.dll>\n");
        return 2;
    }
    const auto path = std::filesystem::absolute(argv[1]);
    HMODULE module = LoadLibraryExW(path.c_str(), nullptr,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if (!module) {
        std::fprintf(stderr, "Cannot load DLSS bridge (Windows error %lu)\n", GetLastError());
        return 1;
    }
    const auto get = reinterpret_cast<BbDlssGetApiFn>(GetProcAddress(module, "BbDlssGetApi"));
    const auto* api = get ? get() : nullptr;
    // Read appended members only after checking the ABI: old DLLs have a shorter struct.
    const bool valid = api && api->abi == BBPORT_DLSS_BRIDGE_ABI &&
        api->Configure && api->InstanceExtensions && api->DeviceExtensions &&
        api->Initialize && api->CreateFeature && api->Evaluate && api->ReleaseFeature &&
        api->Shutdown && api->FrameGenMaxCount && api->FrameGenCreate &&
        api->FrameGenEvaluate && api->FrameGenRelease && api->NeuralRenderSupported &&
        api->NeuralRenderCreate && api->NeuralRenderEvaluate && api->NeuralRenderRelease;
    if (valid) {
        std::printf("DLSS bridge ABI %u: SR, Frame Generation and neural rendering entry points "
                    "verified\n", api->abi);
    } else {
        std::fprintf(stderr, "Invalid DLSS bridge ABI/API (found %u, require %u). Rebuild with packaging/windows/build_dlss.sh\n",
                     api ? api->abi : 0u, BBPORT_DLSS_BRIDGE_ABI);
    }
    FreeLibrary(module);
    return valid ? 0 : 1;
}
