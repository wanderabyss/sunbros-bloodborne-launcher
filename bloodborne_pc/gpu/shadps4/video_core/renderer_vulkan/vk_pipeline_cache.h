// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once
#include <array>
#include <atomic>
#include <condition_variable>
#include <deque>
#include <memory>
#include <mutex>
#include <thread>

#include <unordered_map>
#include <shared_mutex>
#include <variant>
#include <boost/container/static_vector.hpp>
#include <tsl/robin_map.h>
#include "shader_recompiler/profile.h"
#include "shader_recompiler/recompiler.h"
#include "shader_recompiler/specialization.h"
#include "video_core/renderer_vulkan/vk_compute_pipeline.h"
#include "video_core/renderer_vulkan/vk_graphics_pipeline.h"
#include "video_core/renderer_vulkan/vk_resource_pool.h"

template <>
struct std::hash<vk::ShaderModule> {
    std::size_t operator()(const vk::ShaderModule& module) const noexcept {
        return std::hash<size_t>{}(reinterpret_cast<size_t>((VkShaderModule)module));
    }
};

namespace AmdGpu {
class Liverpool;
}

namespace Serialization {
struct Archive;
}

namespace Shader {
struct Info;
}

namespace Vulkan {

class Instance;
class Scheduler;
class ShaderCache;

struct Program {
    struct Module {
        vk::ShaderModule module;
        Shader::StageSpecialization spec;
    };
    static constexpr size_t MaxPermutations = 8;
    using ModuleList = boost::container::small_vector<Module, MaxPermutations>;

    Shader::Info info;
    ModuleList modules{};
    size_t last_used = 0; ///< bbport: permutation of the previous lookup, compared first
    /// bbport: `info` as translated, for draw-preparation workers (they must not read `info`,
    /// whose user data the GPU thread rewrites every draw). Guarded by programs_mutex.
    std::unique_ptr<Shader::Info> info_template;

    Program() = default;
    Program(Shader::HwStage stage, Shader::SwStage l_stage, Shader::ShaderParams params)
        : info{stage, l_stage, params} {}

    void AddPermut(vk::ShaderModule module, Shader::StageSpecialization&& spec) {
        modules.emplace_back(module, std::move(spec));
    }

    void InsertPermut(vk::ShaderModule module, Shader::StageSpecialization&& spec,
                      size_t perm_idx) {
        modules.resize(std::max(modules.size(), perm_idx + 1)); // <-- beware of realloc
        modules[perm_idx] = {module, std::move(spec)};
    }
};

struct DrawIndirectParams {
    u16 vertex_sgpr_offset;
    u32 instance_sgpr_offset;
};

} // namespace Vulkan

namespace AmdGpu {
union Regs;
}

namespace Vulkan {

/// bbport: state of one graphics/compute pipeline selection. The GPU thread owns one
/// (PipelineCache::sel); draw-preparation workers use their own with their register copies.
struct PipelineSelection {
    const AmdGpu::Regs* regs{};
    std::array<Shader::RuntimeInfo, MaxShaderStages> runtime_infos{};
    std::array<const Shader::Info*, MaxShaderStages> infos{};
    std::array<vk::ShaderModule, MaxShaderStages> modules{};
    std::optional<Shader::Gcn::FetchShaderData> fetch_shader{};
    GraphicsPipelineKey graphics_key{};
    bool motion = false;
    DrawIndirectParams draw_indirect_params{};
    struct PrepWorker* worker{}; ///< set: read-only selection for a draw-preparation worker
};

/// bbport: a draw-preparation worker's own program state (see vk_draw_prep.h).
struct PrepWorker {
    struct Stage {
        const Program* program;
        u64 hash;
        Shader::HwStage hw_stage;
        VAddr pgm_base;
        const std::vector<u32>* flat;
    };
    // Node-based: stages keep pointers to these Infos while later stages are inserted.
    std::unordered_map<const Program*, Shader::Info> infos;
    boost::container::static_vector<Stage, MaxShaderStages> stages;
    bool failed = false;
};

struct PreparedDraw;

class PipelineCache {
public:
    explicit PipelineCache(const Instance& instance, Scheduler& scheduler,
                           AmdGpu::Liverpool* liverpool, u32 sparse_page_shift);
    ~PipelineCache();

    void WarmUp();
    void Sync();

    bool LoadComputePipeline(Serialization::Archive& ar);
    bool LoadGraphicsPipeline(Serialization::Archive& ar);
    bool LoadPipelineStage(Serialization::Archive& ar, size_t stage);

    const GraphicsPipeline* GetGraphicsPipeline(const DrawIndirectParams params = {},
                                                const PreparedDraw* prepared = nullptr);

    /// bbport: worker side of draw preparation: selects the pipeline key for `sel.regs` without
    /// creating anything. False when a program or permutation does not exist yet.
    bool PrepareGraphicsPipeline(PipelineSelection& sel);

    /// bbport: GPU-thread side: the pipeline for a prepared draw after checking that registers
    /// and flattened user data match; null to take the regular path.
    const GraphicsPipeline* TryPreparedPipeline(const PreparedDraw& prepared);

    /// bbport: the prepared draw the last GetGraphicsPipeline used, or null (regular path).
    [[nodiscard]] const PreparedDraw* UsedPrepared() const noexcept {
        return used_prepared;
    }

    const ComputePipeline* GetComputePipeline();

    /// bbport: a depth buffer a recorded draw used (vk_rasterizer.cpp), so the texture cache
    /// holds it as a depth image. Only draws writing such a buffer build their pipelines in the
    /// background: a draw left out never sets up its targets, and a buffer it would have been
    /// first to use could be made as a colour image by a later read.
    void NoteDepthTarget(u64 address) noexcept;

    using Result = std::tuple<const Shader::Info*, vk::ShaderModule,
                              std::optional<Shader::Gcn::FetchShaderData>, u64>;
    Result GetProgram(PipelineSelection& sel, Shader::HwStage stage, Shader::SwStage l_stage,
                      const Shader::ShaderParams& params, Shader::Backend::Bindings& binding);

    std::optional<vk::ShaderModule> ReplaceShader(vk::ShaderModule module,
                                                  std::span<const u32> spv_code);

    static std::string GetShaderName(Shader::HwStage stage, u64 hash,
                                     std::optional<size_t> perm = {});

    auto& GetProfile() const {
        return profile;
    }

private:
    void StartDriverCacheWorker();
    void SaveDriverCache();
    bool RefreshGraphicsKey(PipelineSelection& sel);
    bool RefreshGraphicsStages(PipelineSelection& sel);
    bool RefreshComputeKey();

    void DumpShader(std::span<const u32> code, u64 hash, Shader::HwStage stage, size_t perm_idx,
                    std::string_view ext);
    std::optional<std::vector<u32>> GetShaderPatch(u64 hash, Shader::HwStage stage, size_t perm_idx,
                                                   std::string_view ext);
    vk::ShaderModule CompileModule(Shader::Info& info, Shader::RuntimeInfo& runtime_info,
                                   const std::span<const u32>& code, size_t perm_idx,
                                   Shader::Backend::Bindings& binding);
    const Shader::RuntimeInfo& BuildRuntimeInfo(PipelineSelection& sel, Shader::HwStage stage,
                                                Shader::SwStage l_stage);

    [[nodiscard]] bool IsPipelineCacheDirty() const {
        return num_new_pipelines > 0;
    }

    /// bbport (BbToggle::AsyncEffectPipelines): a pipeline built on a background thread.
    struct PipelineJob;
    /// What the selected draw is. Effect: it blends every colour it writes and writes no depth;
    /// SceneGeometry: a G-buffer draw or another depth-tested triangle mesh writing a depth
    /// buffer drawn to before (NoteDepthTarget). Leaving either out for a few frames only delays
    /// an effect or an object the first time it is seen; Other (full-screen passes, depth
    /// buffers not drawn to yet, anything else) is built on the GPU thread.
    enum class DrawKind : u8 { Effect, SceneGeometry, Other };
    [[nodiscard]] DrawKind ClassifyDraw() const;
    [[nodiscard]] bool KnownDepthTarget(u64 address) const noexcept;
    [[nodiscard]] bool BuildsInBackground(DrawKind kind) const;
    void QueueBackgroundPipeline();
    const GraphicsPipeline* FinishBackgroundPipeline(PipelineJob& job);
    void RunPipelineJobs(std::stop_token stop);

private:
    const Instance& instance;
    Scheduler& scheduler;
    AmdGpu::Liverpool* liverpool;
    DescriptorHeap desc_heap;
    vk::UniquePipelineCache pipeline_cache;
    vk::UniquePipelineLayout pipeline_layout;
    Shader::Profile profile{};
    Shader::Pools pools;
    tsl::robin_map<size_t, std::unique_ptr<Program>> program_cache;
    /// bbport: exclusive for program/permutation insertions, shared for worker lookups.
    std::shared_mutex programs_mutex;
    u64 prepared_hits = 0, prepared_misses = 0;
    const PreparedDraw* used_prepared = nullptr;
    tsl::robin_map<ComputePipelineKey, std::unique_ptr<ComputePipeline>> compute_pipelines;
    tsl::robin_map<GraphicsPipelineKey, std::unique_ptr<GraphicsPipeline>> graphics_pipelines;
    PipelineSelection sel{}; ///< GPU thread selection state
    ComputePipelineKey compute_key{};
    std::atomic<u32> num_new_pipelines{}; // new pipelines added to the cache since the game start

    // Only if Config::collectShadersForDebug()
    tsl::robin_map<vk::ShaderModule,
                   std::vector<std::variant<GraphicsPipelineKey, ComputePipelineKey>>>
        module_related_pipelines;
    /// bbport: pipelines being built in the background, by key (GPU thread only), and the
    /// workers' queue.
    tsl::robin_map<GraphicsPipelineKey, std::shared_ptr<PipelineJob>> pending_pipelines;
    /// NoteDepthTarget's last addresses (written by the draw recording thread).
    std::array<std::atomic<u64>, 64> depth_targets{};
    std::atomic<u32> depth_targets_next{0};
    std::mutex jobs_mutex;
    std::condition_variable_any jobs_wake;
    std::deque<std::shared_ptr<PipelineJob>> jobs;
    // Declared last: joined before the driver cache or device references are destroyed.
    std::jthread driver_cache_worker;
    std::array<std::jthread, 2> pipeline_workers;
};

} // namespace Vulkan
