#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""The shader pre-build catalog: which shader permutations and pipelines the game draws, merged
from players' pipeline caches (user/cache/CUSA03173), for every install to translate before
first sight (vk_shader_prebuild.h; run.py passes it as BB_SHADER_CATALOG).

Only the records are kept - a permutation's specialization and resource layout (.meta) and a
pipeline's state (.key) - in the current format. No SPIR-V and no game code: each install
translates the shaders from its own game files.

  shader_catalog.py <catalog folder> <cache folder> [<cache folder> ...] [--exclude <file>] [--vendor <nvidia|amd|...>]
      --exclude: .meta names to leave out (bb-shader-prebuild --rejects: translations that do
      not match the game's own), so those shaders compile while playing as before
      --vendor: subfolder to target (e.g. nvidia, amd) for vendor-partitioned catalogs
  shader_catalog.py --status <cache folder>     how much a play session has recorded
  shader_catalog.py --partition <catalog folder> [--vendor <nvidia|amd>]
      partitions unpartitioned .meta and .key records into vendor subdirectories
"""
from pathlib import Path
import shutil
import struct
import sys

# The versions the game writes (gpu/.../vk_pipeline_serialization.cpp): older records are left.
SHADER_META_VERSION = 8
PIPELINE_KEY_VERSION = 5


def current(path):
    want = SHADER_META_VERSION if path.suffix == '.meta' else PIPELINE_KEY_VERSION
    with path.open('rb') as file:
        head = file.read(4)
    return len(head) == 4 and struct.unpack('<I', head)[0] == want


def merge(catalog, caches, exclude=(), vendor=None):
    exclude = set(exclude)
    catalog = Path(catalog)
    target_dir = catalog / vendor if vendor else catalog
    target_dir.mkdir(parents=True, exist_ok=True)
    added = 0
    for cache in caches:
        for record in sorted(Path(cache).iterdir()):
            if record.suffix not in ('.meta', '.key') or not current(record) or record.name in exclude:
                continue
            target = target_dir / record.name
            if not target.exists():
                shutil.copyfile(record, target)
                added += 1
    total = sum(1 for p in target_dir.iterdir() if p.suffix in ('.meta', '.key'))
    return added, total


def partition(catalog, default_vendor='nvidia'):
    """Partition loose .meta and .key records in catalog into vendor subdirectories."""
    catalog = Path(catalog)
    if not catalog.is_dir():
        return 0
    vendor_dir = catalog / default_vendor
    vendor_dir.mkdir(parents=True, exist_ok=True)
    (catalog / 'amd').mkdir(parents=True, exist_ok=True)
    moved = 0
    for p in list(catalog.iterdir()):
        if p.is_file() and p.suffix in ('.meta', '.key'):
            shutil.move(str(p), str(vendor_dir / p.name))
            moved += 1
    return moved


def status(cache):
    """Current-format records in a cache: shader variants and pipelines seen so far."""
    cache = Path(cache)
    if not cache.is_dir():
        return 0, 0
    records = []
    # If cache has vendor subdirectories, inspect all
    subdirs = [d for d in cache.iterdir() if d.is_dir()]
    if subdirs:
        for d in subdirs:
            records.extend(p for p in d.iterdir() if p.suffix in ('.meta', '.key') and current(p))
    for p in cache.iterdir():
        if p.is_file() and p.suffix in ('.meta', '.key') and current(p):
            records.append(p)
    shaders = sum(p.suffix == '.meta' for p in records)
    return shaders, len(records) - shaders


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == '--status':
        shaders, pipelines = status(sys.argv[2])
        print(f'Recorded so far: {shaders} shader variants, {pipelines} pipelines.')
        return
    if len(sys.argv) >= 3 and sys.argv[1] == '--partition':
        vendor = 'nvidia'
        if '--vendor' in sys.argv:
            at = sys.argv.index('--vendor')
            if at + 1 < len(sys.argv):
                vendor = sys.argv[at + 1]
        moved = partition(sys.argv[2], default_vendor=vendor)
        print(f'shader catalog: partitioned {moved} records into {vendor}/')
        return
    args = sys.argv[1:]
    exclude = ()
    vendor = None
    if '--exclude' in args:
        at = args.index('--exclude')
        exclude = Path(args[at + 1]).read_text(encoding='utf-8').split()
        del args[at:at + 2]
    if '--vendor' in args:
        at = args.index('--vendor')
        vendor = args[at + 1]
        del args[at:at + 2]
    if len(args) < 2:
        sys.exit(__doc__)
    added, total = merge(args[0], args[1:], exclude, vendor=vendor)
    target_name = f"{args[0]}/{vendor}" if vendor else args[0]
    print(f'shader catalog ({target_name}): {added} records added, {total} in total')


if __name__ == '__main__':
    main()
