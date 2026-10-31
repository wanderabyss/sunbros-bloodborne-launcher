// SPDX-License-Identifier: GPL-2.0-or-later
// The menu pointer's window-to-stage mapping (gpu/shim/stage_point.h); no window or game needed.
#include <cassert>
#include <cmath>
#include <cstdio>
#include "stage_point.h"

static bool near(float a, float b) { return std::fabs(a - b) < 0.01f; }

int main() {
    float x, y;
    // 16:9 frame in a 16:9 window: a plain scale.
    assert(BbStage::Point(640, 360, 1280, 720, 2560, 1440, &x, &y) && near(x, 960) && near(y, 540));
    assert(BbStage::Point(0, 0, 1280, 720, 1920, 1080, &x, &y) && near(x, 0) && near(y, 0));
    // A 16:10 window: black bars above and below the 16:9 frame; a point on a bar is off stage.
    assert(BbStage::Point(800, 500, 1600, 1000, 1920, 1080, &x, &y) && near(x, 960) && near(y, 540));
    assert(!BbStage::Point(800, 20, 1600, 1000, 1920, 1080, &x, &y));
    // An ultrawide frame (3440x1440) in its own window: the stage is centred, the sides are off it.
    assert(BbStage::Point(1720, 720, 3440, 1440, 3440, 1440, &x, &y) && near(x, 960) && near(y, 540));
    assert(BbStage::Point(440, 0, 3440, 1440, 3440, 1440, &x, &y) && near(x, 0) && near(y, 0));
    assert(!BbStage::Point(100, 720, 3440, 1440, 3440, 1440, &x, &y));
    // Nothing presented yet.
    assert(!BbStage::Point(10, 10, 1280, 720, 0, 0, &x, &y));
    std::puts("Stage point: letterbox, high-DPI scale and ultrawide mapping PASS");
}
