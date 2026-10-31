#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build the HD Texture Pack from the downloaded texture mods (plans/pc-enhancements.md B4).

    python hd_texture_pack.py --game <folder with dvdroot_ps4> --sources <folder with the zips>
        --out <mods folder> [--name "HD Texture Pack"] [--dry-run] [--progress]

The mods are read straight out of their zips (nothing is extracted, nothing from them is run),
every file goes through picture_gate, and the result is one mod folder of picture files:
<out>/<name>/dvdroot_ps4/... with a pack.json that lists where everything came from.

Map texture archives are merged texture by texture: the game's archive, then each source's
textures that differ from the game's, later sources winning (hd_pack_sources.json gives the
order). The sky mod ships whole archives in which most textures are the game's own; only its
changed ones replace the world mod's. Armour and effect containers keep the game's own models
and effect definitions (picture_gate.check_container).

--progress prints one JSON line per step on stdout for the launcher's progress bar:
{"stage": ..., "done": <bytes>, "total": <bytes>, "file": ...}; the report goes to stderr.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
# Also when started isolated (python -I), as the launcher does for files from downloads.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import fromsoft  # noqa: E402
import picture_gate  # noqa: E402

SOURCES = HERE / 'hd_pack_sources.json'
PACK_NAME = 'HD Texture Pack'
PACK_VERSION = '1.0'
GAME_FOLDERS = {'action', 'chr', 'event', 'facegen', 'font', 'map', 'menu', 'movie', 'msg', 'mtd',
                'obj', 'other', 'param', 'paramdef', 'parts', 'remo', 'script', 'sfx', 'shader',
                'sound'}
CHUNK = 1 << 22


class Progress:
    """Progress lines for the launcher (stdout, JSON) and the report (stderr)."""

    def __init__(self, enabled, total=0):
        self.enabled, self.total, self.done = enabled, total, 0
        self.stage = ''

    def step(self, stage=None, file=None, add=0):
        self.done += add
        if stage:
            self.stage = stage
        if self.enabled:
            print(json.dumps({'stage': self.stage, 'done': self.done, 'total': self.total,
                              'file': file}), flush=True)

    @staticmethod
    def log(message):
        print(message, file=sys.stderr, flush=True)


def game_path(member):
    """'map/m21/m21_0000.tpfbhd' for a zip member under any wrapper folders, or None."""
    parts = member.replace('\\', '/').split('/')
    lowered = [p.casefold() for p in parts]
    if 'dvdroot_ps4' in lowered:
        rest = parts[lowered.index('dvdroot_ps4') + 1:]
        return '/'.join(rest) if rest else None
    for at, part in enumerate(lowered[:-1]):
        if part in GAME_FOLDERS:
            return '/'.join(parts[at:])
    return None


def find(root, relative):
    """`relative` under `root`, matching each part case-insensitively (None if absent)."""
    path = Path(root)
    for part in relative.split('/'):
        if not path.is_dir():
            return None
        wanted = part.casefold()
        match = next((e for e in path.iterdir() if e.name.casefold() == wanted), None)
        if match is None:
            return None
        path = match
    return path


def sha256(path, progress=None):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
            if progress:
                progress.done += len(chunk)
    return digest.hexdigest()


def nexus_page(source):
    """The source's file on Nexus Mods, where the player presses Manual Download."""
    return f'https://www.nexusmods.com/bloodborne/mods/{source["mod"]}?tab=files&file_id={source["file_id"]}'


def is_download(source, name):
    """Whether a file name is the source's Nexus download: "<download>-<mod>-<version>-<time>.zip"."""
    return re.match(re.escape(source['download']) + rf'-{source["mod"]}-.*\.zip$', name, re.I) is not None


def load_sources(folder, listing=SOURCES, include=()):
    """[(source, zip path)] in pack order, for the sources whose zip is in `folder`, and the
    names of those missing. A source marked "default": false is used only when its id is in
    `include`."""
    sources = json.loads(Path(listing).read_text(encoding='utf-8'))['sources']
    zips = sorted(Path(folder).glob('*.zip'))
    found, missing = [], []
    for source in sources:
        if source.get('default', True) is False and source['id'] not in include:
            continue
        match = [z for z in zips if is_download(source, z.name)]
        if match:
            # A file downloaded twice (Windows adds _2): the newest one.
            found.append((source, max(match, key=lambda z: z.stat().st_mtime)))
        else:
            missing.append(source['id'])
    return found, missing


def plan(found, dvdroot):
    """What every source file becomes: {game path: [(source, zip member info, kind)]} in source
    order, and the refused files [(source id, path, reason)]."""
    claims, refused = {}, []
    for source, archive in found:
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                path = game_path(info.filename)
                if path is None:
                    if Path(info.filename).suffix.casefold() not in {'.txt', '.md', '.jpg', '.png', '.pdf', ''}:
                        refused.append((source['id'], info.filename, 'outside the game folders'))
                    continue
                kind, reason = picture_gate.rule(path)
                if kind is None:
                    refused.append((source['id'], path, reason))
                    continue
                game = find(dvdroot, path)
                if game is None:
                    refused.append((source['id'], path, 'not a file the game has (no new files)'))
                    continue
                relative = game.relative_to(dvdroot).as_posix()
                claims.setdefault(relative, []).append((source, archive, info, kind))
    return claims, refused


def copy_stream(src, dst, size):
    left = size
    while left:
        chunk = src.read(min(CHUNK, left))
        if not chunk:
            raise fromsoft.FormatError('archive member is truncated')
        dst.write(chunk)
        left -= len(chunk)


def merge_map(relative, layers, dvdroot, out_root, progress, report):
    """One map texture archive (relative: its .tpfbhd), texture by texture. `layers`: [(source,
    zipfile, bhd info, bdt info)] in pack order, later winning."""
    game_bhd_path = dvdroot / relative
    game_bdt_path = game_bhd_path.with_suffix('.tpfbdt')
    game = fromsoft.Bxf4(game_bhd_path.read_bytes())
    names = game.index()
    owner = [None] * len(game)          # source id that supplies entry i
    placed = [None] * len(game)
    counts = {}
    target_bhd = out_root / relative
    target_bdt = target_bhd.with_suffix('.tpfbdt')
    target_bhd.parent.mkdir(parents=True, exist_ok=True)
    with open(game_bdt_path, 'rb') as game_bdt, open(target_bdt, 'wb') as out:
        out.write(fromsoft.Bxf4.data_header(game_bdt.read(fromsoft.Bxf4.DATA_HEADER_SIZE)))

        def put(i, data, source_id):
            while out.tell() % fromsoft.Bxf4.DATA_ALIGN:
                out.write(b'\0')
            placed[i] = (out.tell(), len(data))
            out.write(data)
            owner[i] = source_id

        # The highest layer first: an entry it changes is taken, and lower layers skip it.
        for source, z, bhd_info, bdt_info in reversed(layers):
            mod_bhd = z.read(bhd_info)
            problems = picture_gate.check_map_header(game_bhd_path.read_bytes(), mod_bhd)
            if problems:
                report['refused'].append({'source': source['id'], 'path': relative,
                                          'reason': '; '.join(problems[:5])})
                progress.step(file=relative, add=bdt_info.compress_size)
                continue
            mod = fromsoft.Bxf4(mod_bhd)
            taken = refused = 0
            with z.open(bdt_info) as stream:
                at = 0
                for j in mod.in_data_order():
                    skip = mod.offsets[j] - at
                    if skip < 0:
                        raise fromsoft.FormatError(f'{relative}: overlapping entries in {source["id"]}')
                    while skip:
                        got = len(stream.read(min(CHUNK, skip)))
                        if not got:
                            raise fromsoft.FormatError(f'{relative}: {source["id"]} data is truncated')
                        skip -= got
                    data = stream.read(mod.sizes[j])
                    at = mod.offsets[j] + len(data)
                    if len(data) != mod.sizes[j]:
                        raise fromsoft.FormatError(f'{relative}: {source["id"]} data is truncated')
                    i = names[mod.names[j].casefold()]
                    if owner[i] is not None:
                        continue
                    if data == (game.read(game_bdt, i) if game.sizes[i] == len(data) else None):
                        continue  # the game's own texture: not a change
                    problem = picture_gate.check_map_entry(game.read(game_bdt, i), data)
                    if problem:
                        refused += 1
                        report['refused'].append({'source': source['id'], 'path': f'{relative}:{mod.names[j]}',
                                                  'reason': problem})
                        continue
                    put(i, data, source['id'])
                    taken += 1
                progress.step(file=relative, add=bdt_info.compress_size)
            counts[source['id']] = taken
            report['sources'][source['id']]['files_accepted'] += taken
            report['sources'][source['id']]['files_refused'] += refused
        # Everything no source changed stays the game's.
        for i in game.in_data_order():
            if owner[i] is None:
                put(i, game.read(game_bdt, i), 'game')
    target_bhd.write_bytes(game.header(placed))
    counts['game'] = owner.count('game')
    report['merged_maps'].append({'path': relative, **{k: v for k, v in counts.items()}})
    report['files'] += 2
    if all(v == 0 for k, v in counts.items() if k != 'game'):
        # Nothing changed after all: leave the game's archive in place.
        target_bhd.unlink()
        target_bdt.unlink()
        report['files'] -= 2
    progress.log(f'{relative}: ' + ', '.join(f'{k} {v}' for k, v in counts.items()))


def take_file(relative, claims, dvdroot, out_root, progress, report):
    """A container or a loose texture: the last source's file that passes the gate."""
    game_bytes = (dvdroot / relative).read_bytes()
    chosen = None
    for source, z, info, kind in claims:
        data = z.read(info)
        verdict = (picture_gate.check_container if kind == 'container' else picture_gate.check_texture)(
            game_bytes, data)
        progress.step(file=relative, add=info.compress_size)
        if verdict.verdict == picture_gate.REFUSE:
            report['refused'].append({'source': source['id'], 'path': relative, 'reason': verdict.reason})
            report['sources'][source['id']]['files_refused'] += 1
            continue
        if chosen:
            progress.log(f'{relative}: {chosen[0]} -> {source["id"]}')
        chosen = (source['id'], verdict)
    if not chosen:
        return
    source_id, verdict = chosen
    report['sources'][source_id]['files_accepted'] += 1
    if verdict.verdict == picture_gate.TEXTURES_ONLY:
        report['rebuilt'].append({'path': relative, 'source': source_id, 'reason': verdict.reason})
    target = out_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(verdict.data)
    report['files'] += 1


def game_running():
    if os.name != 'nt':
        return False
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq bb-probe.exe', '/NH'],
                            capture_output=True, text=True,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return 'bb-probe.exe' in result.stdout.casefold()


def build(game, sources, out, name=PACK_NAME, dry_run=False, show_progress=False, listing=SOURCES, include=()):
    dvdroot = find(game, 'dvdroot_ps4')
    if dvdroot is None:
        raise ValueError(f'{game}: no dvdroot_ps4 (expected the game folder)')
    found, missing = load_sources(sources, listing, include)
    left_out = [s['id'] for s in json.loads(Path(listing).read_text(encoding='utf-8'))['sources']
                if s.get('default', True) is False and s['id'] not in include]
    if not found:
        raise ValueError(f'{sources}: none of the HD Texture Pack downloads')
    total = sum(z.stat().st_size for _, z in found)
    progress = Progress(show_progress, total * 2)
    report = {'name': name, 'pack_version': PACK_VERSION,
              'built': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'picture_only': True,
              'vram_min_mb': 10240, 'sources': {}, 'missing_sources': missing, 'left_out': left_out, 'refused': [], 'rebuilt': [],
              'merged_maps': [], 'files': 0}
    progress.step('checking downloads')
    for source, archive in found:
        digest = sha256(archive, progress)
        progress.step(file=archive.name)
        if source.get('sha256') and digest != source['sha256']:
            progress.log(f'{archive.name}: not the file this pack was made with (updated on Nexus?); '
                         'every file still goes through the picture check')
        report['sources'][source['id']] = {
            'id': source['id'], 'mod': source['title'], 'author': source['author'],
            'nexus': f'https://www.nexusmods.com/bloodborne/mods/{source["mod"]}', 'file': archive.name,
            'sha256': digest, 'files_accepted': 0, 'files_refused': 0}
    claims, refused = plan(found, dvdroot)
    report['refused'] += [{'source': s, 'path': p, 'reason': r} for s, p, r in refused]
    for s, _p, _r in refused:
        report['sources'][s]['files_refused'] += 1
    if dry_run:
        report['planned'] = {path: [c[0]['id'] for c in claim] for path, claim in sorted(claims.items())}
        report['sources'] = list(report['sources'].values())
        return report
    out = Path(out)
    work = out / f'{name}.new'
    if work.exists():
        shutil.rmtree(work)
    out_root = work / 'dvdroot_ps4'
    out_root.mkdir(parents=True)
    zips = {}
    try:
        def opened(archive):
            if archive not in zips:
                zips[archive] = zipfile.ZipFile(archive)
            return zips[archive]

        progress.step('building')
        for relative in sorted(claims):
            claim = claims[relative]
            kind = claim[0][3]
            if kind == 'map':
                if not relative.casefold().endswith('.tpfbhd'):
                    continue  # handled with its header
                data_path = relative[:-len('.tpfbhd')] + '.tpfbdt'
                data_claims = {c[0]['id']: c for c in claims.get(data_path, [])}
                layers = []
                for source, archive, info, _ in claim:
                    if source['id'] not in data_claims:
                        report['refused'].append({'source': source['id'], 'path': relative,
                                                  'reason': 'header without its data file'})
                        continue
                    layers.append((source, opened(archive), info, data_claims[source['id']][2]))
                if layers:
                    merge_map(relative, layers, dvdroot, out_root, progress, report)
            else:
                take_file(relative, [(s, opened(a), i, k) for s, a, i, k in claim], dvdroot, out_root,
                          progress, report)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    finally:
        for z in zips.values():
            z.close()
    report['sources'] = list(report['sources'].values())
    (work / 'pack.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (work / 'README.txt').write_text(readme(report), encoding='utf-8')
    if game_running():
        raise RuntimeError(f'The game is running: close it, then run this again ({work} is kept).')
    final = out / name
    if final.exists():
        shutil.rmtree(final)
    work.rename(final)
    progress.done = progress.total
    progress.step('done', file=str(final))
    return report


def readme(report):
    lines = [f'{report["name"]} {report["pack_version"]} (built {report["built"]})', '',
             'Picture files only: higher-resolution textures for the world, the sky, armour and',
             'effects. No map, enemy, item, event or other game data is changed; every file was',
             'checked by the port\'s picture gate (scripts/picture_gate.py). pack.json lists each',
             'file\'s source and everything that was left out.', '',
             'Switch it on or off on the launcher\'s Graphics page (High-resolution textures).',
             'Keep the port on the same drive as the game: otherwise every start copies the pack.', '',
             'Made from these Nexus Mods downloads (all credit to their authors):']
    for s in report['sources']:
        lines.append(f'- {s["mod"]} by {s["author"]}: {s["nexus"]} ({s["file"]})')
    lines += ['', 'To update: put the new download in the downloads folder and build the pack again',
              '(launcher, or scripts/hd_texture_pack.py).']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--game', required=True, type=Path)
    parser.add_argument('--sources', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--name', default=PACK_NAME)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--progress', action='store_true')
    parser.add_argument('--report', type=Path, help='also write the report here')
    parser.add_argument('--include', action='append', default=[],
                        help='a source left out by default to use anyway (its id, e.g. ARM)')
    args = parser.parse_args()
    report = build(args.game, args.sources, args.out, args.name, args.dry_run, args.progress,
                   include=tuple(args.include))
    text = json.dumps(report, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding='utf-8')
    refused = len(report['refused'])
    print(f'{report["name"]}: {report["files"]} files, {refused} refused'
          + (f'; missing downloads: {", ".join(report["missing_sources"])}' if report['missing_sources'] else ''),
          file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        print(f'HD Texture Pack: {error}', file=sys.stderr)
        sys.exit(1)
