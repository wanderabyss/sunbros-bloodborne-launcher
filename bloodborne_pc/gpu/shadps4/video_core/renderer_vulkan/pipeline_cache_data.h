// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <array>
#include <cstdint>
#include <cstring>
#include <span>

namespace Vulkan {
// Vulkan pipeline-cache header version one (32 bytes). Driver UUID, device and
// vendor must match before opaque bytes are passed to the driver.
inline bool CompatiblePipelineData(std::span<const uint8_t> bytes, uint32_t vendor,
                                   uint32_t device, const std::array<uint8_t, 16>& uuid) {
    if (bytes.size() < 32 || bytes.size() > (256u << 20)) return false;
    uint32_t header[4];
    std::memcpy(header, bytes.data(), sizeof(header));
    return header[0] == 32 && header[1] == 1 && header[2] == vendor && header[3] == device &&
           std::memcmp(bytes.data() + 16, uuid.data(), uuid.size()) == 0;
}
} // namespace Vulkan
