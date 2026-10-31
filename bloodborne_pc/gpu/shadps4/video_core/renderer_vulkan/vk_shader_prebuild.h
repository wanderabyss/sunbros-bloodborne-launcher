// SPDX-License-Identifier: GPL-2.0-or-later
// bbport shader pre-build: translates a shader permutation the pipeline cache knows (its stored
// specialization and resource layout) from the program code in the player's own game files,
// without the game: what the draw read through pointers in game memory comes from the cache.
// Same SPIR-V as the game compiles (bb-shader-prebuild checks it).
#pragma once

#include <filesystem>
#include <optional>
#include <vector>

#include "common/types.h"
#include "shader_recompiler/frontend/fetch_shader.h"
#include "shader_recompiler/info.h"
#include "shader_recompiler/profile.h"
#include "shader_recompiler/specialization.h"

namespace Vulkan::Prebuild {

/// The folder of program code extracted from the game files (scripts/shader_code.py:
/// <hash>.bin, and <hash>.copy.bin for a geometry shader's copy shader); BB_SHADER_CODE.
const std::filesystem::path& CodeDir();
bool Available();

/// The SPIR-V of one stored permutation, or empty when its code is not in the game files, its
/// draw-time inputs were not stored (an older cache), or translation failed. `translated`
/// receives the resource layout this translation produced: it depends on the GPU's features,
/// so a record made on another system is only an input, never the layout the pipeline uses.
std::vector<u32> Translate(const Shader::Info& stored,
                           const std::optional<Shader::Gcn::FetchShaderData>& fetch,
                           const Shader::StageSpecialization& spec, size_t perm_idx,
                           const Shader::Profile& profile, Shader::Info* translated = nullptr);

} // namespace Vulkan::Prebuild
