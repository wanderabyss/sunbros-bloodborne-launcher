// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <unordered_map>
#include <vector>

namespace BbMap {
struct MapBounds { float x0, z0, x1, z1; };

// Built on the map worker, queried only by the UI owner. Results retain source
// order, including overlapping translucent floors. Oversized boxes/queries use
// a bounded fallback rather than exploding the grid or dropping geometry.
class MapSpatialIndex {
public:
    void Build(std::vector<MapBounds> bounds) {
        boxes = std::move(bounds);
        cells.clear(); large.clear(); candidates.clear();
        seen.assign(boxes.size(), 0); generation = 0;
        for (uint32_t i = 0; i < boxes.size(); ++i) {
            int x0, z0, x1, z1;
            if (!Range(boxes[i], x0, z0, x1, z1)) { large.push_back(i); continue; }
            for (int x = x0; x <= x1; ++x) for (int z = z0; z <= z1; ++z)
                cells[Key(x, z)].push_back(i);
        }
    }
    template<class F> void Visit(MapBounds view, F&& visit) {
        int x0, z0, x1, z1;
        if (!Range(view, x0, z0, x1, z1)) {
            for (uint32_t i = 0; i < boxes.size(); ++i) if (Overlap(boxes[i], view)) visit(i);
            return;
        }
        if (++generation == 0) { std::fill(seen.begin(), seen.end(), 0); ++generation; }
        candidates.clear();
        const auto add = [&](uint32_t i) {
            if (seen[i] != generation) {
                seen[i] = generation;
                if (Overlap(boxes[i], view)) candidates.push_back(i);
            }
        };
        for (auto i : large) add(i);
        for (int x = x0; x <= x1; ++x) for (int z = z0; z <= z1; ++z) {
            const auto it = cells.find(Key(x, z));
            if (it != cells.end()) for (auto i : it->second) add(i);
        }
        std::sort(candidates.begin(), candidates.end());
        for (auto i : candidates) visit(i);
    }
private:
    static bool Overlap(MapBounds a, MapBounds b) {
        return a.x0 <= b.x1 && a.x1 >= b.x0 && a.z0 <= b.z1 && a.z1 >= b.z0;
    }
    static uint64_t Key(int x, int z) { return uint64_t(uint32_t(x)) << 32 | uint32_t(z); }
    static bool Range(MapBounds b, int& x0, int& z0, int& x1, int& z1) {
        for (float v : {b.x0, b.z0, b.x1, b.z1})
            if (!std::isfinite(v) || std::abs(v) > 1.0e7f) return false;
        x0 = int(std::floor(b.x0 / 32)); z0 = int(std::floor(b.z0 / 32));
        x1 = int(std::floor(b.x1 / 32)); z1 = int(std::floor(b.z1 / 32));
        return x1 >= x0 && z1 >= z0 && uint64_t(x1 - x0 + 1) * (z1 - z0 + 1) <= 4096;
    }
    std::vector<MapBounds> boxes;
    std::unordered_map<uint64_t, std::vector<uint32_t>> cells;
    std::vector<uint32_t> large, seen, candidates;
    uint32_t generation{};
};
} // namespace BbMap
