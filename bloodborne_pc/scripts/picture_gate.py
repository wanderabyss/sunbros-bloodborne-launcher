#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""The HD Texture Pack's safety gate: only picture files get through.

A texture mod may only change how the game looks, never what it does: no map layouts, events,
AI, params, text, animation, collision, lights or draw params (plans/pc-enhancements.md, rule
0.2.1). Every file the pack builder (hd_texture_pack.py) takes from a download, and every file of
a mod folder marked "picture_only" (mods.py), goes through here.

- Map texture archives (map/mXX/mXX_000N.tpfbhd + .tpfbdt) are accepted when they hold only
  texture files the game's archive already has (merged texture by texture by the builder).
  Lightmaps are not in these archives (they are in gi_env_mXX, which is refused), and a lightmap
  name (_gi_) inside one is refused too.
- Containers that mix pictures with other data (armour parts/*.partsbnd.dcx, effects
  sfx/*.ffxbnd.dcx) keep the game's own non-texture entries: the mod's textures are put into
  the game's container.
- Loose textures (*.tpf, *.tpf.dcx) are accepted when their textures are the game's names.
- Everything else is refused, with the reason.
"""
import argparse
from pathlib import PurePosixPath
import re
import sys

import fromsoft

ACCEPT, TEXTURES_ONLY, REFUSE = 'accept', 'textures_only', 'refuse'

MAP_ARCHIVE = re.compile(r'^map/m\d\d/m\d\d(_\d\d)?_\d{4}\.tpfb(hd|dt)$')
CONTAINERS = (re.compile(r'^parts/[a-z]{2}_[a-z]_\d{4}\.partsbnd\.dcx$'),
              re.compile(r'^sfx/frpg_sfxbnd_[a-z0-9_]+\.ffxbnd\.dcx$'))
LOOSE_TEXTURE = re.compile(r'\.tpf(\.dcx)?$')
# What a refused path is, for the report (the first match names it).
GAMEPLAY = (('.msb', 'map layout'), ('.emevd', 'event script'), ('.luabnd', 'AI script'),
            ('.talkesdbnd', 'talk script'), ('.esd', 'state machine'), ('param/', 'game parameters'),
            ('paramdef/', 'parameter layouts'), ('msg/', 'game text'), ('action/', 'behaviour'),
            ('.anibnd', 'animation'), ('.behbnd', 'behaviour'), ('.hkx', 'collision or physics'),
            ('.btl', 'lights'), ('.gparam', 'draw parameters'), ('drawparam', 'draw parameters'),
            ('.fmg', 'game text'), ('.flver', 'model'), ('.objbnd', 'object'), ('.chrbnd', 'character'),
            ('.mtd', 'material'), ('.patch', "the game's update archive"),
            ('gi_env', "the game's lightmaps"), ('eboot.bin', 'program'), ('sce_', 'system file'))
PROGRAMS = ('.exe', '.dll', '.ini', '.py', '.bat', '.cmd', '.ps1', '.lua', '.js', '.vbs')


def rule(path):
    """(kind, reason) for a game path under dvdroot_ps4, by its name only: kind is 'map',
    'container', 'texture' or None (refused)."""
    path = PurePosixPath(str(path).replace('\\', '/')).as_posix().casefold()
    if path.startswith('dvdroot_ps4/'):
        path = path[len('dvdroot_ps4/'):]
    if path.endswith(PROGRAMS):
        return None, 'a program or script'
    if MAP_ARCHIVE.match(path):
        return 'map', 'map texture archive'
    if any(c.match(path) for c in CONTAINERS):
        return 'container', 'textures inside a container'
    for marker, what in GAMEPLAY:
        if marker in path:
            return None, what
    if LOOSE_TEXTURE.search(path):
        return 'texture', 'texture file'
    return None, 'not a picture file'


def quick(path):
    """Path and type rules only: what mods.py checks at every start for a picture-only mod."""
    return rule(path)[0] is not None


class Verdict:
    def __init__(self, verdict, reason, data=None):
        self.verdict, self.reason, self.data = verdict, reason, data

    def __repr__(self):
        return f'Verdict({self.verdict}, {self.reason!r})'


def _texture_names(tpf_bytes):
    return {t['name'].casefold() for t in fromsoft.Tpf.head(tpf_bytes).textures}


def check_map_header(game_bhd, mod_bhd):
    """Problems with a mod's map archive header against the game's (empty: accepted)."""
    try:
        mod = fromsoft.Bxf4(mod_bhd)
    except fromsoft.FormatError as error:
        return [f'not a map texture archive ({error})']
    game = fromsoft.Bxf4(game_bhd).index()
    problems = [f'{name}: not in the game\'s archive' for name in mod.names if name.casefold() not in game]
    problems += [f'{name}: a lightmap' for name in mod.names if '_gi_' in name.casefold()]
    problems += [f'{name}: not a texture file' for name in mod.names
                 if not name.casefold().endswith(('.tpf', '.tpf.dcx'))]
    return problems


def check_map_entry(game_entry, mod_entry):
    """A map archive entry: a TPF whose textures are the game entry's."""
    try:
        if _texture_names(mod_entry) - _texture_names(game_entry):
            return 'textures the game\'s file does not have'
    except fromsoft.FormatError as error:
        return f'not a texture file ({error})'
    return None


def check_container(game_bytes, mod_bytes):
    """Armour and effect containers: Verdict with the bytes to use. The mod's file when only its
    textures differ from the game's; else the game's container with the mod's textures put in."""
    try:
        game = fromsoft.Bnd4(fromsoft.dcx_decompress(game_bytes))
        mod = fromsoft.Bnd4(fromsoft.dcx_decompress(mod_bytes))
    except fromsoft.FormatError as error:
        return Verdict(REFUSE, f'not a readable container ({error})')
    mine = {name.casefold(): i for i, name in enumerate(mod.names)}
    changed, kept, refused = 0, [], []
    for i, name in enumerate(game.names):
        j = mine.pop(name.casefold(), None)
        if j is None or mod.files[j] == game.files[i]:
            continue
        if name.casefold().endswith('.tpf'):
            problem = check_map_entry(game.files[i], mod.files[j])
            if problem:
                refused.append(f'{name}: {problem}')
                continue
            game.files[i] = mod.files[j]
            changed += 1
        else:
            kept.append(name)
    extra = [mod.names[j] for j in mine.values()]
    if not changed:
        return Verdict(REFUSE, 'no texture changes' + (f'; {len(kept)} other files differ' if kept else ''))
    if not kept and not extra and not refused:
        return Verdict(ACCEPT, f'{changed} textures', mod_bytes)
    notes = [f'{changed} textures from the mod']
    if kept:
        notes.append(f"the game's {', '.join(n.rsplit(chr(92), 1)[-1] for n in kept[:5])}"
                     + (f' and {len(kept) - 5} more' if len(kept) > 5 else '') + ' kept')
    if extra:
        notes.append(f'{len(extra)} files the game lacks left out')
    if refused:
        notes.append('; '.join(refused[:3]))
    return Verdict(TEXTURES_ONLY, ', '.join(notes),
                   fromsoft.dcx_compress(game.to_bytes(), template=game_bytes))


def check_texture(game_bytes, mod_bytes):
    try:
        if _texture_names(mod_bytes) - _texture_names(game_bytes):
            return Verdict(REFUSE, "textures the game's file does not have")
    except fromsoft.FormatError as error:
        return Verdict(REFUSE, f'not a texture file ({error})')
    return Verdict(ACCEPT, 'texture file', mod_bytes)


def main():
    parser = argparse.ArgumentParser(description='Which of these game paths are picture files?')
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    for path in args.paths:
        kind, reason = rule(path)
        print(f'{"ok    " if kind else "REFUSE"} {path}: {reason}')


if __name__ == '__main__':
    sys.exit(main())
