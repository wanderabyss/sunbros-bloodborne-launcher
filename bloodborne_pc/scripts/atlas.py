#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Hunter's Atlas (MikeTat1988/HuntersAtlas, GPL-2.0): the full-screen map's files.

  atlas.py prepare --game GAME --out DIR   make the maps from the player's own game (5-15 min)
  atlas.py status --out DIR                ready / not prepared, as one line

The maps come from Atlas's generator (tools/atlas/generator, frozen in a release as
tools/atlas-generator/generate_atlas.exe); its art is converted to the engine's BBRA format.
run.py turns the map on with environment() when bbport.ini atlas_enabled=1 and the maps are
ready. Nothing is written into the game folder.
"""
import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

PORT = Path(__file__).resolve().parent.parent
ART = PORT / 'tools' / 'atlas' / 'art'
GENERATOR_SOURCE = PORT / 'tools' / 'atlas' / 'generator' / 'generate_atlas.py'
GENERATOR_FROZEN = PORT / 'tools' / 'atlas-generator' / 'generate_atlas.exe'
# bbport.ini keys -> the map's own switches (Atlas's atlas_feature_config.py).
FEATURES = {'atlas_travel': 'BB_MAP_TRAVEL_ENABLED', 'atlas_fog': 'BB_MAP_FOG_ENABLED',
            'atlas_items': 'BB_MAP_ITEMS_ENABLED'}
NPC_MODES = ('all', 'new_dialogue', 'hidden')


def ready(out):
    out = Path(out)
    is_ready = ((out / 'maps' / 'generated-assets.json').is_file() and (out / 'maps' / 'catalog.json').is_file()
                and (out / 'art' / 'native-font.ttf').is_file() and (out / 'art' / 'menu.bbra').is_file())
    if is_ready:
        return True
    candidates = [
        PORT / 'ATLAS' / 'atlas',
        PORT.parent / 'ATLAS' / 'atlas',
        PORT.parent.parent / 'ATLAS' / 'atlas',
    ]
    candidate = next((c for c in candidates if c.is_dir()), PORT / 'ATLAS' / 'atlas')
    if candidate.is_dir() and candidate.resolve() != out.resolve():
        if ((candidate / 'maps' / 'generated-assets.json').is_file() and (candidate / 'maps' / 'catalog.json').is_file()
                and (candidate / 'art' / 'native-font.ttf').is_file() and (candidate / 'art' / 'menu.bbra').is_file()):
            try:
                out.mkdir(parents=True, exist_ok=True)
                for folder in ('art', 'maps'):
                    d = out / folder
                    s = candidate / folder
                    if not d.exists() and s.is_dir():
                        shutil.copytree(s, d)
                return True
            except Exception:
                return True
    return False


def environment(settings, out):
    """The engine's map variables for bbport.ini `settings`, or {} when the map is off or its
    files are not prepared."""
    out = Path(out)
    if str(settings.get('atlas_enabled', '0')) != '1' or not ready(out):
        return {}
    env = {'BB_ATLAS_ENABLED': '1', 'BB_MAP_DIR': str(out / 'maps'), 'BB_MAP_ART_DIR': str(out / 'art'),
           'BB_MAP_CATALOG': str(out / 'maps' / 'catalog.json'), 'BB_MAP_FONT': str(out / 'art' / 'native-font.ttf'),
           'BB_MAP_CONFIG': str(out / 'settings.ini')}
    for key, variable in FEATURES.items():
        env[variable] = '1' if str(settings.get(key, '0')) == '1' else '0'
    env['BB_MAP_ITEM_CATEGORIES'] = 'healing,insight,equipment,echoes'
    mode = settings.get('atlas_npc_mode', 'all')
    env['BB_MAP_NPC_MODE'] = mode if mode in NPC_MODES else 'all'
    return env


def convert_art(out):
    """Atlas's PNG art as BBRA (b'BBRA', width, height, RGBA rows), as its release build does."""
    from PIL import Image
    target = Path(out) / 'art'
    target.mkdir(parents=True, exist_ok=True)
    for picture in sorted(ART.glob('*.png')):
        with Image.open(picture) as image:
            image = image.convert('RGBA')
            data = b'BBRA' + struct.pack('<II', *image.size) + image.tobytes()
        (target / (picture.stem + '.bbra')).write_bytes(data)
    shutil.copyfile(ART / 'fallback.ttf', target / 'fallback.ttf')


def generator_command(game, out):
    if GENERATOR_FROZEN.is_file():
        command = [str(GENERATOR_FROZEN)]
    else:
        # A source checkout: a Python with tools/atlas/generator/requirements-runtime.txt.
        command = [os.environ.get('BB_ATLAS_PYTHON') or sys.executable, str(GENERATOR_SOURCE)]
    replace = ['--replace'] if (Path(out) / 'maps' / 'generated-assets.json').exists() else []
    return command + ['--game-dir', str(game), '--output-dir', str(out), *replace]


def prepare(game, out, progress=print):
    """Runs the generator; `progress` gets its lines ({"progress": n, "stage": ...})."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    candidate = PORT / 'ATLAS' / 'atlas'
    if candidate.is_dir() and candidate.resolve() != out.resolve():
        if ((candidate / 'maps' / 'generated-assets.json').is_file() and (candidate / 'maps' / 'catalog.json').is_file()):
            progress('Installing pre-packaged Hunter\'s Atlas maps…')
            for folder in ('art', 'maps'):
                s = candidate / folder
                d = out / folder
                if s.is_dir():
                    if d.exists():
                        shutil.rmtree(d)
                    shutil.copytree(s, d)
            if ready(out):
                progress('Hunter\'s Atlas maps are ready.')
                return
    command = generator_command(game, out)
    creation = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    # The source generator imports its sibling modules: it runs from its own folder.
    cwd = None if GENERATOR_FROZEN.is_file() else str(GENERATOR_SOURCE.parent)
    process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8', errors='replace', creationflags=creation)
    last = ''
    with open(out / 'prepare.log', 'w', encoding='utf-8') as log:
        if process.stdout is not None:
            for line in process.stdout:
                log.write(line)
                line = line.strip()
                if line:
                    last = line
                    progress(line)
    if process.wait() != 0:
        raise RuntimeError(f'the map generator stopped (exit code {process.returncode}): {last[-300:]}')
    convert_art(out)
    if not ready(out):
        raise RuntimeError('the map generator finished without the maps')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('prepare', 'status'))
    parser.add_argument('--game', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'status':
        print('ready' if ready(args.out) else 'not prepared')
        return
    if not args.game:
        parser.error('prepare needs --game')
    prepare(args.game, args.out)
    print(json.dumps({'progress': 100, 'stage': 'Maps ready'}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f'Atlas: {error}', file=sys.stderr)
        sys.exit(1)
