"""Save backups: zips of the game's savedata folder in <saves folder>/save-backups.

Each backup is <YYYYMMDD-HHMMSS>[ - label].zip holding savedata/... and manifest.json (when,
kind, label, characters, file count and size). Kinds: 'manual' (Back up now, never pruned),
'auto' (after playing, the newest KEEP_AUTO kept) and 'safety' (made before a restore, never
pruned). Nothing here knows whether the game runs: the launcher refuses while it does.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import time
import zipfile
import zlib

BACKUPS_FOLDER = 'save-backups'
SAVES_FOLDER = 'savedata'
MANIFEST = 'manifest.json'
KEEP_AUTO = 10
KINDS = ('manual', 'auto', 'safety')


class BackupError(Exception):
    pass


def savedata_dir(user_dir):
    return Path(user_dir) / SAVES_FOLDER


def backups_dir(user_dir):
    return Path(user_dir) / BACKUPS_FOLDER


def _files(folder):
    return sorted(p for p in Path(folder).rglob('*') if p.is_file())


def folder_stats(folder):
    """(file count, total bytes) of FOLDER; (0, 0) when it is missing."""
    files = _files(folder) if Path(folder).is_dir() else []
    return len(files), sum(p.stat().st_size for p in files)


def _clean_label(label):
    label = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', str(label or '')).strip(' .')
    return re.sub(r'\s+', ' ', label)[:60]


def create_backup(user_dir, label='', kind='manual', summary='', now=None):
    """Zips <user_dir>/savedata into save-backups; returns the new backup's info (list_backups).
    Written to a temporary name first and renamed, so a failed backup leaves no zip behind."""
    if kind not in KINDS:
        raise BackupError(f'Unknown backup kind {kind!r}.')
    source = savedata_dir(user_dir)
    files = _files(source) if source.is_dir() else []
    if not files:
        raise BackupError(f'No saves to back up in {source}.')
    stamp = now or datetime.now()
    label = _clean_label(label)
    base = stamp.strftime('%Y%m%d-%H%M%S') + (f' - {label}' if label else '')
    folder = backups_dir(user_dir)
    folder.mkdir(parents=True, exist_ok=True)
    target, n = folder / f'{base}.zip', 2
    while target.exists():
        target, n = folder / f'{base} ({n}).zip', n + 1
    manifest = {
        'version': 1, 'created': stamp.isoformat(timespec='seconds'), 'kind': kind, 'label': label,
        'summary': summary or '', 'files': len(files), 'bytes': sum(p.stat().st_size for p in files),
    }
    temp = folder / f'.{target.name}.part'
    try:
        with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in files:
                archive.write(path, f'{SAVES_FOLDER}/{path.relative_to(source).as_posix()}')
            archive.writestr(MANIFEST, json.dumps(manifest, indent=2))
        os.replace(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return _info(target)


def _read_manifest(path):
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read(MANIFEST).decode('utf-8'))


def _info(path):
    path = Path(path)
    try:
        manifest = _read_manifest(path)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        manifest = None
    if not isinstance(manifest, dict):
        manifest = None
    stat = path.stat()
    info = {
        'name': path.name, 'path': str(path), 'zipBytes': stat.st_size, 'modified': stat.st_mtime_ns, 'valid': manifest is not None,
        'created': '', 'kind': 'manual', 'label': '', 'summary': '', 'files': 0, 'bytes': 0,
    }
    if manifest:
        info.update({key: manifest.get(key, info[key]) for key in ('created', 'kind', 'label', 'summary', 'files', 'bytes')})
    if not info['created']:
        info['created'] = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds')
    try:
        info['created'] = str(info['created'])
        info['date'] = datetime.fromisoformat(info['created']).strftime('%Y-%m-%d %H:%M')
    except ValueError:
        info['date'] = info['created']
    info['size'] = human_size(info['zipBytes'])
    return info


def human_size(size):
    for unit in ('B', 'KB', 'MB'):
        if size < 1024 or unit == 'MB':
            return f'{size:.0f} {unit}' if unit == 'B' else f'{size:.1f} {unit}'
        size /= 1024
    return f'{size:.1f} GB'


def list_backups(user_dir):
    """The backups, newest first."""
    folder = backups_dir(user_dir)
    if not folder.is_dir():
        return []
    found = [_info(p) for p in folder.glob('*.zip') if p.is_file() and not p.name.startswith('.')]
    return sorted(found, key=lambda info: (info['created'], info['modified'], info['name']), reverse=True)


def _backup_path(user_dir, name):
    """NAME as a backup in this saves folder; refuses paths and anything that is not a zip there."""
    if not name or Path(name).name != name or not name.endswith('.zip') or name.startswith('.'):
        raise BackupError(f'Not a backup name: {name!r}.')
    path = backups_dir(user_dir) / name
    if not path.is_file():
        raise BackupError(f'Backup {name} no longer exists.')
    return path


def delete_backup(user_dir, name):
    _backup_path(user_dir, name).unlink()


def prune_auto(user_dir, keep=KEEP_AUTO):
    """Deletes all but the newest KEEP automatic backups; returns the names deleted."""
    autos = [info for info in list_backups(user_dir) if info['kind'] == 'auto']
    removed = []
    for info in autos[keep:]:
        try:
            Path(info['path']).unlink()
            removed.append(info['name'])
        except OSError:
            pass
    return removed


def _extract(archive, target):
    """The archive's savedata/ entries into TARGET (no entry may leave it)."""
    root = target.resolve()
    for entry in archive.infolist():
        if entry.is_dir() or not entry.filename.startswith(SAVES_FOLDER + '/'):
            continue
        relative = entry.filename[len(SAVES_FOLDER) + 1:]
        destination = (target / relative).resolve()
        if root not in destination.parents:
            raise BackupError(f'Unsafe path in the backup: {entry.filename}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(entry) as src, open(destination, 'wb') as dst:
            shutil.copyfileobj(src, dst)


def _check(folder, manifest):
    count, size = folder_stats(folder)
    if (count, size) != (manifest.get('files'), manifest.get('bytes')):
        raise BackupError(f'Restored saves do not match the backup: {count} files / {size} bytes, '
                          f"expected {manifest.get('files')} / {manifest.get('bytes')}.")


def _remove(path):
    if path.exists():
        shutil.rmtree(path)


def restore_backup(user_dir, name, summary='', _after_swap=None):
    """Replaces <user_dir>/savedata with backup NAME. The current saves are backed up first
    ('before restore', kind 'safety'); the backup is unpacked beside savedata and checked, then
    swapped in. On any failure the previous saves are put back (from the moved folder, or from
    the safety backup). Returns the safety backup's info (None when there were no saves)."""
    path = _backup_path(user_dir, name)
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise BackupError(f'Backup {name} is damaged.')
            manifest = json.loads(archive.read(MANIFEST).decode('utf-8'))
    except (KeyError, ValueError, zipfile.BadZipFile, zlib.error) as error:
        raise BackupError(f'Backup {name} cannot be read: {error}') from error
    live = savedata_dir(user_dir)
    safety = None
    if folder_stats(live)[0]:
        safety = create_backup(user_dir, 'before restore', 'safety', summary)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    incoming = live.with_name(f'{SAVES_FOLDER}.restoring-{stamp}')
    previous = live.with_name(f'{SAVES_FOLDER}.previous-{stamp}')
    _remove(incoming)
    try:
        with zipfile.ZipFile(path) as archive:
            _extract(archive, incoming)
        _check(incoming, manifest)
    except BaseException:
        shutil.rmtree(incoming, ignore_errors=True)
        raise  # the live saves were not touched
    moved = swapped = False
    try:
        if live.exists():
            os.replace(live, previous)
            moved = True
        os.replace(incoming, live)
        swapped = True
        if _after_swap:
            _after_swap(live)
        _check(live, manifest)
    except BaseException as error:
        shutil.rmtree(incoming, ignore_errors=True)
        if moved or swapped:
            _roll_back(live, previous if moved else None, safety)
        raise BackupError(f'Restore failed, your previous saves were put back: {error}') from error
    shutil.rmtree(previous, ignore_errors=True)
    return safety


def _roll_back(live, previous, safety):
    """Puts the saves from before the restore back in LIVE."""
    try:
        _remove(live)
        if previous is not None:
            os.replace(previous, live)
        return  # (no previous: there were no saves before)
    except OSError:
        pass
    # The moved folder could not come back: unpack the safety backup instead.
    if safety is not None:
        shutil.rmtree(live, ignore_errors=True)
        with zipfile.ZipFile(safety['path']) as archive:
            _extract(archive, live)


def character_summary(characters, limit=3):
    """'Name Lv 40, Other Lv 12' from bbport_character.get_characters' dicts."""
    parts = []
    for char in characters[:limit]:
        name = str(char.get('name') or 'Hunter')
        level = char.get('level')
        parts.append(f'{name} Lv {level}' if level else name)
    more = len(characters) - limit
    return ', '.join(parts) + (f' (+{more})' if more > 0 else '')
