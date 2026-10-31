#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fill the original title art's baked side padding, using a generated menu overlay.

Only the identified full-stage title bitmap placement is zoomed, uniformly about the
stage centre. Text, command lists, timelines and the player's original files are kept.
The original MENU_Title_00001 has about 108 black pixels on each side of its 1920-pixel
stage; 112 crops that border and its sampling seam. The resulting ~13% zoom trims a small
amount from top/bottom instead of stretching the picture. Other aspect ratios stay as-is.
"""
import argparse
import os
from pathlib import Path
import struct

import hud_layout as gfx

MOVIES = ('title.gfx', 'title_dlc.gfx', 'title_dlc_eu.gfx')
ART_NAMES = {'MENU_Title_00001', 'MENU_Title_00004'}
PADDING = 112


def fill_title(data):
    if data[:3] not in (b'GFX', b'FWS'):
        raise ValueError('not an uncompressed title movie')
    rect = gfx.Reader(data, 8)
    bits = rect.unsigned(5)
    bounds = tuple(rect.signed(bits) for _ in range(4))
    if bounds != (0, 1920 * 20, 0, 1080 * 20):
        return None
    shapes, sprites, bitmaps = gfx.definitions(data)
    art = {key for key, (styles, left, right) in shapes.items()
           if left == 0 and right == 1920 and styles and len(styles) == 1
           and isinstance(styles[0], tuple) and bitmaps.get(styles[0][1]) in ART_NAMES}
    edits = {}
    zoom = 1920 / (1920 - 2 * PADDING)
    placements = (entry for start, end in [(gfx.stage_start(data), len(data)), *sprites.values()]
                  for entry in gfx.tags(data, start, end))
    for code, _, body, _length in placements:
        if code not in (26, 70):
            continue
        character, span, _name = gfx.place_fields(data, body, code)
        if character not in art or not span:
            continue
        (scale, rotation, translation), _ = gfx.read_matrix(data, span[0])
        # Recognize the original placement, rather than zooming a mod or an already edited movie.
        if (rotation and any(rotation)) or translation != (0, 0) or (scale and scale != (65536, 65536)):
            continue
        edits[body] = ((round(65536 * zoom), round(65536 * zoom)), None,
                       (round(960 * (1 - zoom) * 20), round(540 * (1 - zoom) * 20)))
    if not edits:
        return None
    start = gfx.stage_start(data)
    result = data[:start] + gfx.rewrite_timeline(data, start, len(data), edits)
    return result[:4] + struct.pack('<I', len(result)) + result[8:]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--settings', type=Path)
    p.add_argument('--source', type=Path, action='append', default=[])
    args = p.parse_args()
    target = args.out / 'dvdroot_ps4' / 'menu'
    for name in MOVIES:
        (target / name).unlink(missing_ok=True)
    settings = {}
    if args.settings and args.settings.is_file():
        for line in args.settings.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                settings[key.strip()] = value.strip()
    resolution = os.environ.get('BB_OUTPUT_RES') or settings.get('output_res', '1920x1080')
    try:
        width, height = map(int, resolution.split('x'))
    except ValueError:
        width, height = 1920, 1080
    if os.environ.get('BB_TITLE_FILL', '1') == '0' or width * 9 != height * 16:
        return
    written = 0
    for name in MOVIES:
        source = args.game / 'dvdroot_ps4' / 'menu' / name
        for layer in args.source:
            candidate = layer / 'dvdroot_ps4' / 'menu' / name
            if candidate.is_file():
                source = candidate
        if not source.is_file():
            continue
        try:
            result = fill_title(source.read_bytes())
        except (ValueError, IndexError, struct.error) as error:
            print(f'Title presentation: {name} unchanged ({error})')
            continue
        if result:
            target.mkdir(parents=True, exist_ok=True)
            (target / name).write_bytes(result)
            written += 1
    print(f'Title presentation: {written} title movies fill the screen; menu text unchanged')


if __name__ == '__main__':
    main()
