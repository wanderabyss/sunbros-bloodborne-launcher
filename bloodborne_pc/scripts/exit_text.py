"""Generate desktop-exit wording from the player's message archives; no game files shipped."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from fromsoft import Bnd4, dcx_compress, dcx_decompress
from menu_assets import fmg_read, fmg_write
from patches import game_app_version

STAMP = 'stamp.json'  # beside dvdroot_ps4, so never a game file (mods.mod_files)
REPLACEMENTS = {200: {110004: 'Exit to desktop'},
                201: {110004: 'Save your progress and exit to desktop.'},
                204: {110000: 'Save your progress and exit to desktop?'}}


def rewrite(packed):
    archive = Bnd4(dcx_decompress(packed))
    changed = False
    for i, group in enumerate(archive.ids):
        if group not in REPLACEMENTS:
            continue
        messages = fmg_read(archive.files[i])
        for key, text in REPLACEMENTS[group].items():
            # Only replace existing entries. No new command or menu section is introduced.
            if key in messages:
                messages[key] = text.encode('utf-16-le')
                changed = True
        archive.files[i] = fmg_write(messages)
    return dcx_compress(archive.to_bytes(), template=packed) if changed else None


def identity():
    """What the rewritten files depend on besides their sources: these scripts."""
    here = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in (Path(__file__).name, 'fromsoft.py', 'menu_assets.py'):
        try:
            digest.update((here / name).read_bytes())
        except OSError:
            pass
    return digest.hexdigest()[:16]


def remove_made(out):
    """The files an earlier run wrote, and the stamp that vouches for them."""
    (out / STAMP).unlink(missing_ok=True)
    for old in (out / 'dvdroot_ps4').glob('msg/*/menu.msgbnd.dcx'):
        old.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source', type=Path, action='append', default=[])
    args = parser.parse_args()
    target = args.out / 'dvdroot_ps4'
    if (os.environ.get('BB_EXIT_TO_DESKTOP', '1') == '0' or os.environ.get('BB_ENGINE_HOOKS') == '0'
            or game_app_version(args.game) not in (None, '01.09')):
        remove_made(args.out)
        return
    root = args.game / 'dvdroot_ps4'
    sources = []
    for source in sorted(root.glob('msg/*/menu.msgbnd.dcx')):
        relative = source.relative_to(root)
        for layer in args.source:
            candidate = layer / 'dvdroot_ps4' / relative
            if candidate.is_file():
                source = candidate
        sources.append((relative, source))
    # Unpacking and packing the 22 archives again took 5.3 s of every start (2026-11-06).
    wanted = [identity(), *(f'{relative.as_posix()}\t{source}\t{source.stat().st_size}\t{source.stat().st_mtime_ns}'
                            for relative, source in sources)]
    try:
        stamp = json.loads((args.out / STAMP).read_text(encoding='utf-8'))
        if stamp['sources'] == wanted and all((target / name).is_file() for name in stamp['made']):
            print(f'Exit wording: Exit to desktop in {len(stamp["made"])} message archives (up to date)')
            return
    except (OSError, ValueError, KeyError, TypeError):
        pass
    remove_made(args.out)
    made = []
    for relative, source in sources:
        result = rewrite(source.read_bytes())
        if result:
            dest = target / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(result)
            made.append(relative.as_posix())
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / STAMP).write_text(json.dumps({'sources': wanted, 'made': made}, indent=0), encoding='utf-8')
    print(f'Exit wording: Exit to desktop in {len(made)} message archives')


if __name__ == '__main__':
    main()
