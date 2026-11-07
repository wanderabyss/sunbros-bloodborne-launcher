"""Bakes the launcher's sharp Home art and its dither tile from launcher/art/hero.png.

Home's art is shown sharp, with frost only behind its panels (GlassPanel.qml), so compression shows:
a bright HDR display makes JPEG blocks and banding in the dark sky plain. The art is enlarged 2x for
high-density windows (no detail is invented), kept at full colour resolution, and dithered.
Run again only when hero.png changes:  python scripts/bake_launcher_art.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

LAUNCHER = Path(__file__).resolve().parents[1] / "bloodborne_pc" / "launcher"
SCALE = 2
TILE = 256
SEED = 1387  # the same input bakes the same files


def triangular_noise(rng, shape, amplitude):
    """Dither with no visible pattern: two uniform samples, about +-amplitude levels."""
    return (rng.random(shape) - rng.random(shape)) * amplitude


def bake_home(rng):
    hero = Image.open(LAUNCHER / "art" / "hero.png").convert("RGB")
    large = hero.resize((hero.width * SCALE, hero.height * SCALE), Image.LANCZOS)
    large = large.filter(ImageFilter.UnsharpMask(radius=2.4, percent=70, threshold=2))
    pixels = np.asarray(large, dtype=np.float32)
    pixels += triangular_noise(rng, pixels.shape[:2] + (1,), 1.5)
    out = Image.fromarray(np.clip(pixels + 0.5, 0, 255).astype(np.uint8))
    out.save(LAUNCHER / "assets" / "ui" / "bg" / "home.jpg", quality=95, subsampling=0, optimize=True)


def bake_dither(rng):
    """Over the whole window: the translucent shades and glass gradients band without it. White or
    black at a very low alpha, about two levels on screen."""
    noise = triangular_noise(rng, (TILE, TILE), 1.0)
    tile = np.zeros((TILE, TILE, 4), dtype=np.uint8)
    tile[..., :3] = np.where(noise[..., None] > 0, 255, 0)
    tile[..., 3] = np.round(np.abs(noise) * 4).astype(np.uint8)
    Image.fromarray(tile, "RGBA").save(LAUNCHER / "assets" / "ui" / "dither.png", optimize=True)


if __name__ == "__main__":
    generator = np.random.default_rng(SEED)
    bake_home(generator)
    bake_dither(generator)
