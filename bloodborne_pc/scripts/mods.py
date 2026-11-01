#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Merge loose-file mods through links, preserving the original game and mod files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import sys
import tempfile
import time

# Top-level folders of the game's dvdroot_ps4: a mod made of these is a dvdroot_ps4 itself.
GAME_FOLDERS = {'action', 'chr', 'event', 'facegen', 'font', 'map', 'menu', 'movie', 'msg', 'mtd',
                'obj', 'other', 'param', 'paramdef', 'parts', 'remo', 'script', 'sfx', 'shader',
                'sound'}


def child(folder, name):
    """`name` inside `folder`, matching an existing entry case-insensitively (mods made on
    Windows often differ from the game's lower-case names)."""
    folder = Path(folder)
    for entry in (folder.iterdir() if folder.is_dir() else ()):
        if entry.name.casefold() == name.casefold():
            return entry
    return folder / name


# Files that come with a mod without being part of it: notes, previews, links, licences.
EXTRA_SUFFIXES = {'', '.txt', '.md', '.ini', '.json', '.pdf', '.rtf', '.nfo', '.url', '.htm', '.html',
                  '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
ARCHIVE_SUFFIXES = {'.zip', '.7z', '.rar'}


def content_root(folder, depth=0):
    """(root, prefix): where a mod's files are and the game path they go to, or None.

    Accepted layouts: <mod>/dvdroot_ps4, <mod>/app0/dvdroot_ps4, <mod>/<serial>/dvdroot_ps4, up to
    three wrapper folders around any of these (archives extracted into a folder of their name,
    beside notes and pictures), and the game's folders without dvdroot_ps4 (<mod>/chr,
    <mod>/parts, ...), also next to other folders (Screenshots, Optional)."""
    folder = Path(folder)
    if not folder.is_dir():
        return None
    # Every retail release (patches.BLOODBORNE_IDS).
    for wrapper in ('', 'app0', 'CUSA03173', 'CUSA00900', 'CUSA00207', 'CUSA00208', 'CUSA00299',
                    'CUSA01363', 'CUSA03179', 'CUSA03014', 'CUSA03023'):
        base = child(folder, wrapper) if wrapper else folder
        dvdroot = child(base, 'dvdroot_ps4')
        if dvdroot.is_dir():
            return base, ''
    entries = [e for e in folder.iterdir() if not e.name.startswith('.')]
    folders = [e for e in entries if e.is_dir()]
    if any(e.name.casefold() in GAME_FOLDERS for e in folders):
        return folder, 'dvdroot_ps4'
    if depth < 3 and len(folders) == 1 and not [e for e in entries if e.is_file() and
                                                e.suffix.casefold() not in EXTRA_SUFFIXES]:
        return content_root(folders[0], depth + 1)
    return None


def problem(folder):
    """Why `folder` is not a mod (content_root is None), for the launcher's list."""
    folder = Path(folder)
    files = [e for e in folder.rglob('*') if e.is_file()][:2000]
    if not files:
        return 'empty'
    if any(e.suffix.casefold() in ARCHIVE_SUFFIXES for e in files):
        return 'still an archive: extract it here'
    folders = [e for e in folder.iterdir() if e.is_dir() and not e.name.startswith('.')]
    if len(folders) > 1:
        return ('several folders: put each mod in its own folder in Mods (each with dvdroot_ps4, '
                'or folders like chr, parts, map)')
    return 'no game files: expected dvdroot_ps4, or folders like chr, parts, map'


def unrecognized(root):
    """(name, problem) of the folders of `root` that are not mods."""
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(((p.name, problem(p)) for p in root.iterdir()
                   if p.is_dir() and not p.name.startswith('.') and not content_root(p)),
                  key=lambda item: (item[0].casefold(), item[0]))


def discover(root):
    """Named mods: folders of `root` with an accepted layout (content_root)."""
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted((p.name for p in root.iterdir() if p.is_dir() and content_root(p)),
                  key=lambda name: (name.casefold(), name))


def selected(root, config):
    available = discover(root)
    if not config or not Path(config).is_file():
        return available
    settings = json.loads(Path(config).read_text(encoding='utf-8'))
    disabled_names = settings.get('disabled', [])
    if not isinstance(disabled_names, list) or not all(isinstance(n, str) for n in disabled_names):
        raise ValueError('Disabled mods must be a list of folder names')
    disabled = set(disabled_names)
    order = settings.get('order', [])
    if not isinstance(order, list) or not all(isinstance(n, str) for n in order):
        raise ValueError('Mod order must be a list of folder names')
    # New folders are enabled automatically and appended in alphabetical order.
    return list(dict.fromkeys(n for n in [*order, *available]
                             if n in available and n not in disabled))


def mod_files(folder):
    """(game path, source) of every file a mod replaces or adds under dvdroot_ps4."""
    layout = content_root(folder)
    if not layout:
        raise ValueError(f'{folder}: expected dvdroot_ps4 (or chr/, parts/, ...) inside the mod folder')
    root, prefix = layout
    root = root.resolve()
    # A pack built as picture files only (hd_texture_pack.py writes pack.json) is checked again
    # here, by path and type, so a file added to it by hand cannot change the game.
    picture_only = False
    try:
        picture_only = json.loads((Path(folder) / 'pack.json').read_text(encoding='utf-8')).get('picture_only') is True
    except (OSError, ValueError, AttributeError):
        pass
    if picture_only:
        import picture_gate
    for directory, folders, files in os.walk(root, followlinks=False):
        directory = Path(directory)
        for name in [*folders, *files]:
            if (directory / name).is_symlink():
                raise ValueError(f'Mod symlinks are unsupported: {directory / name}')
        for name in sorted(files):
            source = directory / name
            if prefix and source.relative_to(root).parts[0].casefold() not in GAME_FOLDERS:
                continue  # notes and folders beside the game's (Screenshots, Optional)
            relative = Path(prefix) / source.relative_to(root) if prefix else source.relative_to(root)
            # Readme/metadata stay outside the mounted game. This loader handles assets;
            # executable patches use the existing patch compiler, with address validation.
            if relative.parts[0].casefold() != 'dvdroot_ps4':
                if relative.parts[0].casefold() in ('eboot.bin', 'sce_module', 'sce_sys'):
                    raise ValueError(f'Executable/system replacement is unsupported: {source}')
                continue
            if not source.is_file():
                raise ValueError(f'Not a regular mod file: {source}')
            if picture_only and not picture_gate.quick(relative.as_posix()):
                print(f'Mods: {Path(folder).name}: {relative.as_posix()} left out (not a picture file)',
                      file=sys.stderr)
                continue
            yield relative, source


# Windows: files are always hard links (copies across volumes), never symlinks. The runtime's
# UCRT _stat64 and FindFirstFileA report a file symlink's own size (0), not its target's, and
# the game panics loading it (FileTransferTask.cpp(865)). Directories are symlinks, or
# junctions without the symlink privilege (Developer Mode off). Hard links and junctions are
# not symlinks, so the overlay remembers what it linked and where to.
#
# A process started with Windows' redirection trust policy (RedirectionGuard; Armoury Crate on
# the ROG Ally starts games this way, and children inherit it) refuses to follow a junction or
# symlink a non-administrator made: ERROR_UNTRUSTED_MOUNT_POINT. The first directory link is
# tried; if it is refused, every directory becomes a real folder of hard-linked files (about
# 6 s for the whole game on an SSD) for the rest of this overlay.
#
# Those real folders are also the first choice whenever the game's files can be hard-linked
# where the overlay is (same NTFS volume). A delete that follows junctions goes through the
# overlay into the game: removing an agent worktree that held a left overlay emptied a whole
# dump except eboot.bin (Oct 2026). Deleting a hard link leaves the game's file in place, so
# junctions are used only where hard links cannot reach.
LINKED = {}
UNTRUSTED_MOUNT_POINT = 448
MIRROR_DIRECTORIES = False


def _directory_link_followed(link):
    try:
        os.listdir(link)
        return True
    except OSError as error:
        if getattr(error, 'winerror', None) == UNTRUSTED_MOUNT_POINT:
            return False
        raise


def _hard_links_reach(game, overlay):
    """Whether the game's files can be hard-linked into `overlay`."""
    sample = next((entry for entry in game.iterdir() if entry.is_file()), None)
    if sample is None:
        return False
    probe = overlay / ('.link-probe-' + sample.name)
    try:
        os.link(sample, probe)
    except OSError:
        return False
    unlink_file(probe, sample)
    return True


def _mirror_directory(link, target):
    link.mkdir()
    for entry in target.iterdir():
        make_link(link / entry.name, entry)


def make_link(link, target):
    global MIRROR_DIRECTORIES
    if os.name != 'nt':
        link.symlink_to(target, target_is_directory=target.is_dir())
        return
    if target.is_dir():
        if MIRROR_DIRECTORIES:
            _mirror_directory(link, target)
            return
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
            LINKED[str(link)] = target
        if _directory_link_followed(link):
            return
        remove_link(link)
        MIRROR_DIRECTORIES = True
        print('Mods: this process may not follow folder links (Windows redirection trust); '
              'copying the folder structure with hard links instead', file=sys.stderr)
        _mirror_directory(link, target)
        return
    else:
        try:
            os.link(target, link)
        except OSError:
            shutil.copy2(target, link)
    LINKED[str(link)] = target


def is_link(path):
    return path.is_symlink() or str(path) in LINKED or (hasattr(path, 'is_junction') and path.is_junction())


def link_target(path):
    return LINKED.get(str(path)) or path.resolve(strict=True)


def remove_link(path):
    if hasattr(path, 'is_junction') and path.is_junction():
        os.rmdir(path)
    else:
        unlink_file(path, LINKED.get(str(path)))
    LINKED.pop(str(path), None)


def unlink_file(path, linked=None):
    """Windows refuses to delete a read-only file (WinError 5), and a hard link shares the
    attribute with the file it links: game files copied from a read-only source keep it. It is
    cleared for the deletion and set again on `linked`, the file that stays. From emurphy04
    (Supermedo/bloodborne_pc PR #77, ba34a3a)."""
    try:
        path.unlink()
        return
    except PermissionError:
        mode = path.stat().st_mode
        if os.name != 'nt' or mode & stat.S_IWRITE:
            raise
    os.chmod(path, mode | stat.S_IWRITE)
    try:
        path.unlink()
    finally:
        rest = path if path.exists() else linked
        if rest is not None and rest.exists():
            os.chmod(rest, mode)


def remove_overlay(overlay, game=None):
    """shutil.rmtree for an overlay, whose read-only links are deleted as remove_link does
    (`game`: the game folder it mirrors, for links made by another run)."""
    def retry(function, path, error):
        path = Path(path)
        if function not in (os.unlink, os.remove) or not path.is_file():
            raise error[1] if isinstance(error, tuple) else error
        linked = LINKED.get(str(path))
        if linked is None and game is not None:
            mirror = Path(game) / path.relative_to(overlay)
            if mirror.is_file() and os.path.samefile(path, mirror):
                linked = mirror
        unlink_file(path, linked)
    if sys.version_info >= (3, 12):
        shutil.rmtree(overlay, onexc=retry)
    else:
        shutil.rmtree(overlay, onerror=retry)
    owner_file(overlay).unlink(missing_ok=True)


# Each overlay has an owner file beside it (<overlay>.owner): the processes using it, one id per
# line (run.py, then the game it starts). run.py removes its overlay when the game ends, but a
# start that is killed (the test scripts' Stop-Process -Force, co-op's taskkill /F) never gets
# there: 183 overlays were left in out/, 54 GB of their own data (about 700 GB as Explorer counts
# the hard links). Every start removes the overlays whose owners are all gone.
OWNER_SUFFIX = '.owner'
# An owner file without an id yet: its overlay is being made.
OWNER_GRACE_SECONDS = 60


def owner_file(overlay):
    return Path(str(overlay) + OWNER_SUFFIX)


def add_overlay_owner(overlay, pid):
    """`pid` uses `overlay` too: it stays while any of its owners runs."""
    with open(owner_file(overlay), 'a', encoding='ascii') as file:
        file.write(f'{pid}\n')


def process_alive(pid):
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not handle:
        return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED: it exists
    try:
        return kernel32.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT: still running
    finally:
        kernel32.CloseHandle(handle)


def overlay_in_use(owner):
    try:
        pids = [int(line) for line in owner.read_text(encoding='ascii').split() if line.isdigit()]
        age = time.time() - owner.stat().st_mtime
    except OSError:
        return True  # another start is removing it
    if not pids:
        return age < OWNER_GRACE_SECONDS
    return any(process_alive(pid) for pid in pids)


def sweep_overlays(folder, game=None):
    """Removes the overlays in `folder` whose owners are gone (OWNER_SUFFIX). One without an owner
    file was made before there were any."""
    folder = Path(folder)
    if not folder.is_dir():
        return
    for path in sorted(folder.glob('mod-game-*')):
        if path.name.endswith(OWNER_SUFFIX):
            # Left alone by run.sh's cleanup, or by a start killed before its folder was made.
            if not Path(str(path)[:-len(OWNER_SUFFIX)]).exists() and not overlay_in_use(path):
                path.unlink(missing_ok=True)
            continue
        owner = owner_file(path)
        if not path.is_dir() or (owner.exists() and overlay_in_use(owner)):
            continue
        try:
            remove_overlay(path, game)
            print(f'Mods: removed {path.name}, left by an earlier start', file=sys.stderr)
        except OSError as error:
            print(f'Mods: {path.name}, left by an earlier start, not removed ({error})', file=sys.stderr)


def new_overlay_folder(out, owner):
    """An empty overlay folder in `out`. Its owner file comes first, so that another start never
    takes it for a left one."""
    while True:
        handle, name = tempfile.mkstemp(prefix='mod-game-', suffix=OWNER_SUFFIX, dir=out)
        try:
            with os.fdopen(handle, 'w', encoding='ascii') as file:
                file.write(f'{owner}\n')
            overlay = Path(name[:-len(OWNER_SUFFIX)])
            overlay.mkdir()
            return overlay
        except FileExistsError:  # an earlier overlay of that name
            os.unlink(name)
        except BaseException:
            os.unlink(name)
            raise


def expand(directory):
    """Materialize one directory level; never write through a directory link."""
    if is_link(directory):
        target = link_target(directory)
        if not target.is_dir():
            raise ValueError(f'File/directory conflict at {directory.name}')
        remove_link(directory)
        directory.mkdir()
        for entry in target.iterdir():
            make_link(directory / entry.name, entry)
    elif directory.exists() and not directory.is_dir():
        raise ValueError(f'File/directory conflict at {directory.name}')
    else:
        directory.mkdir(exist_ok=True)


def build_overlay(game, out, mods, owner_pid=None):
    """The game with `mods` linked over it (a new overlay in `out`, or the game itself without
    any), used by `owner_pid` (this process by default; see OWNER_SUFFIX)."""
    game = Path(game).resolve(strict=True)
    out = Path(out).resolve()
    places = [out]
    if os.name == 'nt':
        if out.drive.casefold() != game.drive.casefold():
            # Hard links only reach files on the same volume: the overlay goes beside the game.
            places.insert(0, game.parent)
        # A drive without links (exFAT, FAT32, some network shares: "Incorrect function") cannot
        # hold the overlay; folder links on another drive still reach the game, and its files are
        # copied (only the folders a mod changes are opened up).
        temp = Path(tempfile.gettempdir()).resolve()
        if temp not in places:
            places.append(temp)
    for place in places:
        sweep_overlays(place, game)
    replacements = []
    owners = {}
    for name, root in mods:
        count = 0
        for relative, source in mod_files(root):
            key = relative.as_posix().casefold()
            if key in owners:
                print(f'Mods: {relative}: {owners[key]} -> {name}', file=sys.stderr)
            owners[key] = name
            replacements.append((relative, source))
            count += 1
        print(f'Mods: {name}: {count} files', file=sys.stderr)
    if not replacements:
        return game
    out.mkdir(parents=True, exist_ok=True)
    for at, place in enumerate(places):
        try:
            return _overlay_at(game, place, replacements, owner_pid or os.getpid())
        except OSError as error:
            if at == len(places) - 1:
                raise
            print(f'Mods: no overlay in {place} ({error}); trying {places[at + 1]}', file=sys.stderr)


def _overlay_at(game, out, replacements, owner_pid):
    global MIRROR_DIRECTORIES
    MIRROR_DIRECTORIES = False
    LINKED.clear()
    overlay = new_overlay_folder(out, owner_pid)
    try:
        MIRROR_DIRECTORIES = os.name == 'nt' and _hard_links_reach(game, overlay)
        for entry in game.iterdir():
            make_link(overlay / entry.name, entry)
        replaced = added = 0
        for relative, source in replacements:
            # Each component takes the game's spelling when it exists in another case.
            parent = overlay
            for part in relative.parts[:-1]:
                parent = child(parent, part)
                expand(parent)
            destination = child(parent, relative.parts[-1])
            if is_link(destination):
                replaced += link_target(destination).is_relative_to(game)
                remove_link(destination)
            elif destination.exists():
                raise ValueError(f'File/directory conflict: {relative}')
            else:
                added += 1
            make_link(destination, source)
        print(f'Mods: {replaced} game files replaced, {added} added', file=sys.stderr)
        return overlay
    except BaseException:
        remove_overlay(overlay, game)
        raise


# The in-game PC menu's layer (enhancements.py) adds its strings to every language's menu text.
# A layer above it with its own copy of that file (a mod that edits menu text, such as Restored
# Change Appearance Feature, or the Brazilian Portuguese text layer) hid them, and the PC rows
# showed message ids instead of names (GitHub issue #48). The strings are added to that copy
# instead, in a layer on top of the others.
PC_MENU_LAYER = 'pc-menu'
PC_MENU_TEXT_LAYER = 'pc-menu-text'
PC_MENU_TEXT_FILE = 'menu.msgbnd.dcx'
PC_MENU_MOVIES = {'optionsetting.gfx', 'title.gfx', 'title_dlc.gfx'}


def pc_menu_text_identity():
    """What the merged files depend on besides their sources: the menu's scripts and strings."""
    here = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in ('menu_assets.py', 'fromsoft.py', 'pc_menu_messages.tsv'):
        try:
            digest.update((here / name).read_bytes())
        except OSError:
            pass
    return f'pc-menu-text 1 {digest.hexdigest()[:16]}'


def keep_pc_menu_text(layers, generated, out):
    """`layers`, with one more on top when a layer above the PC menu's replaces a language's
    menu text: that copy with the PC menu's strings added. A mod replacing one of the movies the
    menu edits is only reported (its sections would have to be rebuilt in the mod's movie)."""
    names = [name for name, _root in layers]
    if PC_MENU_LAYER not in names:
        return layers
    owners = {}  # game path, case-folded -> (game path, file, layer): the last layer wins
    for name, root in layers[names.index(PC_MENU_LAYER) + 1:]:
        for relative, source in mod_files(root):
            parts = [p.casefold() for p in relative.parts]
            if len(parts) == 4 and parts[1] == 'msg' and parts[3] == PC_MENU_TEXT_FILE:
                owners[relative.as_posix().casefold()] = (relative, source, name)
            elif len(parts) == 3 and parts[1] == 'menu' and parts[2] in PC_MENU_MOVIES and \
                    name not in generated:
                print(f'Mods: {name} replaces {relative.as_posix()}, which the in-game PC menu also '
                      'edits; the mod\'s copy is used and the PC menu may be incomplete',
                      file=sys.stderr)
    if not owners:
        return layers
    folder = Path(out) / PC_MENU_TEXT_LAYER
    stamp_file = folder / 'stamp.txt'
    lines = [pc_menu_text_identity()]
    for key in sorted(owners):
        relative, source, _name = owners[key]
        info = source.stat()
        lines.append(f'{relative.as_posix()}\t{source}\t{info.st_size}\t{int(info.st_mtime)}')
    stamp = '\n'.join(lines) + '\n'
    try:
        previous = stamp_file.read_text(encoding='utf-8')
    except OSError:
        previous = None
    made = [line.split('\t', 1)[0] for line in (previous or '').splitlines()[1:]]
    if previous == stamp and made and all((folder / m).is_file() for m in made):
        return [*layers, (PC_MENU_TEXT_LAYER, folder)]
    # Only the files this function wrote go, one by one: nothing here is a link into the game.
    for m in made:
        old = folder / m
        if old.is_file() and not is_link(old):
            old.unlink()
    if stamp_file.is_file():
        stamp_file.unlink()
    import menu_assets
    rows = menu_assets.read_messages()
    lines = lines[:1]
    for key in sorted(owners):
        relative, source, name = owners[key]
        try:
            data = menu_assets.build_menu_messages(source.read_bytes(), rows)
        except (OSError, menu_assets.FormatError, IndexError, struct.error) as error:
            # One that already has the menu's ids was made from the PC menu's own file and works.
            print(f'Mods: {name}\'s {relative.as_posix()} is used as it is ({error}); the PC '
                  'menu\'s rows may show numbers in that language', file=sys.stderr)
            continue
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        info = source.stat()
        lines.append(f'{relative.as_posix()}\t{source}\t{info.st_size}\t{int(info.st_mtime)}')
        print(f'Mods: PC menu strings added to {name}\'s {relative.as_posix()}', file=sys.stderr)
    if len(lines) == 1:
        return layers
    # A file left as it is keeps the stamp from matching, so it is tried (and reported) again.
    stamp_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return [*layers, (PC_MENU_TEXT_LAYER, folder)]


# Sojin Chikage's layer (enhancements.py pc_sojin_chikage) adds rows to the gameparam and names to
# every item text. A player's mod above it with its own copy of either (ShopEdit's gameparam, a
# text mod) would hide the weapons, and a save holding one would not load them. The rows and
# names are added to that copy instead, in a layer on top; the shop rows go to the ranges the
# Bath Messengers' talk script on top opens (ShopEdit's own shop, or the game's five stages).
SOJIN_LAYER = 'sojin-chikage'
SOJIN_MERGE_LAYER = 'sojin-chikage-merge'
SOJIN_PARAM = ('dvdroot_ps4', 'param', 'gameparam', 'gameparam.parambnd.dcx')
SOJIN_TALK = ('dvdroot_ps4', 'script', 'talk', 'm21_00_00_00.talkesdbnd.dcx')
SOJIN_TEXT = 'item.msgbnd.dcx'
SOJIN_OWN = {('dvdroot_ps4', 'chr', 'c0000.anibnd.dcx'), ('dvdroot_ps4', 'parts', 'wp_a_1062.partsbnd.dcx'),
             ('dvdroot_ps4', 'parts', 'wp_a_1062_l.partsbnd.dcx')}


def sojin_identity():
    here = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in [here / 'fromsoft.py', here / 'esd.py', *sorted((here / 'sojin').glob('*.py'))]:
        try:
            digest.update(path.read_bytes())
        except OSError:
            pass
    return f'sojin-merge 1 {digest.hexdigest()[:16]}'


def keep_sojin(layers, game, out):
    """`layers`, with one more on top when a layer above Sojin Chikage's replaces the gameparam,
    the Hunter's Dream talk script or an item text: those files with the weapons added. A mod
    that already has the weapons (the stand-alone Sojin Chikage mod) is used as it is, and one
    replacing the moveset or model files is only reported."""
    names = [name for name, _root in layers]
    if SOJIN_LAYER not in names:
        return layers
    above = layers[names.index(SOJIN_LAYER) + 1:]
    owners = {}   # game path, case-folded -> (game path, file, layer): the last layer wins
    talk = None   # the talk script on top, from any layer
    for name, root in layers:
        for relative, source in mod_files(root):
            parts = tuple(p.casefold() for p in relative.parts)
            if parts == SOJIN_TALK:
                talk = source
            if name == SOJIN_LAYER or (name, root) not in above:
                continue
            if parts == SOJIN_PARAM or (len(parts) == 4 and parts[1] == 'msg' and parts[3] == SOJIN_TEXT):
                owners[relative.as_posix().casefold()] = (relative, source, name)
            elif parts in SOJIN_OWN:
                print(f'Mods: {name} replaces {relative.as_posix()}, which Sojin Chikage also makes; the '
                      'mod\'s copy is used and the weapon may not work', file=sys.stderr)
    if not owners:
        return layers
    talk = talk or Path(game) / Path(*SOJIN_TALK)
    folder = Path(out) / SOJIN_MERGE_LAYER
    stamp_file = folder / 'stamp.txt'
    lines = [sojin_identity()]
    for source in [talk, *(owners[key][1] for key in sorted(owners))]:
        info = source.stat()
        lines.append(f'{source}\t{info.st_size}\t{int(info.st_mtime)}')
    stamp = '\n'.join(lines) + '\n'
    try:
        previous = stamp_file.read_text(encoding='utf-8')
    except OSError:
        previous = None
    if previous == stamp and folder.is_dir():
        return [*layers, (SOJIN_MERGE_LAYER, folder)]
    # Only this function's own files are here: nothing in it is a link into the game.
    if folder.is_dir() and not is_link(folder):
        shutil.rmtree(folder)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from sojin import weapon
    weapon.set_game(Path(game) / 'dvdroot_ps4')
    made = 0
    for key in sorted(owners):
        relative, source, name = owners[key]
        data = source.read_bytes()
        try:
            if relative.name.casefold() == SOJIN_TEXT:
                data = weapon.add_text(data)
            elif weapon.has_weapon(data):
                print(f'Mods: {name} already has Sojin Chikage; its {relative.as_posix()} is used as it is',
                      file=sys.stderr)
                continue
            else:
                data = weapon.add_params(data, talk.read_bytes())
        except (weapon.SojinError, OSError, ValueError, KeyError, IndexError, struct.error) as error:
            print(f'Mods: Sojin Chikage not added to {name}\'s {relative.as_posix()} ({error}); the weapon '
                  'is missing while that mod is on', file=sys.stderr)
            continue
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        made += 1
        print(f'Mods: Sojin Chikage added to {name}\'s {relative.as_posix()}', file=sys.stderr)
    if not made:
        return layers
    stamp_file.write_text(stamp, encoding='utf-8')
    return [*layers, (SOJIN_MERGE_LAYER, folder)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--mods-dir', required=True, type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--enabled', choices=('0', '1'), default='1')
    # Files the port's own features make from the game (PC enhancements, menu assets), each a
    # folder with a dvdroot_ps4 layout. They lie under the player's mods, which still win, and
    # apply with mods off: every feature has its own switch.
    parser.add_argument('--generated', type=Path, action='append', default=[])
    # The HD Texture Pack (scripts/hd_texture_pack.py), kept in its own folder apart from the
    # launcher's so every launcher version finds it. It has its own switch, so it applies with
    # mods off too, and lies under the player's mods, which still win.
    parser.add_argument('--hd-pack', type=Path)
    # The process the overlay lasts for (run.py, run.sh): this script's caller by default.
    parser.add_argument('--owner-pid', type=int, default=os.getppid())
    args = parser.parse_args()
    layers = [(folder.name, folder) for folder in args.generated if content_root(folder)]
    pack = args.hd_pack if args.hd_pack and content_root(args.hd_pack) else None
    if pack:
        layers.append((pack.name, pack))
    if args.enabled == '1':
        # shadPS4's loose overlay convention, beside the original game.
        # Another launcher's overlay there would stop every start, though the player never chose
        # it here: BBLauncher builds it from symlinks into its own Mods-Active folder, or leaves
        # it empty. Such a folder is left out, with what to do.
        legacy = Path(str(args.game.resolve()) + '-mods')
        if legacy.is_dir():
            try:
                for _entry in mod_files(legacy):  # what build_overlay would refuse
                    pass
            except ValueError as error:
                why = ('its files are symlinks (made by another launcher, such as BBLauncher)'
                       if 'symlink' in str(error) else str(error))
                print(f'Mods: {legacy} left out: {why}. Copy the mod itself into the Mods folder '
                      f'to use it here.', file=sys.stderr)
            else:
                layers.append((legacy.name, legacy))
        # A directly selected loose overlay is also accepted.
        if child(args.mods_dir, 'dvdroot_ps4').is_dir():
            layers.append((args.mods_dir.name, args.mods_dir))
        else:
            for name in selected(args.mods_dir, args.config):
                if not (pack and (args.mods_dir / name).resolve() == pack.resolve()):  # once only
                    layers.append((name, args.mods_dir / name))
    generated = {folder.name for folder in args.generated}
    try:
        layers = keep_pc_menu_text(layers, generated, args.out)
    except (OSError, ValueError) as error:
        print(f'Mods: PC menu strings not merged ({error})', file=sys.stderr)
    try:
        layers = keep_sojin(layers, args.game, args.out)
    except (OSError, ValueError) as error:
        print(f'Mods: Sojin Chikage not merged ({error})', file=sys.stderr)
    print(build_overlay(args.game, args.out, layers, args.owner_pid))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, TypeError) as error:
        print(f'Mods: {error}', file=sys.stderr)
        sys.exit(1)
