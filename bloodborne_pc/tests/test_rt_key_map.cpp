// SPDX-License-Identifier: GPL-2.0-or-later
// Ray tracing's key -> slot map (rt_key_map.h) against std::unordered_map: random sets and
// erases with many collisions, key 0, replacing, erasing only the matching slot, and growth.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <random>
#include <unordered_map>
#include "gpu/shadps4/video_core/renderer_vulkan/rt_key_map.h"

using Vulkan::RtKeyMap;

int main() {
    RtKeyMap map;
    assert(map.Find(0) == RtKeyMap::Empty); // before Reserve
    map.EraseIf(0, 0);
    map.Reserve(64);
    map.Set(0, 7);
    assert(map.Find(0) == 7 && map.Size() == 1);
    map.Set(0, 9); // replaced
    assert(map.Find(0) == 9 && map.Size() == 1);
    map.EraseIf(0, 7); // another slot: kept
    assert(map.Find(0) == 9);
    map.EraseIf(0, 9);
    assert(map.Find(0) == RtKeyMap::Empty && map.Size() == 0);

    // Few distinct keys in a small table: long runs that wrap around the end.
    std::mt19937_64 random{12345};
    for (const uint64_t range : {40ull, 5000ull, ~0ull}) {
        RtKeyMap m;
        m.Reserve(range < 100 ? 8 : 1024); // grows past this
        std::unordered_map<uint64_t, uint32_t> reference;
        for (int step = 0; step < 200000; ++step) {
            const uint64_t key = random() % range;
            const uint32_t slot = uint32_t(random() % 4);
            switch (random() % 3) {
            case 0:
                m.Set(key, slot);
                reference[key] = slot;
                break;
            case 1:
                m.EraseIf(key, slot);
                if (const auto it = reference.find(key); it != reference.end() && it->second == slot) {
                    reference.erase(it);
                }
                break;
            default: {
                const auto it = reference.find(key);
                assert(m.Find(key) == (it == reference.end() ? RtKeyMap::Empty : it->second));
            }
            }
            assert(m.Size() == reference.size());
        }
        for (const auto& [key, slot] : reference) {
            assert(m.Find(key) == slot);
        }
    }
    map.Clear();
    assert(map.Find(1) == RtKeyMap::Empty && map.Size() == 0);
    map.Set(1, 2); // usable again after Clear
    assert(map.Find(1) == 2);
    std::puts("Ray tracing key map: set, find, erase and growth match std::unordered_map PASS");
}
