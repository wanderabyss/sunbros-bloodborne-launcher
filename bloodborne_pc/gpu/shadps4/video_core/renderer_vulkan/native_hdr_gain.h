// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: native HDR (hdr_native): adds a gain output to the game's tone mapper. See vk_native_hdr.h.
// Header only and free of Vulkan, so that test_native_hdr_gain.cpp can run it on its own.
#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <optional>
#include <span>
#include <unordered_map>
#include <utility>
#include <vector>

namespace Vulkan::NativeHdrGain {

/// The color attachment the gain goes to: the tone mapper only writes attachment 0.
inline constexpr std::uint32_t Attachment = 1;
/// The largest gain the frame's alpha carries: 8 stops, in 255 steps of about 1/32 stop.
inline constexpr float MaxGain = 256.0f;

/// The game's tone mappers with the exponential curve (vertex shader 1ea5a07e). 5e67d866 runs with
/// depth of field and the game's AA off, ccb08339 with them on. cbe2dd84 and 1caf4b82 have another
/// curve and fda39ee2 and 6b1bc5f0 none: AddGainOutput finds no curve there, and they get no gain.
inline bool IsToneMapper(std::uint64_t hash) {
    constexpr std::array<std::uint64_t, 5> hashes{0xccb08339, 0x5e67d866, 0x5c02eaf8, 0x925d5712,
                                                  0x15fa3515};
    return std::find(hashes.begin(), hashes.end(), hash) != hashes.end();
}

/// A copy of a tone mapper's SPIR-V that also writes gain = E / (1 - exp(-E)) to Attachment, with
/// E = K * largest channel: scene light over what the curve 1 - exp(-E) leaves of it. That is 1 in
/// the shadows, where the curve is linear, and grows only where it compresses, so the SDR picture
/// times the gain keeps the game's grading and bloom. Empty when the code is not the expected one.
inline std::vector<std::uint32_t> AddGainOutput(std::span<const std::uint32_t> words) {
    enum : std::uint32_t {
        OpExtInstImport = 11, OpExtInst = 12, OpEntryPoint = 15, OpTypeBool = 20, OpTypeFloat = 22,
        OpTypeVector = 23, OpTypePointer = 32, OpConstant = 43, OpFunction = 54, OpVariable = 59,
        OpStore = 62, OpAccessChain = 65, OpDecorate = 71, OpCompositeConstruct = 80,
        OpFNegate = 127, OpBitcast = 124, OpFMul = 133, OpFDiv = 136, OpFSub = 131,
    };
    enum : std::uint32_t { GlslExp = 27, GlslFMax = 40, GlslFClamp = 43 };
    constexpr std::uint32_t DecorationLocation = 30;
    if (words.size() < 6 || words[0] != 0x07230203u) {
        return {};
    }

    struct Inst {
        std::size_t at;
        std::uint32_t count, op;
    };
    std::vector<Inst> insts;
    for (std::size_t i = 5; i < words.size();) {
        const std::uint32_t count = words[i] >> 16;
        if (count == 0 || i + count > words.size()) {
            return {};
        }
        insts.push_back({i, count, words[i] & 0xffff});
        i += count;
    }

    std::uint32_t float_t = 0, ext = 0;
    std::unordered_map<std::uint32_t, std::uint32_t> constants; // bits -> id
    std::unordered_map<std::uint32_t, std::uint32_t> negated, access_base, var_type;
    std::unordered_map<std::uint32_t, std::uint32_t> pointee, vector_size;
    std::unordered_map<std::uint32_t, bool> bitcasts;
    std::size_t entry = 0, decorate = 0, function = 0, last_stores = 0;
    std::vector<std::size_t> stores;
    for (const auto& in : insts) {
        const auto w = words.data() + in.at;
        switch (in.op) {
        case OpTypeFloat:
            if (w[2] == 32) float_t = w[1];
            break;
        case OpExtInstImport: ext = w[1]; break;
        case OpEntryPoint: entry = in.at; break;
        case OpDecorate:
            if (!decorate) decorate = in.at;
            break;
        case OpFunction:
            if (!function) function = in.at;
            break;
        case OpTypeVector:
            if (w[2] == float_t) vector_size[w[1]] = w[3];
            break;
        case OpTypePointer: pointee[w[1]] = w[3]; break;
        case OpVariable: var_type[w[2]] = w[1]; break;
        case OpConstant:
            if (in.count == 4 && w[1] == float_t) constants[w[3]] = w[2];
            break;
        case OpFNegate: negated[w[2]] = w[3]; break;
        case OpBitcast: bitcasts[w[2]] = true; break;
        case OpAccessChain: access_base[w[2]] = w[3]; break;
        case OpStore: stores.push_back(in.at); break;
        default: break;
        }
    }
    if (!float_t || !ext || !entry || !decorate || !function || stores.size() < 4) {
        return {};
    }
    last_stores = stores[stores.size() - 4];

    const auto bits = [](float x) {
        std::uint32_t b;
        std::memcpy(&b, &x, sizeof(b));
        return b;
    };
    // The curve's three inputs: max(2^-14, c).
    const auto eps = constants.find(bits(1.0f / 16384.0f));
    if (eps == constants.end()) {
        return {};
    }
    std::vector<std::uint32_t> inputs, input_ids;
    for (const auto& in : insts) {
        const auto w = words.data() + in.at;
        if (in.op == OpExtInst && in.count == 7 && w[3] == ext && w[4] == GlslFMax &&
            w[5] == eps->second) {
            inputs.push_back(w[6]);
            input_ids.push_back(w[2]);
        }
    }
    if (inputs.size() != 3) {
        return {};
    }
    // K: the guest constant in -max(2^-14, c) * K.
    std::optional<std::uint32_t> k;
    for (const auto& in : insts) {
        if (in.op != OpFMul) continue;
        const auto w = words.data() + in.at;
        for (const auto [a, b] : {std::pair{w[3], w[4]}, std::pair{w[4], w[3]}}) {
            const auto neg = negated.find(a);
            if (neg != negated.end() && bitcasts.count(b) &&
                std::find(input_ids.begin(), input_ids.end(), neg->second) != input_ids.end()) {
                k = b;
            }
        }
    }
    if (!k) {
        return {};
    }
    // The fragment output the last stores write, for its pointer and vector types.
    const std::uint32_t target = words[last_stores + 1];
    const auto base = access_base.find(target);
    if (base == access_base.end()) {
        return {};
    }
    const auto ptr_type = var_type.find(base->second);
    if (ptr_type == var_type.end()) {
        return {};
    }
    const auto vec_type = pointee.find(ptr_type->second);
    if (vec_type == pointee.end()) {
        return {};
    }
    const auto size = vector_size.find(vec_type->second);
    if (size == vector_size.end() || size->second != 4) {
        return {};
    }

    std::uint32_t bound = words[3];
    std::vector<std::uint32_t> globals, code;
    const auto constant = [&](float x) {
        const auto [it, added] = constants.try_emplace(bits(x), bound);
        if (added) {
            globals.insert(globals.end(), {(4u << 16) | OpConstant, float_t, bound, bits(x)});
            ++bound;
        }
        return it->second;
    };
    const auto emit = [&](std::uint32_t op, std::initializer_list<std::uint32_t> args) {
        const std::uint32_t id = bound++;
        code.insert(code.end(),
                    {(std::uint32_t(args.size() + 3) << 16) | op, float_t, id});
        code.insert(code.end(), args);
        return id;
    };
    const auto glsl = [&](std::uint32_t fn, std::initializer_list<std::uint32_t> args) {
        const std::uint32_t id = bound++;
        code.insert(code.end(),
                    {(std::uint32_t(args.size() + 5) << 16) | OpExtInst, float_t, id, ext, fn});
        code.insert(code.end(), args);
        return id;
    };
    const std::uint32_t zero = constant(0.0f), one = constant(1.0f);
    const std::uint32_t small_e = constant(1.0f / 4096.0f), max_gain = constant(MaxGain);
    const std::uint32_t output = bound++;

    const std::uint32_t largest =
        glsl(GlslFMax, {glsl(GlslFMax, {input_ids[0], input_ids[1]}), input_ids[2]});
    const std::uint32_t e = glsl(GlslFMax, {emit(OpFMul, {largest, *k}), small_e});
    const std::uint32_t exp_e = glsl(GlslExp, {emit(OpFNegate, {e})});
    const std::uint32_t curve = emit(OpFSub, {one, exp_e});
    const std::uint32_t gain = glsl(GlslFClamp, {emit(OpFDiv, {e, curve}), one, max_gain});
    const std::uint32_t composite = bound++;
    code.insert(code.end(), {(7u << 16) | OpCompositeConstruct, vec_type->second, composite, gain,
                             zero, zero, one});
    code.insert(code.end(), {(3u << 16) | OpStore, output, composite});
    globals.insert(globals.end(), {(4u << 16) | OpVariable, ptr_type->second, output, 3u /*Output*/});

    // Back to front, so that the positions found above stay right.
    std::vector<std::uint32_t> out(words.begin(), words.end());
    out.insert(out.begin() + std::ptrdiff_t(last_stores), code.begin(), code.end());
    out.insert(out.begin() + std::ptrdiff_t(function), globals.begin(), globals.end());
    const std::array<std::uint32_t, 4> location{(4u << 16) | OpDecorate, output, DecorationLocation,
                                                Attachment};
    out.insert(out.begin() + std::ptrdiff_t(decorate), location.begin(), location.end());
    const std::uint32_t entry_count = out[entry] >> 16;
    out.insert(out.begin() + std::ptrdiff_t(entry + entry_count), output);
    out[entry] = ((entry_count + 1) << 16) | OpEntryPoint;
    out[3] = bound;
    return out;
}

} // namespace Vulkan::NativeHdrGain
