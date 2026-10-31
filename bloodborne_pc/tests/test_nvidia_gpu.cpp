// SPDX-License-Identifier: GPL-2.0-or-later
// gpu/shim/bbport_nvidia_gpu.h: generations from real Vulkan device names, the DLSS model
// dlss_model=auto picks for them, and the cards DLSS 5 is offered on.
#include "bbport_nvidia_gpu.h"
#include <cassert>
#include <cstdio>

int main() {
    const struct {
        unsigned vendor;
        const char* name;
        int generation;
    } cards[] = {
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 2060", BbNvidiaRtx20},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 2080 Ti", BbNvidiaRtx20},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 3060 Laptop GPU", BbNvidiaRtx30},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 3080", BbNvidiaRtx30},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 3090 Ti", BbNvidiaRtx30},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4060 Ti", BbNvidiaRtx40},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4070 Ti SUPER", BbNvidiaRtx40},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4080 SUPER", BbNvidiaRtx40},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4090 D", BbNvidiaRtx40},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4090 Laptop GPU", BbNvidiaRtx40},
        {BB_VENDOR_NVIDIA, "NVIDIA RTX 4000 Ada Generation", BbNvidiaRtx40},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 5070 Ti", BbNvidiaRtx50},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 5090", BbNvidiaRtx50},
        {BB_VENDOR_NVIDIA, "NVIDIA RTX A4000", BbNvidiaOther},
        {BB_VENDOR_NVIDIA, "NVIDIA RTX PRO 6000 Blackwell Workstation Edition", BbNvidiaOther},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce GTX 1080 Ti", BbNvidiaOther},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 9090", BbNvidiaOther},
        {0x1002, "AMD Radeon RX 7900 XTX", BbNvidiaOther},
        {0x1002, "RTX 4080 (not NVIDIA's vendor id)", BbNvidiaOther},
        {BB_VENDOR_NVIDIA, nullptr, BbNvidiaOther},
    };
    for (const auto& card : cards) {
        const int generation = BbNvidiaGen(card.vendor, card.name);
        if (generation != card.generation) {
            std::printf("%s: %d, expected %d\n", card.name ? card.name : "(null)", generation,
                        card.generation);
            assert(false);
        }
    }
    // RTX 20/30: K everywhere; RTX 40/50: K for DLAA, Quality and Balanced, M in Performance, L in
    // Ultra Performance (NVIDIA's defaults); others: the driver's.
    for (int quality = 0; quality <= 4; ++quality) {
        const unsigned ada = quality == 4 ? 12u : quality == 3 ? 13u : 11u;
        assert(BbDlssAutoPreset(BbNvidiaRtx20, quality) == 11);
        assert(BbDlssAutoPreset(BbNvidiaRtx30, quality) == 11);
        assert(BbDlssAutoPreset(BbNvidiaRtx40, quality) == ada);
        assert(BbDlssAutoPreset(BbNvidiaRtx50, quality) == ada);
        assert(BbDlssAutoPreset(BbNvidiaOther, quality) == 0);
    }
    // DLSS 5: desktop 4080 / 4090 (SUPER, D) and RTX 50 from the 5070 Ti; never laptops.
    const struct {
        unsigned vendor;
        const char* name;
        bool eligible;
    } dlss5[] = {
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4080", true},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4080 SUPER", true},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4090", true},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4090 D", true},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 5070 Ti", true},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 5080", true},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 5090", true},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 5090 D", true},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4070 Ti SUPER", false},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4060", false},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4090 Laptop GPU", false},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 5090 Laptop GPU", false},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 5070", false},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 5060 Ti", false},
        {BB_VENDOR_NVIDIA, "NVIDIA RTX 4000 Ada Generation", false},
        {BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 3090 Ti", false},
        {0x1002, "AMD Radeon RX 7900 XTX", false},
    };
    for (const auto& card : dlss5) {
        const char* reason = "unset";
        const bool eligible = BbDlss5Eligible(card.vendor, card.name, &reason) != 0;
        if (eligible != card.eligible || (reason == nullptr) != eligible) {
            std::printf("DLSS 5 %s: %d (%s), expected %d\n", card.name, eligible,
                        reason ? reason : "null", card.eligible);
            assert(false);
        }
    }
    assert(BbDlss5Eligible(BB_VENDOR_NVIDIA, "NVIDIA GeForce RTX 4080", nullptr));
    std::puts("NVIDIA generations, DLSS auto model and DLSS 5 cards PASS");
}
