// SPDX-FileCopyrightText: Copyright 2025 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include "common/path_util.h"
#include "common/singleton.h"
#include "common/types.h"
#include "common/draining_queue.h"
#include <memory>

#include <functional>
#include <thread>
#include <vector>

namespace Storage {

enum class BlobType : u32 {
    ShaderMeta,
    ShaderBinary,
    PipelineKey,
    ShaderProfile,
    DriverPipelineCache,
};

class DataBase {
public:
    static DataBase& Instance() {
        return *Common::Singleton<DataBase>::Instance();
    }

    void Open(u32 vendor_id = 0);
    void Close();
    [[nodiscard]] bool IsOpened() const {
        return opened;
    }
    void FinishPreload();
    /// bbport: removes every cached blob (an incompatible cache is rebuilt, not ignored).
    void Clear();
    /// bbport shader pre-build: removes the blobs of one type only (the SPIR-V, which the game
    /// files can make again, keeping what the draws saw).
    void ClearType(BlobType type);
    /// bbport shader pre-build: adds a catalog's shader and pipeline records (.meta, .key) the
    /// cache does not have yet; returns how many were added.
    u32 Seed(const std::filesystem::path& catalog, u32 vendor_id = 0);
    /// Whether a blob is stored (directory caches; archives answer true and are read as before).
    bool Has(BlobType type, const std::string& name) const;
    /// How many blobs of a type are stored (directory caches; 0 for archives).
    u32 Count(BlobType type) const;

    bool Save(BlobType type, const std::string& name, std::vector<u8>&& data);
    bool Save(BlobType type, const std::string& name, std::vector<u32>&& data);

    void Load(BlobType type, const std::string& name, std::vector<u8>& data);
    void Load(BlobType type, const std::string& name, std::vector<u32>& data);

    void ForEachBlob(BlobType type, const std::function<void(std::vector<u8>&& data)>& func);
    // Startup only. Remove rejected directory records after visiting; archives stay read-only.
    u32 PruneBlobs(BlobType type, const std::function<bool(std::vector<u8>&& data)>& keep);

private:
    std::unique_ptr<Common::DrainingQueue> io_worker;
    std::filesystem::path cache_path{};
    bool opened{};
};

} // namespace Storage
