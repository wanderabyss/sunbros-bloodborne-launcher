// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: ray tracing's structure key -> slot map (vk_ray_tracing.h). Open addressing with
// linear probing and backward-shift erase: a lookup per draw reads one or two cache lines,
// where std::unordered_map followed a node per key. The keys are hashes already (any 64-bit
// value); an empty cell holds the slot Empty. Cases: tests/test_rt_key_map.cpp.
#pragma once

#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

namespace Vulkan {

class RtKeyMap {
public:
    static constexpr uint32_t Empty = ~0u;

    /// Empty, with room for `count` keys at most half full.
    void Reserve(size_t count) {
        size_t n = 16;
        while (n < count * 2) {
            n *= 2;
        }
        cells.assign(n, Cell{});
        mask = n - 1;
        size = 0;
    }
    /// Empty, its memory released.
    void Clear() {
        cells = {};
        mask = 0;
        size = 0;
    }
    /// The slot of `key`, or Empty.
    [[nodiscard]] uint32_t Find(uint64_t key) const {
        if (cells.empty()) {
            return Empty;
        }
        for (size_t i = Start(key);; i = (i + 1) & mask) {
            const Cell& c = cells[i];
            if (c.slot == Empty) {
                return Empty;
            }
            if (c.key == key) {
                return c.slot;
            }
        }
    }
    /// `key` maps to `slot` (not Empty), inserted or replaced.
    void Set(uint64_t key, uint32_t slot) {
        if ((size + 1) * 2 > cells.size()) {
            Grow();
        }
        for (size_t i = Start(key);; i = (i + 1) & mask) {
            Cell& c = cells[i];
            if (c.slot == Empty) {
                c = {key, slot};
                ++size;
                return;
            }
            if (c.key == key) {
                c.slot = slot;
                return;
            }
        }
    }
    /// Removes `key` when it maps to `slot`.
    void EraseIf(uint64_t key, uint32_t slot) {
        if (cells.empty()) {
            return;
        }
        size_t hole = Start(key);
        for (;; hole = (hole + 1) & mask) {
            const Cell& c = cells[hole];
            if (c.slot == Empty) {
                return;
            }
            if (c.key == key) {
                break;
            }
        }
        if (cells[hole].slot != slot) {
            return;
        }
        // Later cells of the run move into the hole unless their home lies after it (then a
        // lookup from the home would not pass the hole).
        for (size_t j = (hole + 1) & mask;; j = (j + 1) & mask) {
            const Cell& c = cells[j];
            if (c.slot == Empty) {
                break;
            }
            if (((j - Start(c.key)) & mask) >= ((j - hole) & mask)) {
                cells[hole] = c;
                hole = j;
            }
        }
        cells[hole] = Cell{};
        --size;
    }
    [[nodiscard]] size_t Size() const {
        return size;
    }

private:
    struct Cell {
        uint64_t key = 0;
        uint32_t slot = Empty;
    };
    [[nodiscard]] size_t Start(uint64_t key) const {
        const uint64_t h = key * 0x9e3779b97f4a7c15ULL;
        return size_t(h ^ (h >> 32)) & mask;
    }
    void Grow() {
        std::vector<Cell> old = std::move(cells);
        const size_t n = old.empty() ? 16 : old.size() * 2;
        cells.assign(n, Cell{});
        mask = n - 1;
        size = 0;
        for (const Cell& c : old) {
            if (c.slot != Empty) {
                Set(c.key, c.slot);
            }
        }
    }

    std::vector<Cell> cells;
    size_t mask = 0, size = 0;
};

} // namespace Vulkan
