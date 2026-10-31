// SPDX-FileCopyrightText: Copyright 2025-2026 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "common/elf_info.h"
#include "common/io_file.h"
#include "common/polyfill_thread.h"
#include "common/thread.h"
#include "core/emulator_settings.h"

#include "video_core/cache_storage.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_pipeline_cache.h"

#include <miniz.h>

#include <condition_variable>
#include <functional>
#include <future>
#include <mutex>
#include <queue>

namespace {

mz_zip_archive zip_ar{};
bool ar_is_read_only{true};

} // namespace

namespace Storage {

constexpr std::string GetBlobFileExtension(BlobType type) {
    switch (type) {
    case BlobType::ShaderMeta: {
        return "meta";
    }
    case BlobType::ShaderBinary: {
        return "spv";
    }
    case BlobType::PipelineKey: {
        return "key";
    }
    case BlobType::DriverPipelineCache: {
        return "vkcache";
    }
    case BlobType::ShaderProfile: {
        return "bin";
    }
    default:
        UNREACHABLE();
    }
}

namespace {

bool IEquals(std::string_view a, std::string_view b) {
    return std::ranges::equal(a, b, [](char ca, char cb) {
        return std::tolower(static_cast<unsigned char>(ca)) ==
               std::tolower(static_cast<unsigned char>(cb));
    });
}

} // namespace

static std::string ResolveEffectiveVendor(u32 vendor_id) {
    if (const char* env_vendor = std::getenv("BB_GPU_VENDOR"); env_vendor && *env_vendor) {
        if (IEquals(env_vendor, "nvidia") || IEquals(env_vendor, "0x10de")) return "nvidia";
        if (IEquals(env_vendor, "amd") || IEquals(env_vendor, "0x1002")) return "amd";
        if (IEquals(env_vendor, "intel") || IEquals(env_vendor, "0x8086")) return "intel";
        std::string ev = env_vendor;
        std::transform(ev.begin(), ev.end(), ev.begin(), ::tolower);
        return ev;
    }
    switch (vendor_id) {
    case 0x10de: return "nvidia";
    case 0x1002: return "amd";
    case 0x8086: return "intel";
    default:
        if (vendor_id != 0) {
            char buf[16];
            std::snprintf(buf, sizeof(buf), "0x%04x", vendor_id);
            return buf;
        }
        return "";
    }
}

void DataBase::Open(u32 vendor_id) {
    if (opened) {
        return;
    }

    const auto& game_info = Common::ElfInfo::Instance();

    using namespace Common::FS;
    if (EmulatorSettings.IsPipelineCacheArchived()) {
        mz_zip_zero_struct(&zip_ar);

        cache_path = GetUserPath(PathType::CacheDir) /
                     std::filesystem::path{game_info.GameSerial()}.replace_extension(".zip");

        if (!mz_zip_reader_init_file(&zip_ar, cache_path.string().c_str(),
                                     MZ_ZIP_FLAG_READ_ALLOW_WRITING) ||
            !mz_zip_validate_archive(&zip_ar, 0)) {
            LOG_INFO(Render, "Cache archive {} is not found or archive is corrupted",
                     cache_path.string().c_str());
            mz_zip_reader_end(&zip_ar);
            mz_zip_writer_init_file(&zip_ar, cache_path.string().c_str(), 0);
        }
    } else {
        const auto vendor_sub = ResolveEffectiveVendor(vendor_id);
        const auto base_dir = GetUserPath(PathType::CacheDir) / game_info.GameSerial();
        if (!vendor_sub.empty()) {
            cache_path = base_dir / vendor_sub;
        } else {
            cache_path = base_dir;
        }

        std::error_code ec;
        // Migration: if base_dir contains legacy unpartitioned .meta, .key, .spv or profile,
        // move them into the vendor partition so existing warm caches are preserved without
        // cross-vendor pollution.
        if (!vendor_sub.empty() && std::filesystem::exists(base_dir, ec)) {
            std::filesystem::create_directories(cache_path, ec);
            const auto meta = "." + GetBlobFileExtension(BlobType::ShaderMeta);
            const auto key = "." + GetBlobFileExtension(BlobType::PipelineKey);
            const auto spv = "." + GetBlobFileExtension(BlobType::ShaderBinary);
            for (const auto& entry : std::filesystem::directory_iterator(base_dir, ec)) {
                if (!entry.is_regular_file(ec)) continue;
                const auto ext = entry.path().extension();
                const auto fname = entry.path().filename().string();
                if (ext == meta || ext == key || ext == spv || fname == "profile" || fname == "driver") {
                    const auto target = cache_path / entry.path().filename();
                    if (!std::filesystem::exists(target, ec)) {
                        std::filesystem::copy_file(entry.path(), target, ec);
                    }
                    std::filesystem::remove(entry.path(), ec);
                }
            }
        } else if (!std::filesystem::exists(cache_path, ec)) {
            std::filesystem::create_directories(cache_path, ec);
        }
    }

    io_worker = std::make_unique<Common::DrainingQueue>([] {
        Common::SetCurrentThreadName("shadPS4:PipelineCacheIO");
    });
    opened = true;
}

void DataBase::Close() {
    if (!IsOpened()) {
        return;
    }

    io_worker->Stop();
    io_worker.reset();

    if (EmulatorSettings.IsPipelineCacheArchived()) {
        mz_zip_writer_finalize_archive(&zip_ar);
        mz_zip_writer_end(&zip_ar);
    }

    opened = false;
    LOG_INFO(Render, "Cache dumped");
}

template <typename T>
bool WriteVector(const BlobType type, std::filesystem::path&& path_, std::vector<T>&& v, Common::DrainingQueue& queue) {
    auto request = std::packaged_task<void()>{[type, path_ = std::move(path_), v = std::move(v)]() {
        auto path{path_};
        path.replace_extension(GetBlobFileExtension(type));
        if (EmulatorSettings.IsPipelineCacheArchived()) {
            ASSERT_MSG(!ar_is_read_only,
                       "The archive is read-only. Did you forget to call `FinishPreload`?");
            if (!mz_zip_writer_add_mem(&zip_ar, path.string().c_str(), v.data(),
                                       v.size() * sizeof(T), MZ_BEST_COMPRESSION)) {
                LOG_ERROR(Render, "Failed to add {} to the archive", path.string().c_str());
            }
        } else {
            // bbport: write beside and rename into place, so a game that ends during the
            // write never leaves a truncated blob for the next start.
            using namespace Common::FS;
            auto temp{path};
            temp += ".tmp";
            {
                const auto file = IOFile{temp, FileAccessMode::Create};
                if (!file.IsOpen() || file.Write(v) != v.size()) {
                    return;
                }
            }
            std::error_code error;
            std::filesystem::rename(temp, path, error);
        }
    }};
    return queue.Push(std::move(request));
}

template <typename T>
void LoadVector(BlobType type, std::filesystem::path& path, std::vector<T>& v) {
    using namespace Common::FS;
    path.replace_extension(GetBlobFileExtension(type));
    if (EmulatorSettings.IsPipelineCacheArchived()) {
        int index{-1};
        index = mz_zip_reader_locate_file(&zip_ar, path.string().c_str(), nullptr, 0);
        if (index < 0) {
            LOG_WARNING(Render, "File {} is not found in the archive", path.string().c_str());
            return;
        }
        mz_zip_archive_file_stat stat{};
        mz_zip_reader_file_stat(&zip_ar, index, &stat);
        if (type == BlobType::DriverPipelineCache && stat.m_uncomp_size > (256u << 20)) return;
        v.resize(stat.m_uncomp_size / sizeof(T));
        mz_zip_reader_extract_to_mem(&zip_ar, index, v.data(), stat.m_uncomp_size, 0);
    } else {
        const auto file = IOFile{path, FileAccessMode::Read};
        if (type == BlobType::DriverPipelineCache && file.GetSize() > (256u << 20)) return;
        v.resize(file.GetSize() / sizeof(T));
        file.Read(v);
    }
}

bool DataBase::Save(BlobType type, const std::string& name, std::vector<u8>&& data) {
    if (!opened) {
        return false;
    }

    auto path = EmulatorSettings.IsPipelineCacheArchived() ? std::filesystem::path{name}
                                                           : cache_path / name;
    return WriteVector(type, std::move(path), std::move(data), *io_worker);
}

bool DataBase::Save(BlobType type, const std::string& name, std::vector<u32>&& data) {
    if (!opened) {
        return false;
    }

    auto path = EmulatorSettings.IsPipelineCacheArchived() ? std::filesystem::path{name}
                                                           : cache_path / name;
    return WriteVector(type, std::move(path), std::move(data), *io_worker);
}

void DataBase::Load(BlobType type, const std::string& name, std::vector<u8>& data) {
    if (!opened) {
        return;
    }

    auto path = EmulatorSettings.IsPipelineCacheArchived() ? std::filesystem::path{name}
                                                           : cache_path / name;
    return LoadVector(type, path, data);
}

void DataBase::Load(BlobType type, const std::string& name, std::vector<u32>& data) {
    if (!opened) {
        return;
    }

    auto path = EmulatorSettings.IsPipelineCacheArchived() ? std::filesystem::path{name}
                                                           : cache_path / name;
    return LoadVector(type, path, data);
}

void DataBase::ForEachBlob(BlobType type, const std::function<void(std::vector<u8>&& data)>& func) {
    (void)PruneBlobs(type, [&](std::vector<u8>&& data) { func(std::move(data)); return true; });
}

u32 DataBase::PruneBlobs(BlobType type, const std::function<bool(std::vector<u8>&& data)>& keep) {
    std::vector<std::filesystem::path> rejected;
    const auto& ext = GetBlobFileExtension(type);
    if (EmulatorSettings.IsPipelineCacheArchived()) {
        const auto num_files = mz_zip_reader_get_num_files(&zip_ar);
        for (int index = 0; index < num_files; ++index) {
            std::array<char, MZ_ZIP_MAX_ARCHIVE_FILENAME_SIZE> file_name{};
            file_name.fill(0);
            mz_zip_reader_get_filename(&zip_ar, index, file_name.data(), file_name.size());
            if (std::string{file_name.data()}.ends_with(ext)) {
                mz_zip_archive_file_stat stat{};
                mz_zip_reader_file_stat(&zip_ar, index, &stat);
                std::vector<u8> data(stat.m_uncomp_size);
                mz_zip_reader_extract_to_mem(&zip_ar, index, data.data(), data.size(), 0);
                (void)keep(std::move(data));
            }
        }
    } else {
        for (const auto& file_name : std::filesystem::directory_iterator{cache_path}) {
            if (file_name.path().extension().string().ends_with(ext)) {
                using namespace Common::FS;
                const auto& file = IOFile{file_name, FileAccessMode::Read};
                if (file.IsOpen()) {
                    std::vector<u8> data(file.GetSize());
                    file.Read(data);
                    if (!keep(std::move(data))) rejected.push_back(file_name.path());
                }
            }
        }
    }
    u32 removed = 0;
    for (const auto& path : rejected) {
        std::error_code ec;
        removed += std::filesystem::remove(path, ec) ? 1 : 0;
    }
    return removed;
}

void DataBase::Clear() {
    if (!opened || EmulatorSettings.IsPipelineCacheArchived()) {
        return;
    }
    std::error_code ec;
    u64 removed = 0;
    for (const auto& entry : std::filesystem::directory_iterator(cache_path, ec)) {
        if (entry.is_regular_file(ec) && std::filesystem::remove(entry.path(), ec)) {
            ++removed;
        }
    }
    LOG_WARNING(Render, "Pipeline cache cleared ({} files): it is rebuilt for this build", removed);
}

void DataBase::ClearType(BlobType type) {
    if (!opened || EmulatorSettings.IsPipelineCacheArchived()) {
        return;
    }
    const auto ext = "." + GetBlobFileExtension(type);
    std::error_code ec;
    u64 removed = 0;
    for (const auto& entry : std::filesystem::directory_iterator(cache_path, ec)) {
        if (entry.is_regular_file(ec) && entry.path().extension() == ext &&
            std::filesystem::remove(entry.path(), ec)) {
            ++removed;
        }
    }
    LOG_WARNING(Render, "Pipeline cache: {} {} files removed", removed, ext);
}

bool DataBase::Has(BlobType type, const std::string& name) const {
    if (!opened || EmulatorSettings.IsPipelineCacheArchived()) {
        return opened;
    }
    auto path = cache_path / name;
    path.replace_extension(GetBlobFileExtension(type));
    std::error_code ec;
    return std::filesystem::exists(path, ec);
}

u32 DataBase::Count(BlobType type) const {
    if (!opened || EmulatorSettings.IsPipelineCacheArchived()) {
        return 0;
    }
    const auto ext = "." + GetBlobFileExtension(type);
    std::error_code ec;
    u32 count = 0;
    for (const auto& entry : std::filesystem::directory_iterator(cache_path, ec)) {
        count += entry.path().extension() == ext;
    }
    return count;
}


u32 DataBase::Seed(const std::filesystem::path& catalog, u32 vendor_id) {
    if (!opened || EmulatorSettings.IsPipelineCacheArchived()) {
        return 0;
    }
    const auto meta = "." + GetBlobFileExtension(BlobType::ShaderMeta);
    const auto key = "." + GetBlobFileExtension(BlobType::PipelineKey);
    std::error_code ec;
    if (!std::filesystem::exists(catalog, ec)) {
        return 0;
    }

    const auto effective_vendor = ResolveEffectiveVendor(vendor_id);
    u32 added = 0;

    auto copy_records_from = [&](const std::filesystem::path& dir) {
        if (!std::filesystem::is_directory(dir, ec)) return;
        for (const auto& entry : std::filesystem::directory_iterator(dir, ec)) {
            const auto ext = entry.path().extension();
            if (!entry.is_regular_file(ec) || (ext != meta && ext != key)) {
                continue;
            }
            const auto target = cache_path / entry.path().filename();
            if (!std::filesystem::exists(target, ec) &&
                std::filesystem::copy_file(entry.path(), target, ec)) {
                ++added;
            }
        }
    };

    // Check if catalog contains vendor partition subdirectories
    bool partitioned = false;
    for (const auto& entry : std::filesystem::directory_iterator(catalog, ec)) {
        if (entry.is_directory(ec)) {
            const auto name = entry.path().filename().string();
            if (IEquals(name, "nvidia") || IEquals(name, "0x10de") ||
                IEquals(name, "amd") || IEquals(name, "0x1002") ||
                IEquals(name, "intel") || IEquals(name, "0x8086")) {
                partitioned = true;
                break;
            }
        }
    }

    if (partitioned) {
        // Copy exclusively from the single effective vendor directory
        if (!effective_vendor.empty()) {
            copy_records_from(catalog / effective_vendor);
            if (effective_vendor == "nvidia") copy_records_from(catalog / "0x10de");
            else if (effective_vendor == "amd") copy_records_from(catalog / "0x1002");
            else if (effective_vendor == "intel") copy_records_from(catalog / "0x8086");
        }
        // Copy common directory if present
        copy_records_from(catalog / "common");
        // Copy any loose files directly in the catalog root
        for (const auto& entry : std::filesystem::directory_iterator(catalog, ec)) {
            if (entry.is_regular_file(ec)) {
                const auto ext = entry.path().extension();
                if (ext == meta || ext == key) {
                    const auto target = cache_path / entry.path().filename();
                    if (!std::filesystem::exists(target, ec) &&
                        std::filesystem::copy_file(entry.path(), target, ec)) {
                        ++added;
                    }
                }
            }
        }
    } else {
        copy_records_from(catalog);
    }
    return added;
}

void DataBase::FinishPreload() {
    if (EmulatorSettings.IsPipelineCacheArchived()) {
        mz_zip_writer_init_from_reader(&zip_ar, cache_path.string().c_str());
        ar_is_read_only = false;
    }
}

} // namespace Storage
