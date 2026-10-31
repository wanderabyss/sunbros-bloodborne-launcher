// SPDX-License-Identifier: GPL-2.0-or-later
// bbport shader pre-build (vk_shader_prebuild.h).
#include "video_core/renderer_vulkan/vk_shader_prebuild.h"

#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>

#include "shader_recompiler/backend/spirv/emit_spirv.h"
#include "shader_recompiler/recompiler.h"

namespace Vulkan::Prebuild {

namespace {
std::vector<u32> ReadCode(const std::filesystem::path& path) {
    std::ifstream file(path, std::ios::binary);
    const std::vector<char> bytes((std::istreambuf_iterator<char>(file)),
                                  std::istreambuf_iterator<char>());
    if (bytes.empty() || bytes.size() % 4) {
        return {};
    }
    std::vector<u32> code(bytes.size() / 4);
    std::memcpy(code.data(), bytes.data(), bytes.size());
    return code;
}

std::filesystem::path CodeFile(u64 hash, bool copy) {
    char name[48];
    std::snprintf(name, sizeof(name), "%016llx%s.bin", (unsigned long long)hash,
                  copy ? ".copy" : "");
    return CodeDir() / name;
}

/// Restores the offline hooks however translation ends.
struct OfflineInputs {
    OfflineInputs(const std::vector<u32>& flat, const Shader::TessellationDataConstantBuffer* tess,
                  const std::optional<Shader::Gcn::FetchShaderData>& fetch,
                  const std::array<std::optional<AmdGpu::Buffer>, 32>& sharps) {
        Shader::Info::offline_flat_ud = &flat;
        Shader::Info::offline_tess_constants = tess;
        Shader::Gcn::offline_fetch_shader = &fetch;
        Shader::Gcn::offline_attrib_sharps = &sharps;
    }
    ~OfflineInputs() {
        Shader::Info::offline_flat_ud = nullptr;
        Shader::Info::offline_tess_constants = nullptr;
        Shader::Gcn::offline_fetch_shader = nullptr;
        Shader::Gcn::offline_attrib_sharps = nullptr;
    }
};
} // namespace

const std::filesystem::path& CodeDir() {
    static const std::filesystem::path dir = [] {
        const char* env = std::getenv("BB_SHADER_CODE");
        return env && *env ? std::filesystem::path(env) : std::filesystem::path{};
    }();
    return dir;
}

bool Available() {
    std::error_code error;
    return !CodeDir().empty() && std::filesystem::is_directory(CodeDir(), error);
}

std::vector<u32> Translate(const Shader::Info& stored,
                           const std::optional<Shader::Gcn::FetchShaderData>& fetch,
                           const Shader::StageSpecialization& spec, size_t perm_idx,
                           const Shader::Profile& profile, Shader::Info* translated) {
    if (!Available() || (stored.hw_stage == Shader::HwStage::Hull && !spec.tess_constants)) {
        return {};
    }
    // Each vertex input's descriptor as the draw read it, by semantic.
    std::array<std::optional<AmdGpu::Buffer>, 32> sharps{};
    if (fetch) {
        if (spec.vs_attrib_sharps.size() != fetch->attributes.size()) {
            return {}; // stored before the descriptors were kept
        }
        for (size_t i = 0; i < fetch->attributes.size(); ++i) {
            if (fetch->attributes[i].semantic < sharps.size()) {
                sharps[fetch->attributes[i].semantic] = spec.vs_attrib_sharps[i];
            }
        }
    }
    const std::vector<u32> code = ReadCode(CodeFile(stored.pgm_hash, false));
    if (code.empty()) {
        return {};
    }
    // The user data the draw saw: the first registers of its flattened copy.
    std::array<u32, Shader::ShaderParams::NumShaderUserData> user_data{};
    std::memcpy(user_data.data(), stored.flattened_ud_buf.data(),
                std::min(stored.flattened_ud_buf.size(), user_data.size()) * sizeof(u32));
    const Shader::ShaderParams params{user_data, code, stored.pgm_hash};
    Shader::Info info(stored.hw_stage, stored.sw_stage, params);

    Shader::RuntimeInfo runtime_info = spec.runtime_info;
    // A program's first permutation is specialised after its translation, which counts the
    // emulated clip distances as one more fragment input (InjectClipDistanceAttributes): from
    // the stored count, translating would add it again - an extra input in 33 of 1066 shaders.
    if (perm_idx == 0 && stored.sw_stage == Shader::SwStage::Fragment &&
        runtime_info.hw.fs.clip_distance_emulation && runtime_info.hw.fs.num_inputs != 0) {
        --runtime_info.hw.fs.num_inputs;
    }
    std::vector<u32> copy_code;
    if (stored.hw_stage == Shader::HwStage::Geometry) {
        copy_code = ReadCode(CodeFile(runtime_info.hw.gs.vs_copy_hash, true));
        if (copy_code.empty()) {
            return {};
        }
        runtime_info.hw.gs.vs_copy = copy_code;
    }
    const OfflineInputs inputs{stored.flattened_ud_buf,
                               spec.tess_constants ? &*spec.tess_constants : nullptr, fetch,
                               sharps};
    try {
        Shader::Pools pools;
        Shader::Backend::Bindings binding = spec.start;
        const auto program = Shader::TranslateProgram(code, pools, info, runtime_info, profile);
        if (info.translation_failed) {
            return {};
        }
        auto spv = Shader::Backend::SPIRV::EmitSPIRV(profile, runtime_info, program, binding);
        if (translated) {
            *translated = info;
        }
        return spv;
    } catch (const std::exception&) {
        return {};
    }
}

} // namespace Vulkan::Prebuild
