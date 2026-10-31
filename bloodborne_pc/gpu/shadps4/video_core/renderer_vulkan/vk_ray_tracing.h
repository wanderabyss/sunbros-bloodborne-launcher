// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: hardware ray tracing: an
// acceleration structure of the scene the game draws, in world space, kept across frames.
// It works while the ray tracing setting turns an effect on (bbport.ini ray_tracing), or with
// BB_RT=1; it can be switched at any time. Its GPU memory is set up on first use and released
// ReleaseFrames after it was switched off. BB_RT=0: never (Instance then leaves the extensions
// off).
//
// The geometry is object motion's (vk_object_motion.h): G-buffer draws keep the clip position of
// every vertex they use, before the upscaler's jitter; with ray tracing on, every G-buffer draw
// is captured (as BB_OBJECT_MOTION_ALL=1). Clip positions go to world space with the camera of
// the scene constants (view = (clip.x / sx, clip.y / sy, clip.w), then the inverse view).
//
// GPU work, little CPU (section 0 of the plan):
// - Each static draw (and instance) gets its own bottom-level structure, built once (fast trace,
//   then compacted) and reused while its key matches. rt_instances.comp checks four of its
//   vertices against the stored ones every frame; a mismatch read back a few frames later
//   (never waited for) drops the structure, and a draw that keeps moving becomes dynamic.
// - Skinned or moving draws (dynamic) keep their structure and indices too; it is refit to this
//   frame's positions each frame and rebuilt every RebuildFrames.
// - Indices are copied and rebased on the GPU from the game's index buffers (rt_gather.comp),
//   only when a structure is built. New builds have a per-frame triangle budget.
// - rt_instances.comp writes the top-level instances (transform: world to this frame's view,
//   so rays are traced in view space, as the depth is). The CPU appends 32 bytes per instance.
//
// The top level is ready after Record; Scene() hands it to the passes that trace rays.

#pragma once

#include <array>
#include <atomic>
#include <cstdlib>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "common/types.h"
#include "video_core/renderer_vulkan/motion_history.h"
#include "video_core/renderer_vulkan/rt_key_map.h"
#include "video_core/renderer_vulkan/vk_common.h"

struct VmaAllocation_T;
typedef struct VmaAllocation_T* VmaAllocation;

namespace Vulkan {

class Instance;
class Scheduler;
class ObjectMotion;

class RayTracing {
public:
    RayTracing(const Instance& instance, Scheduler& scheduler, ObjectMotion* object_motion);
    ~RayTracing();

    /// The ray tracer of this run, or null (not allowed, no support, object motion off).
    static RayTracing* Get();
    /// Whether ray tracing may be used this run (not BB_RT=0): Instance enables the extensions
    /// where the GPU and driver have them.
    static bool Allowed();
    /// Whether ray tracing is on from the start (the setting is not Off, or BB_RT=1): object
    /// motion then sets aside room for every G-buffer draw's positions (fixed at start).
    static bool WantedAtStart();
    /// Whether the setting (or BB_RT=1) turns it on now, where it can run: object motion then
    /// holds every G-buffer draw's positions.
    [[nodiscard]] bool Wanted() const;
    /// Whether its structures and buffers are set up (they stay ReleaseFrames after it is
    /// switched off).
    [[nodiscard]] bool Holding() const noexcept {
        return enabled;
    }
    /// Whether the scene is captured and built this frame (decided at each frame start): object
    /// motion then captures every G-buffer draw, as the structure needs the static world too.
    [[nodiscard]] bool Active() const noexcept {
        return on.load(std::memory_order_relaxed);
    }

    struct DrawInput {
        u64 key;             ///< the mesh: shader, vertex streams, index data and range, instances
        u64 placement;       ///< hash of its world matrix, quantized (5 cm, 1/32); 0: unknown
        u64 matrix;          ///< hash of the same matrix, exact (0: unknown)
        /// Hash of what places its vertices, the bone palette and the world matrix (0: unknown):
        /// a dynamic structure whose pose is the one it was refit with needs no refit.
        u64 pose;
        std::array<float, 3> origin; ///< the matrix's translation, world space
        u32 store;           ///< object motion's first element of the draw (0: nothing stored)
        u32 vertices;        ///< elements stored for each instance
        u32 instances;       ///< instance i's elements follow at store + i * vertices
        u32 first_vertex;    ///< vertex index of the first stored element
        u64 index_address;   ///< GPU address of the draw's index data, or 0 for a non-indexed draw
        u32 index_count;
        u32 index_size;      ///< 2 or 4
        s32 base_vertex;
        bool dynamic;        ///< skinned, or its bones changed: refit every frame
        bool alpha_tested;   ///< the pixel shader discards (foliage, fences, hair): mask 0x02
        bool character;      ///< a character-size skeleton: opaque even when alpha-tested
    };
    /// A G-buffer triangle-list draw whose positions object motion stores this frame.
    void AddDraw(const DrawInput& draw);
    /// Start of a frame (with ObjectMotion::OnFrameStart).
    void OnFrameStart();

    struct Camera {
        std::array<float, 12> view;     ///< world to view, 3x4 rows
        std::array<float, 12> inv_view; ///< view to world, 3x4 rows
        std::array<float, 4> proj;      ///< x scale, y scale, z scale, z offset
        std::array<float, 2> jitter;    ///< viewport shift, render pixels
        std::array<float, 3> light;     ///< towards the moon, world space (zero: none)
    };
    /// At the upscaler (scene depth final, every G-buffer draw recorded): build the structure,
    /// and run the depth check on some frames. `depth_view`: the scene depth (General layout).
    void Record(vk::CommandBuffer cmdbuf, vk::ImageView depth_view, u32 width, u32 height,
                const Camera& camera);

    /// This frame's top level (after Record), or null. Instance masks: 0x01 opaque geometry
    /// (characters included), 0x02 see-through geometry (not opaque: ray queries see its
    /// triangles as candidates), 0x04 geometry pinned to the far plane (no ray should), 0x08 and
    /// 0x10 the same as 0x01 and 0x02 for structures kept though not drawn this frame (the
    /// effects' rays see them, the depth check does not).
    [[nodiscard]] vk::AccelerationStructureKHR Scene() const noexcept {
        return scene_ready ? tlas : vk::AccelerationStructureKHR{};
    }
    /// This frame's camera for the passes (rt_common.glsl FrameConstants), after Record; and
    /// last frame's, or 0 when last frame had none.
    [[nodiscard]] u64 FrameConstantsAddress() const noexcept {
        return scene_ready ? frames[slot].constants.address : 0;
    }
    /// CPU time the effects (vk_rt_effects.h) spent this frame, for the report.
    void NoteEffectsCpu(double microseconds) {
        sums.cpu_effects += microseconds;
    }
    /// Whether this frame's per-draw CPU work is timed (one frame in TimedStride); the
    /// rasterizer times ray tracing's object motion in the same frames.
    [[nodiscard]] bool TimedFrame() const noexcept {
        return timed_frame;
    }
    /// The rasterizer's object-motion work for the draws ray tracing adds (no character
    /// skeleton): the gate (did the bones change), index ranges (cached or scanned), the history
    /// (where the positions go), and the placement key up to AddDraw.
    enum class MotionPart : u8 { Gate, IndexRanges, History, Placement, Count };
    using MotionTimes = std::array<double, size_t(MotionPart::Count)>;
    /// Its CPU time in the last (timed) frame per part, microseconds, for the report.
    void NoteMotionCpu(const MotionTimes& microseconds) {
        if (microseconds[0] + microseconds[1] + microseconds[2] + microseconds[3] > 0.0) {
            for (size_t i = 0; i < microseconds.size(); ++i) {
                sums.cpu_motion[i] += microseconds[i];
            }
        }
    }
    /// The structures' coverage counts (rt_common.glsl CoverageStats), for the effects' rays.
    [[nodiscard]] u64 CoverageStatsAddress() const noexcept {
        return coverage_stats.address;
    }
    /// The frame counter (an effect that ran in frame N - 1 can use its history in frame N).
    [[nodiscard]] u64 FrameNumber() const noexcept {
        return frame;
    }
    [[nodiscard]] u64 PreviousFrameConstantsAddress() const noexcept {
        return scene_ready && previous_recorded + 1 == frame
                   ? frames[(slot + FrameSlots - 1) % FrameSlots].constants.address
                   : 0;
    }

private:
    struct Buffer {
        vk::Buffer buffer{};
        VmaAllocation allocation{};
        void* mapped{};
        u64 address{};
        vk::DeviceSize size{};
    };
    enum class State : u8 { Free, Pending, Ready };
    /// A cached bottom-level structure: one draw (one instance of it).
    struct Entry {
        u64 key = 0;
        u64 mesh = 0;            ///< DrawInput::key
        u64 matrix = 0;          ///< DrawInput::matrix when last drawn
        u64 pose = 0;            ///< dynamic: DrawInput::pose of the positions it holds
        State state = State::Free;
        bool dynamic = false;
        bool alpha = false;
        bool character = false;
        bool placed = false;     ///< keyed by placement
        bool compacting = false; ///< switched to its compacted copy, not copied yet
        u32 generation = 0;      ///< bumped on every reuse of the slot
        u32 vertices = 0, index_count = 0, triangles = 0; ///< of each part
        u32 parts = 1;           ///< geometries: a character drawn instanced has one per instance
        u32 distance = 0;        ///< dynamic: view distance in metres, read back (0: unknown)
        u64 last_used = 0, built = 0;
        vk::AccelerationStructureKHR blas{};
        Buffer storage{};        ///< the structure (dynamic: then its indices, at index_offset)
        vk::DeviceSize index_offset = 0;
        vk::DeviceSize build_scratch = 0, update_scratch = 0;
        u64 address = 0;         ///< device address of the structure
    };
    /// A draw instance of this frame that needs indices (a new build).
    struct IndexItem {
        u64 src, dst;
        u32 start, count;
        s32 rebase;
        u32 vertices, index_size, sig_slot, error_slot, pad;
    };
    static_assert(sizeof(IndexItem) == 48);
    /// A draw instance of this frame whose world positions a build needs.
    struct VertexItem {
        u64 dst;
        u32 start, count, store, pad[3];
    };
    static_assert(sizeof(VertexItem) == 32);
    /// A top-level instance of this frame (rt_instances.comp).
    struct InstanceItem {
        u64 blas;
        u32 custom;   ///< entry slot
        u32 flags;    ///< Instance* below
        u32 store, vertices;
        u32 siblings, sibling_count; ///< InstanceSiblings: its mesh's other structures (Record)
    };
    static_assert(sizeof(InstanceItem) == 32);
    static constexpr u32 InstanceVerify = 1, InstanceSignature = 2, InstanceNonIndexed = 4,
                         InstanceAlpha = 8, InstanceCharacter = 16, InstanceNew = 32,
                         InstanceKept = 64, InstanceSiblings = 128;
    /// A static instance without a placement key (instanced, or no world matrix) that no longer
    /// matches its structure may be another of its mesh's structures: rt_instances.comp looks for
    /// it among at most MaxSiblings of them (written per frame in Record) and uses it.
    static constexpr u32 MaxSiblings = 128;
    static constexpr u32 SiblingWords = 3 * 65535; ///< per frame: slot, address low, high
    static constexpr u32 SiblingMatch = 0x8000'0000u; ///< result word: | the matching slot
    /// A structure built or refit this frame (Record).
    struct Build {
        u32 slot;
        u32 vertex_item;   ///< its positions (VertexItem index)
        u64 indices;       ///< address of its rebased indices, 0: non-indexed
        bool update;       ///< refit (dynamic, built before)
    };
    struct Frame {
        u64 tick = 0;
        bool recorded = false;
        Buffer constants{}, index_items{}, vertex_items{}, instance_items{}, results{}, siblings{};
        std::vector<std::pair<u32, u32>> verified; ///< slot, generation of each result word
        std::vector<std::pair<u32, u32>> built;    ///< slot, generation of each build error word
        std::vector<std::pair<u32, u32>> queried;  ///< slot, generation of each size query
        /// Slot and generation of each structure in the sibling lists: a match the GPU reports
        /// FrameSlots frames later names a slot, maybe reused since.
        std::vector<std::pair<u32, u32>> siblings_listed;
        vk::QueryPool sizes{};
        Buffer check_counters{};
        bool checked = false;
    };
    /// An entry switched to its compacted copy (OnFrameStart); Record copies into it.
    struct Compaction {
        u32 slot, generation;
        Buffer old_storage;
        vk::AccelerationStructureKHR old_blas;
        u64 old_address;
    };

    /// Per-frame host buffers. A slot written at frame M was read by frame M-4 (its own) and
    /// frame M-3 (as the previous camera): OnFrameStart waits for both, normally long done.
    static constexpr u32 FrameSlots = 4;
    static constexpr u32 MaxEntries = 16384;
    static constexpr u32 MaxInstances = 16384;
    static constexpr u32 MaxInstancesPerDraw = 256;
    static constexpr u32 MaxItems = 8192;           ///< index and vertex items a frame
    /// New structures a frame; the rest wait for the next frames (entering an area spreads its
    /// buffer creation instead of stalling one frame).
    static constexpr u32 MaxNewPerFrame = 64;
    /// And, past MinNewPerFrame, no more once their creation took CreateBudgetUs on the CPU this
    /// frame (each is a size query, a buffer and a create call: area entry made one frame
    /// ~3 ms longer).
    static constexpr u32 MinNewPerFrame = 8;
    static constexpr double CreateBudgetUs = 250.0;
    /// Compacted copies made a frame; the rest wait for the next frames.
    static constexpr u32 MaxCompactPerFrame = 16;
    static constexpr u32 GatherVertices = 6u << 20; ///< world positions a frame (builds, refits)
    static constexpr u32 GatherIndices = 9u << 20;  ///< transient indices a frame (static builds)
    /// Dynamic: a full rebuild after this many refits (refits keep it right; the boxes only
    /// loosen as the pose changes).
    static constexpr u32 RebuildFrames = 90;
    static constexpr u64 UnusedFrames = 1800;       ///< evicted when not drawn for this long
    /// Off-screen casters: static structures drawn in the last KeepFrames but not this frame
    /// stay in the scene (mask 0x08, or 0x10 when see-through), at most MaxKept, the most recently
    /// drawn first; rt_instances.comp leaves out those farther than 60 m.
    static constexpr u64 KeepFrames = 1000;
    static constexpr u32 MaxKept = 4096;
    static constexpr u32 MismatchesToDynamic = 3;   ///< within MismatchWindow frames
    static constexpr u64 MismatchWindow = 600;
    /// A mesh seen moving (its matrix changed, or its small skeleton animated) is keyed by
    /// occurrence and refit every frame until it has not moved for MovingFrames.
    static constexpr u64 MovingFrames = 600;
    /// A placement-keyed structure built within this distance of one of last frame's that was
    /// not drawn again (metres): the same object, moved.
    static constexpr float NearMove = 2.0f;
    /// A placement-keyed structure built this frame (DetectMoves).
    struct Miss {
        u64 mesh;
        std::array<float, 3> origin;
        u32 slot, generation;
    };

    bool CreateResources();
    void ReleaseResources();
    /// Mapped buffers the CPU only writes (uploads) may live in VRAM the CPU can write (ReBAR);
    /// those it reads back stay in system memory.
    enum class Host { None, Write, Read };
    bool CreateBuffer(Buffer& out, vk::DeviceSize size, vk::BufferUsageFlags usage, Host host,
                      vk::DeviceSize alignment = 0);
    void DestroyBuffer(Buffer& buffer);
    void DeferDestroy(Buffer& buffer, vk::AccelerationStructureKHR& structure);
    bool EnsureScratch(vk::DeviceSize size);
    bool CreatePipelines();
    u32 AllocateEntry(u64 key);
    void FreeEntry(u32 slot);
    void ReadResults(Frame& frame);
    /// Frees what was not drawn for a while, and while over the budget; false: nothing freed.
    bool Evict(u64 target);
    void MarkMoving(u64 mesh);
    void DetectMoves();
    bool CreateStructure(Entry& entry, vk::DeviceSize size, vk::DeviceSize extra);
    void RecordCompaction(vk::CommandBuffer cmdbuf);

    const Instance& instance;
    Scheduler& scheduler;
    ObjectMotion* object_motion;
    bool available = false;      ///< supported, object motion on: may be switched on
    bool setup_failed = false;   ///< CreateResources failed: not tried again
    bool enabled = false;        ///< GPU resources set up
    std::atomic<bool> on{false}; ///< Active()
    u64 off_frames = 0;          ///< frames since it was switched off
    u64 level_file_frames = 0;   ///< BB_RT_LEVEL_FILE polling
    u64 mark_file_frames = 0;    ///< BB_TEST_MARK_FILE polling
    /// Switched off this long (frames): its structures and buffers are released.
    static constexpr u64 ReleaseFrames = 600;
    bool scene_ready = false;
    vk::Device device{};
    vk::DeviceSize scratch_alignment = 256;
    u64 budget_bytes = 768ull << 20;
    u64 build_budget = 1u << 20; ///< new static triangles a frame
    u32 check_every = 8;         ///< depth check every Nth frame while structures are new
                                 ///< (CheckNewFrames), else every 4 * Nth (0: never)
    static constexpr u64 CheckNewFrames = 240;
    u64 last_new_frame = 0;      ///< the last frame a structure was created
    u32 check_mask = 0xFF;       ///< instance mask of the check's rays (BB_RT_CHECK_MASK)

    // No lock (it cost a lock and unlock per draw): every call comes from the thread that
    // records draws, the GPU thread or the draw pipe's recording thread, one at a time (the
    // pipe is drained before the GPU thread records again).
    std::vector<Entry> entries;
    std::vector<u32> free_slots;
    RtKeyMap lookup;                           ///< key (with occurrence and instance) -> slot
    struct KeyHash {
        size_t operator()(u64 key) const noexcept {
            return size_t(key);
        }
    };
    Motion::FlatMap<u64, u32, KeyHash> occurrences; ///< this frame: draw key -> times seen
    /// Static draws found moving, and draws with bad indices: key -> the frame it was noted.
    /// Both expire (KeyMemoryFrames): a door that stopped is static again, a draw whose indices
    /// were bad in one frame (being rewritten) gets another try.
    std::unordered_map<u64, u64> dynamic_keys;
    std::unordered_map<u64, u64> failed_keys;
    static constexpr u64 KeyMemoryFrames = 3600;
    std::vector<u32> pending;                  ///< slots allocated this frame, not built yet
    std::vector<u32> kept_slots;               ///< candidates to keep (refreshed every 60 frames)
    std::unordered_map<u64, std::vector<u32>> mesh_slots; ///< mesh -> its structures' slots
    Motion::FlatMap<u64, u32, KeyHash> sibling_lists;   ///< Record: mesh -> its list + 1
    std::vector<u64> swap_stamps; ///< per slot: the ReadResults pass that swapped it, + 1
    std::vector<std::pair<u64, u32>> evict_candidates; ///< Evict's (last used, slot), reused
    u64 pressure_limit = 0;
    bool memory_pressure = false;
    u64 pressure_reclaimed = 0;
    u64 evict_after = 0;                       ///< over budget, nothing freed: no Evict before
    static constexpr u64 EvictRetryFrames = 16;
    std::unordered_map<u64, u64> moving_meshes; ///< mesh -> the last frame it moved
    std::vector<Miss> misses, previous_misses; ///< this frame's and last frame's
    std::vector<std::pair<u32, u32>> stale;    ///< slot, generation: freed at the next frame

    std::unordered_map<u64, std::pair<u32, u64>> mismatch_counts; ///< key -> count, last frame
    struct CompactReady {
        u32 slot, generation;
        u64 size; ///< compacted
    };
    std::vector<CompactReady> compact_ready;
    double create_us = 0.0; ///< this frame's structure creation, CPU microseconds
    /// Build sizes by shape (dynamic, indexed, parts, vertices, triangles): the same props
    /// repeat, and each query is a driver call.
    std::unordered_map<u64, std::array<vk::DeviceSize, 3>> size_cache;
    std::vector<Compaction> compact_switched;
    u64 used_bytes = 0;

    // This frame, from AddDraw.
    std::vector<IndexItem> index_items;
    std::vector<VertexItem> vertex_items;
    std::vector<InstanceItem> instance_items;
    std::vector<Build> builds;
    std::vector<std::pair<u32, u32>> verified;
    // Record's own lists, kept between frames (no allocation once grown).
    struct Batch {
        size_t first, count;
    };
    std::vector<Batch> record_batches;
    std::vector<vk::DeviceSize> record_scratch_offsets;
    std::vector<VkAccelerationStructureGeometryKHR> record_geometries;
    std::vector<VkAccelerationStructureGeometryKHR> size_geometries; ///< AddDraw's size queries
    std::vector<u32> size_primitives;
    std::vector<VkAccelerationStructureBuildGeometryInfoKHR> record_infos;
    std::vector<VkAccelerationStructureBuildRangeInfoKHR> record_ranges;
    std::vector<const VkAccelerationStructureBuildRangeInfoKHR*> record_range_pointers;
    std::vector<VkAccelerationStructureKHR> record_queries;
    u32 index_threads = 0, vertex_threads = 0;
    u32 dynamic_count = 0, last_dynamic_count = 0; ///< dynamic structures drawn this, last frame
    static constexpr u32 RefitBudget = 256;
    /// verified: a dynamic structure's slot, its word holds the view distance.
    static constexpr u32 DistanceTag = 0x8000'0000u;
    u64 new_triangles = 0;
    u32 skipped = 0, over_budget = 0;

    u64 frame = 0;
    u32 slot = 0;
    u64 reported_dropped = 0; ///< object motion's dropped draws at the last report
    bool warned_dropped = false;
    u64 recorded_frame = 0, previous_recorded = 0; ///< frames whose Record built the scene
    std::array<Frame, FrameSlots> frames{};

    Buffer gather_positions{}, gather_indices{}, signatures{}, sig_vertices{}, tlas_instances{};
    /// Per entry: rt_check.comp's counts of its coverage (rt_common.glsl CoverageStats).
    Buffer coverage_stats{};
    bool coverage_cleared = false;
    Buffer tlas_buffer{}, scratch{};
    vk::AccelerationStructureKHR tlas{};

    vk::UniqueDescriptorSetLayout check_layout{};
    vk::UniquePipelineLayout push_only_layout{}, check_pipeline_layout{};
    vk::UniquePipeline gather_indices_pipeline{}, gather_vertices_pipeline{},
        instances_pipeline{}, check_pipeline{};

    // Report every ReportFrames frames (BB_RT_REPORT_FRAMES for tests): sums since the last one.
    const u64 ReportFrames = [] {
        const char* value = std::getenv("BB_RT_REPORT_FRAMES");
        const u64 n = value ? std::strtoull(value, nullptr, 10) : 0;
        return n >= 30 ? n : 300;
    }();
    struct Sums {
        u64 frames = 0, instances = 0, alpha = 0, characters = 0, kept = 0, triangles = 0, builds = 0,
            built_triangles = 0,
            refits = 0, refits_unchanged = 0, rebuilds = 0, mismatches = 0, mismatches_placed = 0, to_dynamic = 0,
            started_moving = 0, placed = 0, rematched = 0,
            evicted = 0, compacted = 0,
            skipped = 0, over_budget = 0, errors = 0;
        std::array<u64, 5> check{};
        u64 compacted_before = 0, compacted_after = 0;
        /// CPU time on the render thread, microseconds: AddDraw, Record, OnFrameStart, and the
        /// effects (NoteEffectsCpu).
        double cpu_draws = 0.0, cpu_record = 0.0, cpu_frame = 0.0, cpu_effects = 0.0;
        double cpu_wait = 0.0; ///< of cpu_frame: waiting for the GPU to free a frame slot
        /// Object motion for the draws ray tracing adds, per part (NoteMotionCpu). It and
        /// cpu_draws are taken in timed frames only (TimedFrame).
        MotionTimes cpu_motion{};
        u64 timed_frames = 0;
    } sums;
    static constexpr u64 TimedStride = 8;
    bool timed_frame = false;
};

} // namespace Vulkan
