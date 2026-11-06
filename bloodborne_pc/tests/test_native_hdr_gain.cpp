// bbport: native HDR: the SPIR-V edit of the game's tone mapper (native_hdr_gain.h).
#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>

#include "shadps4/video_core/renderer_vulkan/native_hdr_gain.h"

using Vulkan::NativeHdrGain::AddGainOutput;
using Vulkan::NativeHdrGain::IsToneMapper;
using Words = std::vector<std::uint32_t>;

namespace {

enum : std::uint32_t {
    Float = 1, Vec4, Ptr, Out, Ext, Eps, Cb, C0, C1, C2, Fn, AccessR, AccessG, AccessB, AccessA,
    FMax0, FMax1, FMax2, Neg, K, Mul, Stored, Next = 40,
};

std::uint32_t Bits(float x) {
    std::uint32_t b;
    std::memcpy(&b, &x, sizeof(b));
    return b;
}

void Add(Words& w, std::uint32_t op, std::initializer_list<std::uint32_t> args) {
    w.push_back((std::uint32_t(args.size() + 1) << 16) | op);
    w.insert(w.end(), args);
}

/// The shape of the game's tone mapper: three max(2^-14, c), -max * K, four output stores.
Words ToneMapperLike(bool with_curve = true) {
    Words w{0x07230203u, 0x00010300u, 0, Next, 0};
    Add(w, 11, {Ext, 0x4c534c47u});                  // OpExtInstImport
    Add(w, 15, {4, Fn, 0x6e69616du, 0, Out});        // OpEntryPoint Fragment "main" with Out
    Add(w, 71, {Out, 30, 0});                        // OpDecorate Location 0
    Add(w, 22, {Float, 32});                         // OpTypeFloat
    Add(w, 23, {Vec4, Float, 4});                    // OpTypeVector
    Add(w, 32, {Ptr, 3, Vec4});                      // OpTypePointer Output
    Add(w, 59, {Ptr, Out, 3});                       // OpVariable Output
    Add(w, 43, {Float, Eps, Bits(with_curve ? 1.0f / 16384.0f : 0.5f)});
    Add(w, 43, {Float, C0, Bits(0.5f)});
    Add(w, 54, {Float, Fn, 0, 0});                   // OpFunction
    Add(w, 248, {Next - 1});                         // OpLabel
    for (std::uint32_t id : {FMax0, FMax1, FMax2}) { // max(2^-14, c)
        Add(w, 12, {Float, id, Ext, 40, Eps, C0});
    }
    Add(w, 127, {Float, Neg, FMax0});                // OpFNegate
    Add(w, 124, {Float, K, Cb});                     // OpBitcast
    Add(w, 133, {Float, Mul, Neg, K});               // OpFMul
    for (std::uint32_t id : {AccessR, AccessG, AccessB, AccessA}) {
        Add(w, 65, {Ptr, id, Out, C0});              // OpAccessChain
    }
    for (std::uint32_t id : {AccessR, AccessG, AccessB, AccessA}) {
        Add(w, 62, {id, Mul});                       // OpStore
    }
    Add(w, 253, {});                                 // OpReturn
    Add(w, 56, {});                                  // OpFunctionEnd
    return w;
}

struct Parsed {
    std::uint32_t stores = 0, variables = 0, location1 = 0, entry_interface = 0;
};

Parsed Parse(const Words& w) {
    Parsed p;
    std::size_t i = 5;
    while (i < w.size()) {
        const std::uint32_t count = w[i] >> 16, op = w[i] & 0xffff;
        assert(count > 0 && i + count <= w.size());
        // Every result and reference stays below the header's bound.
        if (op == 62) ++p.stores;
        if (op == 59) ++p.variables;
        if (op == 71 && w[i + 2] == 30 && w[i + 3] == 1) p.location1 = w[i + 1];
        if (op == 15) p.entry_interface = w[i + count - 1];
        i += count;
    }
    assert(i == w.size());
    return p;
}

} // namespace

int main() {
    const auto spv = ToneMapperLike();
    const auto out = AddGainOutput(spv);
    assert(!out.empty());
    const Parsed before = Parse(spv), after = Parse(out);
    assert(after.stores == before.stores + 1);
    assert(after.variables == before.variables + 1);
    assert(after.location1 != 0);
    assert(after.entry_interface == after.location1); // declared in the entry point's interface
    assert(out[3] > spv[3]);                          // the bound grew
    assert(after.location1 < out[3]);

    // The output comes before the function, the gain's code before the shader's own stores.
    const auto find = [&](std::uint32_t op, std::uint32_t word1_or_0) {
        for (std::size_t i = 5; i < out.size(); i += out[i] >> 16) {
            if ((out[i] & 0xffff) == op && (!word1_or_0 || out[i + 1] == word1_or_0)) return i;
        }
        return out.size();
    };
    assert(find(59, Ptr) < find(54, 0));
    assert(find(62, after.location1) < find(62, AccessR));

    // Not the expected code: untouched, no gain.
    assert(AddGainOutput(ToneMapperLike(false)).empty());
    assert(AddGainOutput(Words{1, 2, 3}).empty());

    // Only the curve's tone mappers.
    assert(IsToneMapper(0xccb08339) && IsToneMapper(0x5e67d866));
    assert(!IsToneMapper(0xcbe2dd84) && !IsToneMapper(0xed4c7668));
    return 0;
}
