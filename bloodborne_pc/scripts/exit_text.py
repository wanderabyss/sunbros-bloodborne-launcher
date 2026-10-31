"""Generate desktop-exit wording from the player's message archives; no game files shipped."""
import argparse
import os
from pathlib import Path
from fromsoft import Bnd4, dcx_compress, dcx_decompress
from menu_assets import fmg_read, fmg_write
from patches import game_app_version

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source', type=Path, action='append', default=[])
    args = parser.parse_args()
    target = args.out / 'dvdroot_ps4'
    for old in target.glob('msg/*/menu.msgbnd.dcx'):
        old.unlink()
    if (os.environ.get('BB_EXIT_TO_DESKTOP', '1') == '0' or os.environ.get('BB_ENGINE_HOOKS') == '0'
            or game_app_version(args.game) not in (None, '01.09')):
        return
    count = 0
    root = args.game / 'dvdroot_ps4'
    for source in sorted(root.glob('msg/*/menu.msgbnd.dcx')):
        relative = source.relative_to(root)
        for layer in args.source:
            candidate = layer / 'dvdroot_ps4' / relative
            if candidate.is_file():
                source = candidate
        result = rewrite(source.read_bytes())
        if result:
            dest = target / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(result)
            count += 1
    print(f'Exit wording: Exit to desktop in {count} message archives')


if __name__ == '__main__':
    main()
