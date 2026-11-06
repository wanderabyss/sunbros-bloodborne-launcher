// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#version 450

layout (location = 0) in vec2 uv;
layout (location = 0) out vec4 color;

layout (binding = 0) uniform sampler2D texSampler;

layout (push_constant) uniform settings {
    float gamma;
    bool hdr;
    bool srgb_input;
    bool sdr_on_hdr;
    // bbport: HDR brightness (bbport_settings.h HdrLevels): SDR white and the ceiling in nits,
    // and the highlight expansion, 0..1.
    float white_nits;
    float peak_nits;
    float boost;
    // bbport: native HDR (vk_native_hdr.h): 0 off, 1 the gain is in alpha, 2 no gain (menus).
    uint native;
    // bbport: how much of the color native HDR rebuilds, 0..1 (hdr_native_color).
    float native_color;
    // bbport: native HDR's curve: gain in stops where highlights start, and where they reach the
    // display's peak (hdr_native_start, hdr_native_end; the overlay's HDR curve).
    float native_start;
    float native_end;
    // bbport: the most native HDR raises a highlight over the SDR picture (hdr_native_boost).
    float native_boost;
} pp;

const float cutoff = 0.0031308, a = 1.055, b = 0.055, d = 12.92;
vec3 gamma(vec3 rgb) {
    return mix(
        a * pow(rgb, vec3(1.0 / (2.4 + 1.0 - pp.gamma))) - b,
        d * rgb / pp.gamma,
        lessThan(rgb, vec3(cutoff))
    );
}

// Exact inverse of gamma() at unit gamma, for buffers that are sRGB encoded but must be sampled
// through a UNORM view because Vulkan has no sRGB variant of the 10-bit format.
vec3 degamma(vec3 rgb) {
    return mix(
        pow(max(rgb + b, 0.0) / a, vec3(2.4)),
        rgb / d,
        lessThan(rgb, vec3(d * cutoff))
    );
}

// bbport: Windows decodes an SDR swapchain on an HDR display with the piecewise sRGB curve, while
// an SDR display (and the TV the game was graded on) applies gamma 2.2. Near black the sRGB curve
// is several times brighter, which lifts the blacks. Re-encode so that decode gives gamma 2.2.
vec3 gamma22_for_srgb_decode(vec3 encoded) {
    vec3 rgb = pow(max(encoded, 0.0), vec3(2.2));
    return mix(a * pow(rgb, vec3(1.0 / 2.4)) - b, d * rgb, lessThan(rgb, vec3(cutoff)));
}

// ITU-R BT.709 to ITU-R BT.2020 color gamut conversion matrix (column-major in GLSL)
const mat3 MAT_709_TO_2020 = mat3(
    vec3(0.6274040, 0.0690970, 0.0163916),  // column 0
    vec3(0.3292820, 0.9195400, 0.0880132),  // column 1
    vec3(0.0433136, 0.0113612, 0.8955950)   // column 2
);

// SMPTE ST 2084 inverse EOTF: encodes linear display light as PQ signal values.
// Takes linear light normalized to [0, 1] where 1.0 = 10,000 cd/m² (nits).
vec3 ST2084_PQ(vec3 L) {
    const float m1 = 2610.0 / 16384.0;
    const float m2 = (2523.0 / 4096.0) * 128.0;
    const float c1 = 3424.0 / 4096.0;
    const float c2 = (2413.0 / 4096.0) * 32.0;
    const float c3 = (2392.0 / 4096.0) * 32.0;

    vec3 L_pow = pow(clamp(L, vec3(0.0), vec3(1.0)), vec3(m1));
    vec3 num = c1 + c2 * L_pow;
    vec3 den = 1.0 + c3 * L_pow;
    return pow(num / den, vec3(m2));
}

// SDR highlight expansion with a bounded display-light shoulder, not recovered HDR data.
// SDR white at pp.white_nits; the shoulder starts at 60% of pp.peak_nits and approaches it
// (defaults 120, 600 and 1000 nits: the fixed values before these settings).
vec3 ToneMapBloodborneHDR(vec3 linear_rgb) {
    linear_rgb = clamp(linear_rgb, vec3(0.0), vec3(100.0));
    float y = dot(linear_rgb, vec3(0.2126, 0.7152, 0.0722));
    // Soft highlight expansion shoulder above 50% SDR luminance
    float highlight = max(y - 0.5, 0.0) / 0.5;
    // Expands incandescent peaks up to ~6.5x at full boost
    float boost = 1.0 + 5.5 * pp.boost * pow(highlight, 2.2);
    vec3 rec2020_nits = max(MAT_709_TO_2020 * (linear_rgb * boost * pp.white_nits), vec3(0.0));
    // Bound the maximum channel while preserving chromaticity. The shoulder has unit
    // slope at the knee and asymptotically approaches the peak instead of hard clipping.
    float peak = max(max(rec2020_nits.r, rec2020_nits.g), rec2020_nits.b);
    float knee = 0.6 * pp.peak_nits, room = pp.peak_nits - knee;
    if (peak > knee) {
        float mapped = knee + room * (1.0 - exp(-(peak - knee) / room));
        rec2020_nits *= mapped / peak;
    }
    return ST2084_PQ(rec2020_nits / 10000.0);
}

// Inverse of ST2084_PQ: PQ signal to linear light, 1.0 = 10,000 nits.
vec3 ST2084_Linear(vec3 pq) {
    const float m1 = 2610.0 / 16384.0;
    const float m2 = (2523.0 / 4096.0) * 128.0;
    const float c1 = 3424.0 / 4096.0;
    const float c2 = (2413.0 / 4096.0) * 32.0;
    const float c3 = (2392.0 / 4096.0) * 32.0;
    vec3 p = pow(clamp(pq, vec3(0.0), vec3(1.0)), vec3(1.0 / m2));
    return pow(max(p - c1, vec3(0.0)) / (c2 - c3 * p), vec3(1.0 / m1));
}

// bbport: native HDR: the game's curve 1 - exp(-E) works per channel, so a bright colored light is
// nearly white in the SDR picture, and only scaling it gives a brighter, paler light. The gain gives
// the largest channel's E (gain = E / (1 - exp(-E))), and with the SDR ratios each channel's E comes
// back. Pixels with little or no gain (the scene's midtones, the HUD) keep the SDR color exactly.
vec3 RestoreColor(vec3 sdr_linear, float gain) {
    float e = gain;
    for (int i = 0; i < 4; ++i) {
        e = gain * (1.0 - exp(-e));
    }
    // Capped: at a large E any channel a little under the largest maps to almost nothing, which
    // turned colored lights into pure primaries (the SDR ratios aren't that exact).
    e = min(e, 3.0);
    float top = max(max(max(sdr_linear.r, sdr_linear.g), sdr_linear.b), 0.0001);
    vec3 ratio = clamp(sdr_linear / top, vec3(0.0), vec3(1.0));
    vec3 channels = -log(max(1.0 - ratio * (1.0 - exp(-e)), vec3(0.0001)));
    float largest = max(max(max(channels.r, channels.g), channels.b), 0.0001);
    return mix(sdr_linear * gain, channels * (top * gain / largest),
               pp.native_color * smoothstep(1.02, 1.25, gain));
}

// bbport: native HDR: linear SDR with the tone mapper's gain is scene light with the game's
// grading (1.0 = SDR white). BT.2390's roll-off on the largest channel, in PQ, keeps the
// chromaticity while highlights approach the peak; below the knee nothing changes.
vec3 NativeHdr(vec3 sdr_linear, float encoded_gain) {
    float gain = pp.native == 1u ? exp2((1.0 - encoded_gain) * 8.0) : 1.0;
    // The gain has render size and comes from before DLSS, frame generation and DLSS 5, so it can
    // miss the picture around fast movement. A pixel too dark for it gets what its own level allows
    // on the game's curve. Measured highlights sit at SDR levels of about 0.5 to 0.8 (the grading
    // keeps white under 1), so the limit fades out over that range.
    float level = clamp(max(max(sdr_linear.r, sdr_linear.g), sdr_linear.b), 0.001, 0.999);
    gain = mix(min(gain, max(-log(1.0 - level) / level, 1.0)), gain, smoothstep(0.5, 0.8, level));
    // The scene's range (gains above 100 in a heavy attack's flash) is far wider than the display's
    // room above white, so scaling it linearly pins a large flash flat at the peak. Log-compressed
    // between two gains, it fills that room and keeps shape inside the flash. Below the start stays
    // the SDR picture: a flash's soft cloud has moderate gain, and raising it reads as white bleeding
    // while the arcs, at far higher gain, carry the highlight. Highlights sit near an SDR level of
    // 0.75, hence the room above that. Never more than the gain itself.
    // Limited as well: a flash reads against the scene around it, so with the room alone a lower
    // paper white raised the flash further over its surroundings and bled more.
    float room = clamp(pp.peak_nits / pp.white_nits / 0.75, 1.0, max(pp.native_boost, 1.0));
    float along = (log2(max(gain, 1.0)) - pp.native_start) / max(pp.native_end - pp.native_start, 0.1);
    gain = min(gain, 1.0 + (room - 1.0) * clamp(along, 0.0, 1.0));
    vec3 nits = max(MAT_709_TO_2020 * (RestoreColor(sdr_linear, gain) * pp.white_nits), vec3(0.0));
    float largest = max(max(nits.r, nits.g), nits.b);
    if (largest > 0.0) {
        float e1 = ST2084_PQ(vec3(largest / 10000.0)).r;
        float top = ST2084_PQ(vec3(pp.peak_nits / 10000.0)).r;
        float knee = 1.5 * top - 0.5;
        if (e1 > knee) {
            float t = (e1 - knee) / (1.0 - knee);
            float t2 = t * t, t3 = t2 * t;
            float e2 = (2.0 * t3 - 3.0 * t2 + 1.0) * knee + (t3 - 2.0 * t2 + t) * (1.0 - knee) +
                       (-2.0 * t3 + 3.0 * t2) * top;
            nits *= ST2084_Linear(vec3(e2)).r * 10000.0 / largest;
        }
    }
    return ST2084_PQ(nits / 10000.0);
}

void main() {
    vec4 color_linear = texture(texSampler, uv);
    if (pp.srgb_input) color_linear.rgb = degamma(color_linear.rgb);
    if (pp.native != 0u) {
        color = vec4(NativeHdr(color_linear.rgb, color_linear.a), 1.0);
    } else if (pp.hdr) {
        color = vec4(ToneMapBloodborneHDR(color_linear.rgb), color_linear.a);
    } else {
        vec3 encoded = gamma(color_linear.rgb);
        if (pp.sdr_on_hdr) encoded = gamma22_for_srgb_decode(encoded);
        color = vec4(encoded, color_linear.a);
    }
}
