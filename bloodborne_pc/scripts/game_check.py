#!/usr/bin/env python3
"""Damaged game extractions: the game's compressed files must unpack.

An extraction tool that leaves parts of compressed sectors stale (LibOrbisPkg PkgTool on .NET 6 or
newer, deadinside28/bloodborne_pc issue #81) makes the game hang while it loads its shaders, with
no error. run.py checks the shaders, which the game loads first; a broken extraction damages most
files, these among them. BB_SKIP_GAME_CHECK=1 skips it.

Run as a script, it checks every .dcx file of a game folder: game_check.py GAME_DIR

From deadinside28/bloodborne_pc 0.5-pre4 (10baf9d).
"""
import struct
import sys
import zlib
from pathlib import Path

CHECKED_FOLDER = 'dvdroot_ps4/shader'


def dcx_broken(path):
    """True when a DFLT .dcx file does not unpack to its stated size or fails zlib's checksum.
    Other compressions are not checked."""
    data = Path(path).read_bytes()
    if data[:4] != b'DCX\0' or data[0x18:0x1C] != b'DCS\0' or data[0x28:0x2C] != b'DFLT':
        return False
    size, packed = struct.unpack_from('>II', data, 0x1C)
    try:
        return len(zlib.decompress(data[0x4C:0x4C + packed])) != size
    except zlib.error:
        return True


def readable_and_broken(path):
    """dcx_broken, but a file that cannot be read now (locked by an antivirus or a sync tool)
    counts as intact: the check must not keep a good game from starting."""
    try:
        return dcx_broken(path)
    except OSError as error:
        print(f'Game check: {path} not checked ({error})', file=sys.stderr)
        return False


def broken_files(game, folder=CHECKED_FOLDER):
    """The .dcx files under the game's folder that do not unpack (paths relative to the game)."""
    root = Path(game)
    return [f.relative_to(root).as_posix() for f in sorted((root / folder).rglob('*.dcx'))
            if readable_and_broken(f)]


def explain(broken):
    return (f'The game files are damaged: {len(broken)} shader file(s) in {CHECKED_FOLDER} do not '
            f'unpack ({", ".join(broken[:3])}{", ..." if len(broken) > 3 else ""}), and the game '
            'would hang while loading them. The extraction tool left parts of compressed sectors '
            'stale (LibOrbisPkg PkgTool on .NET 6 or newer does): extract the game and the 1.09 '
            'update again with another tool. scripts/game_check.py GAME_DIR checks every file. '
            'BB_SKIP_GAME_CHECK=1 starts it anyway.')


# Present folders can still be empty. Deleting a mod overlay left in an agent's worktree once
# followed its folder junctions and emptied a whole dump except eboot.bin: the start then failed
# in prepare.py (sce_module/libc.prx), and the launcher showed the game as ready.
REQUIRED_FILES = ('sce_module/libc.prx', 'sce_module/libSceFios2.prx', 'sce_sys/param.sfo')
REQUIRED_CONTENT = ('dvdroot_ps4/chr', 'dvdroot_ps4/map', 'dvdroot_ps4/parts', 'dvdroot_ps4/sound')


def missing_files(game):
    """The files and content folders a start needs that `game` lacks (an empty folder is
    reported as '<folder> (empty)')."""
    game = Path(game)
    missing = [name for name in REQUIRED_FILES if not (game / name).is_file()]
    for name in REQUIRED_CONTENT:
        folder = game / name
        if not folder.is_dir() or not any(path.is_file() for path in folder.rglob('*')):
            missing.append(name + ' (empty)' if folder.is_dir() else name)
    return missing


def explain_missing(game, missing):
    more = f' and {len(missing) - 3} more' if len(missing) > 3 else ''
    return (f'Game files are missing from {game}: {", ".join(missing[:3])}{more}. Copy your '
            'CUSA03173 dump (eboot.bin, sce_module, sce_sys, dvdroot_ps4) into that folder again, '
            'or reinstall it there.')


def main(argv):
    """game_check.py GAME_DIR: every .dcx file of the game, those that do not unpack listed."""
    if len(argv) != 2:
        print('Usage: game_check.py GAME_DIR', file=sys.stderr)
        return 2
    game = Path(argv[1])
    files = sorted((game / 'dvdroot_ps4').rglob('*.dcx'))
    broken = []
    for number, path in enumerate(files, 1):
        if readable_and_broken(path):
            broken.append(path)
            print(f'damaged: {path.relative_to(game).as_posix()}')
        if number % 1000 == 0:
            print(f'{number} of {len(files)} checked', file=sys.stderr)
    print(f'{len(broken)} of {len(files)} .dcx files do not unpack')
    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
