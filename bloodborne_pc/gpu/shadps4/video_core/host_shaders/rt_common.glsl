// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: ray tracing (vk_ray_tracing.h): the frame's camera, shared by the rt_*.comp passes.
#extension GL_EXT_buffer_reference : require
#extension GL_EXT_shader_explicit_arithmetic_types_int64 : require

// RayTracing::Record writes it once a frame (host visible).
layout(buffer_reference, std430, buffer_reference_align = 16) readonly buffer FrameConstants {
    vec4 view[3];     // world to view, rows
    vec4 inv_view[3]; // view to world, rows
    vec4 proj;        // x scale, y scale, z scale, z offset (clip = (x sx, y sy, z zs + zo, z))
    vec2 inv_scale;   // 1 / proj.xy
    vec2 jitter;      // viewport shift, render pixels
    vec2 size;        // render pixels
    uint frame_index;
    uint pad;
    vec4 light;       // towards the moon, world space (zero: none)
};

// Object motion's clip positions (vk_object_motion.h).
layout(buffer_reference, std430, buffer_reference_align = 16) readonly buffer ClipPositions {
    vec4 clip[];
};

// Per structure (entry slot): camera rays of rt_check.comp whose first hit on it matched the
// game's depth (x on a front face, y on a back face), and that found the game drew something
// farther there (z front, w back: seen through, a cut-out of foliage, fences or grates; the game
// masks them in hardware, not in its shaders). Faces are counted apart: the game culls the faces
// that turn away from the camera and the structure keeps both, so only see-through hits on the
// face the game draws (the one most matches are on) say the structure has gaps.
layout(buffer_reference, std430, buffer_reference_align = 16) buffer CoverageStats {
    uvec4 counts[];
};

const uint CoverageSamples = 48u; // counts before a structure's coverage is trusted

// The share of a structure's surface that blocks light, from those counts, or `unknown`.
float Coverage(CoverageStats stats, uint slot, float unknown) {
    const uvec4 c = stats.counts[slot];
    const uint matched = c.x + c.y;
    const uint through = c.x >= c.y ? c.z : c.w;
    const uint n = matched + through;
    return n < CoverageSamples ? unknown : float(matched) / float(n);
}

vec3 ClipToView(FrameConstants f, vec4 c) {
    return vec3(c.x * f.inv_scale.x, c.y * f.inv_scale.y, c.w);
}

vec3 ViewToWorld(FrameConstants f, vec3 v) {
    const vec4 p = vec4(v, 1.0);
    return vec3(dot(f.inv_view[0], p), dot(f.inv_view[1], p), dot(f.inv_view[2], p));
}
