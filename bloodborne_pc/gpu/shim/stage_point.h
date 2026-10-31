// SPDX-License-Identifier: GPL-2.0-or-later
// bbport: a window point on the menus' 1920x1080 Scaleform stage (the menu pointer). The
// presented frame is letterboxed into the window (vk_presenter.cpp FitImage) and the stage is
// centred in the frame at a uniform scale (show-all), which also covers non-16:9 outputs.
#pragma once

#include <algorithm>

namespace BbStage {

// (mx, my) in window units, the window (ww, wh) in the same units, the frame (fw, fh) in pixels.
// True when the point is on the stage.
inline bool Point(float mx, float my, float ww, float wh, float fw, float fh, float* x, float* y) {
    if (ww <= 0 || wh <= 0 || fw <= 0 || fh <= 0) return false;
    const float fit = std::min(ww / fw, wh / fh);
    const float fx = (mx - (ww - fw * fit) * 0.5f) / fit, fy = (my - (wh - fh * fit) * 0.5f) / fit;
    const float stage = std::min(fw / 1920.0f, fh / 1080.0f);
    *x = (fx - (fw - 1920.0f * stage) * 0.5f) / stage;
    *y = (fy - (fh - 1080.0f * stage) * 0.5f) / stage;
    return *x >= 0 && *y >= 0 && *x <= 1920.0f && *y <= 1080.0f;
}

} // namespace BbStage
