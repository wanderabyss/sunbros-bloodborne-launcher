// SPDX-License-Identifier: GPL-2.0-or-later
// bbport shader pre-build, offline check: translates every shader permutation a pipeline cache
// knows (its .meta: the specialization and resource layout a draw saw) from the program code
// in the player's own game files, without the game, and compares the SPIR-V with the cache's.
// The translation is the game's own (vk_shader_prebuild.h, used by the pipeline cache warm-up).
//
//   bb-shader-prebuild <cache dir> <code dir> [--write | --rejects <file>]
//
// <code dir> is scripts/shader_code.py's output. With --write the translated SPIR-V replaces
// the cache's where it differs. --rejects lists the .meta records whose translation differs
// from the cache's SPIR-V or fails, one name a line: shader_catalog.py leaves them out of the
// catalog, so they compile while playing as before instead of from a translation not proven.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>
#include <vector>

#include "common/serdes.h"
#include "shader_recompiler/frontend/fetch_shader.h"
#include "shader_recompiler/info.h"
#include "shader_recompiler/profile.h"
#include "shader_recompiler/specialization.h"
#include "video_core/renderer_vulkan/vk_shader_prebuild.h"

namespace Vulkan {
bool LoadShaderMeta(Serialization::Archive& ar, Shader::Info& info,
                    std::optional<Shader::Gcn::FetchShaderData>& fetch_shader_data,
                    Shader::StageSpecialization& spec, size_t& perm_idx, bool* spirv_current);
}

namespace fs = std::filesystem;

static std::vector<u8> ReadFile(const fs::path& path) {
    std::ifstream file(path, std::ios::binary);
    return std::vector<u8>((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
}

int main(int argc, char** argv) {
    if (argc < 3) {
        std::fprintf(stderr, "usage: bb-shader-prebuild <cache dir> <code dir> [--write]\n");
        return 2;
    }
    const fs::path cache = argv[1];
    const bool write = argc > 3 && std::strcmp(argv[3], "--write") == 0;
    std::ofstream rejects;
    if (argc > 4 && std::strcmp(argv[3], "--rejects") == 0) {
        rejects.open(argv[4]);
    }
#ifdef _WIN32
    _putenv_s("BB_SHADER_CODE", argv[2]);
#else
    setenv("BB_SHADER_CODE", argv[2], 1);
#endif
    if (!Vulkan::Prebuild::Available()) {
        std::fprintf(stderr, "no code folder %s\n", argv[2]);
        return 2;
    }

    const auto profile_blob = ReadFile(cache / "profile.bin");
    if (profile_blob.size() != sizeof(Shader::Profile)) {
        std::fprintf(stderr, "no usable profile.bin in %s\n", cache.string().c_str());
        return 2;
    }
    Shader::Profile profile{};
    std::memcpy(&profile, profile_blob.data(), sizeof(profile));

    u32 total = 0, identical = 0, different = 0, skipped = 0, failed = 0;
    for (const auto& entry : fs::directory_iterator(cache)) {
        if (entry.path().extension() != ".meta") {
            continue;
        }
        ++total;
        Serialization::Archive ar{ReadFile(entry.path())};
        Shader::Info stored{};
        std::optional<Shader::Gcn::FetchShaderData> fetch;
        Shader::StageSpecialization spec{};
        size_t perm_idx = 0;
        bool spirv_current = true;
        if (!Vulkan::LoadShaderMeta(ar, stored, fetch, spec, perm_idx, &spirv_current)) {
            ++skipped; // another metadata version, or a motion-vector shader (session-local)
            continue;
        }
        if (const char* only = std::getenv("BB_PREBUILD_SHOW"); only && *only) {
            if (std::strtoull(only, nullptr, 16) == stored.pgm_hash) {
                std::printf("%s: perm %zu, %zu vertex inputs, fetch %s, motion %d\n",
                            entry.path().filename().string().c_str(), perm_idx,
                            spec.vs_attribs.size(), fetch ? "yes" : "no",
                            int(spec.runtime_info.hw.vs.motion_vectors));
            }
            continue;
        }
        const std::vector<u32> spv =
            Vulkan::Prebuild::Translate(stored, fetch, spec, perm_idx, profile);
        if (spv.empty()) {
            ++failed;
            if (rejects.is_open()) {
                rejects << entry.path().filename().string() << '\n';
            }
            continue;
        }
        char spv_name[64];
        std::snprintf(spv_name, sizeof(spv_name), "0x%016llx_%zu.spv",
                      (unsigned long long)stored.pgm_hash, perm_idx);
        const auto cached = ReadFile(cache / spv_name);
        const bool same = cached.size() == spv.size() * 4 &&
                          std::memcmp(cached.data(), spv.data(), cached.size()) == 0;
        if (same) {
            ++identical;
        } else {
            ++different;
            if (rejects.is_open()) {
                rejects << entry.path().filename().string() << '\n';
            }
            if (different <= 8) {
                std::printf("differs: %s (%zu bytes cached, %zu translated)\n", spv_name,
                            cached.size(), spv.size() * 4);
            }
            if (write) {
                std::ofstream(cache / spv_name, std::ios::binary)
                    .write(reinterpret_cast<const char*>(spv.data()), spv.size() * 4);
            }
        }
    }
    std::printf("shader pre-build: %u permutations: %u identical, %u different, %u skipped, "
                "%u could not be translated\n",
                total, identical, different, skipped, failed);
    return failed ? 1 : 0;
}
