// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <algorithm>
#include <cstdint>

namespace Vulkan::Motion {

// Strict decimal Mi-vertices (1..64); zero/absent/invalid means use the default.
inline uint32_t ParseCaptureBudget(const char* value) {
    if (!value || !*value) {
        return 0;
    }
    uint32_t millions = 0;
    for (; *value; ++value) {
        if (*value < '0' || *value > '9') {
            return 0;
        }
        millions = millions * 10 + uint32_t(*value - '0');
        if (millions > 64) {
            return 0;
        }
    }
    return millions << 20;
}

struct CaptureBudget {
    uint32_t base{}, rt{};

    // RT override wins over the legacy override for RT only. Never shrink below
    // base history capacity. The legacy base setting retains its existing parser.
    static CaptureBudget Choose(uint32_t legacy, const char* rt_override, bool supported) {
        const uint32_t base = legacy ? legacy : 4u << 20;
        const uint32_t requested = ParseCaptureBudget(rt_override);
        return {base, supported ? std::max(base, requested ? requested : legacy ? legacy : 12u << 20)
                                : base};
    }

    uint32_t Capacity(bool active) const { return active ? rt : base; }
    static uint32_t Reserve(uint32_t capacity, bool active) {
        return active ? capacity / 100 * 15 : 0;
    }
    static uint64_t Bytes(uint32_t capacity) { return (1 + 2 * uint64_t(capacity)) * 16; }
};

} // namespace Vulkan::Motion
