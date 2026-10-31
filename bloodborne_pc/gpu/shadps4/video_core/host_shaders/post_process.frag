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

void main() {
    vec4 color_linear = texture(texSampler, uv);
    if (pp.srgb_input) color_linear.rgb = degamma(color_linear.rgb);
    if (pp.hdr) {
        color = vec4(ToneMapBloodborneHDR(color_linear.rgb), color_linear.a);
    } else {
        vec3 encoded = gamma(color_linear.rgb);
        if (pp.sdr_on_hdr) encoded = gamma22_for_srgb_decode(encoded);
        color = vec4(encoded, color_linear.a);
    }
}
