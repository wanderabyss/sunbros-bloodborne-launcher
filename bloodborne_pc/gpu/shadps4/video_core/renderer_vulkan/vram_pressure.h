// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <cstdint>

namespace Vulkan {
inline bool RtPressureActive(bool was_active, uint64_t usage, uint64_t budget) {
    return budget && usage >= budget / 100 * (was_active ? 85 : 90);
}

// Keep recent/live RT geometry protected by the existing eviction recency gate.
// Only cold entries are eligible; this target never authorizes an unsafe free.
inline uint64_t RtPressureTarget(uint64_t usage, uint64_t budget, uint64_t rt_used,
                                 uint64_t normal_target, bool pressured) {
    if (!budget || !pressured) return normal_target;
    const uint64_t desired_usage = budget / 100 * 85;
    const uint64_t reclaim = usage > desired_usage ? usage - desired_usage : 0;
    return std::min(normal_target, rt_used - std::min(rt_used, reclaim));
}
} // namespace Vulkan
