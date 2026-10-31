// SPDX-License-Identifier: GPL-2.0-or-later
// NVIDIA GeForce generations by the Vulkan device name ("NVIDIA GeForce RTX 4080 SUPER"), the
// DLSS model each runs best (bbport.ini dlss_model=auto), and the cards DLSS 5 is offered on.
// Plain C, so tools/ can use it too. Cases: tests/test_nvidia_gpu.cpp.
#pragma once

#include <stdint.h>
#include <string.h>

#include "bbport_dlss_models.h" // BbDlssPresetName

#define BB_VENDOR_NVIDIA 0x10DEu

/// GeForce RTX 20, 30, 40, 50, or 0 for anything else (GTX, workstation cards without a
/// generation in the name, other vendors).
enum BbNvidiaGeneration { BbNvidiaOther = 0, BbNvidiaRtx20 = 20, BbNvidiaRtx30 = 30,
                          BbNvidiaRtx40 = 40, BbNvidiaRtx50 = 50 };

/// The four-digit number after "RTX " in `name` (4080 for "RTX 4080 SUPER"), or 0 ("RTX A4000",
/// "RTX PRO 6000", no "RTX ").
static inline int BbRtxNumber(const char* name) {
    const char* rtx = name ? strstr(name, "RTX ") : NULL;
    if (!rtx) {
        return 0;
    }
    int number = 0, digits = 0;
    for (const char* c = rtx + 4; *c >= '0' && *c <= '9' && digits < 5; ++c, ++digits) {
        number = number * 10 + (*c - '0');
    }
    return digits == 4 ? number : 0;
}

/// The RTX generation of `name`: the number after "RTX " (2060 .. 5090; also laptops), or the
/// workstation "RTX 4000/5000/6000 Ada Generation" (RTX 40). Others: BbNvidiaOther.
static inline int BbNvidiaGen(uint32_t vendor_id, const char* name) {
    if (vendor_id != BB_VENDOR_NVIDIA || !name) {
        return BbNvidiaOther;
    }
    const int number = BbRtxNumber(name);
    if (!number) {
        return BbNvidiaOther;
    }
    if (number % 1000 == 0) {
        return strstr(name, "Ada") ? BbNvidiaRtx40 : BbNvidiaOther;
    }
    const int generation = number / 1000 * 10;
    return generation >= BbNvidiaRtx20 && generation <= BbNvidiaRtx50 ? generation
                                                                       : BbNvidiaOther;
}

/// The DLSS render preset (NVSDK_NGX_DLSS_Hint_Render_Preset) dlss_model=auto picks for a card
/// generation and quality mode (0 DLAA, 1 Quality, 2 Balanced, 3 Performance, 4 Ultra
/// Performance): RTX 20/30 have no FP8, on which DLSS 4.5's M and L cost about twice K, so K
/// in every mode; RTX 40/50 NVIDIA's defaults (DLSS 310 SDK): K for DLAA, Quality and Balanced,
/// DLSS 4.5's M for Performance and L for Ultra Performance. M in the first three cost an RTX
/// 4090 at 4K 0.7-2.7 ms more than K a frame (DLAA 3.9 against 1.2 ms: 55 FPS, below the 60 cap;
/// docs/dlss-4.2.0-comparison.md). 0: the driver's choice.
static inline unsigned BbDlssAutoPreset(int generation, int quality) {
    enum { PresetK = 11, PresetL = 12, PresetM = 13 };
    if (generation == BbNvidiaRtx20 || generation == BbNvidiaRtx30) {
        return PresetK;
    }
    if (generation == BbNvidiaRtx40 || generation == BbNvidiaRtx50) {
        return quality >= 4 ? PresetL : quality == 3 ? PresetM : PresetK;
    }
    return 0;
}

/// Whether DLSS 5 (neural rendering, experimental) is offered on this card: desktop GeForce RTX
/// 4080, 4080 SUPER, 4090 and 4090 D, and RTX 50 from the 5070 Ti up (decision 5: the community
/// bridge needs that much GPU time); never a laptop GPU. When not, `reason` (if not null) gets
/// why (static text).
static inline int BbDlss5Eligible(uint32_t vendor_id, const char* name, const char** reason) {
    const int generation = BbNvidiaGen(vendor_id, name);
    const int number = BbRtxNumber(name);
    const char* why = NULL;
    if (generation != BbNvidiaRtx40 && generation != BbNvidiaRtx50) {
        why = "needs a GeForce RTX 4080, 4090 or newer";
    } else if (strstr(name, "Laptop")) {
        why = "not offered on laptop GPUs";
    } else if (generation == BbNvidiaRtx40 && number != 4080 && number != 4090) {
        why = "needs a GeForce RTX 4080, 4090 or newer";
    } else if (generation == BbNvidiaRtx50 && number < 5080 &&
               !(number == 5070 && strstr(name, "5070 Ti"))) {
        why = "needs a GeForce RTX 5070 Ti or faster";
    }
    if (reason) {
        *reason = why;
    }
    return why == NULL;
}
