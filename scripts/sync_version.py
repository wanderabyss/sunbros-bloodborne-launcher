#!/usr/bin/env python3
"""sync_version.py

Reads the latest release entry from Release_Notes.md and syncs it
to the project version in pyproject.toml (and uv.lock).

- Updates pyproject.toml and re-stages it into the SAME commit.
- Supports --check flag for pre-push and CI validation gates.
- Idempotent: exits 0 immediately when already in sync.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import re
import sys
import tomllib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def get_repo_root() -> Path:
    current = Path(__file__).resolve().parent.parent
    if (current / "pyproject.toml").is_file():
        return current
    return Path.cwd()


def find_release_notes(root: Path) -> Path:
    candidates = [
        root / "Release_Notes.md",
        root / "custom" / "docs" / "Release_Notes.md",
        root / "md" / "Release_Notes.md",
        root / "RELEASE_NOTES.md",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return root / "Release_Notes.md"


def extract_latest_version(release_notes_path: Path) -> str | None:
    if not release_notes_path.is_file():
        return None
    content = release_notes_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        # Skip empty lines, unreleased headers, and non-version headers
        if not line.startswith("## ") or "Unreleased" in line:
            continue
        # Matches formats:
        # ## [1.0.261001.204003] — 2026-10-01
        # ## [3.0.0+build261025.184108] — 2026-10-25
        # ## [1.1.0] — 2026-10-01
        # ## Version 1.1.0
        # ## 1.1.0
        match = re.search(r"##\s+(?:\[|Version\s+)?([0-9]+(?:\.[0-9]+)+(?:\+[0-9a-zA-Z.]+)?)(?:\]|\s|$)", line)
        if match:
            return match.group(1)
    return None


def read_project_version(pyproject_path: Path) -> str | None:
    if not pyproject_path.is_file():
        return None
    content = pyproject_path.read_text(encoding="utf-8")
    data = tomllib.loads(content)
    return data.get("project", {}).get("version")


def sync_version(root: Path, check_only: bool = False, auto_promote: bool = True) -> int:
    rel_notes_path = find_release_notes(root)
    pyproject_path = root / "pyproject.toml"

    current = read_project_version(pyproject_path)
    if not current:
        print(f"sync_version: [ERROR] could not read project.version from {pyproject_path.name}", file=sys.stderr)
        return 1

    if not rel_notes_path.is_file():
        if check_only:
            print(
                f"sync_version: [ERROR] {rel_notes_path.name} not found. Run 'python scripts/bump_build_number.py' to generate it.",
                file=sys.stderr,
            )
            return 1
        today_str = datetime.now().strftime("%Y-%m-%d")
        initial_content = (
            f"# Release Notes\n\n"
            f"## [{current}] — {today_str}\n"
            f"### Initial Release\n\n"
            f"- Synchronized version {current}\n\n---\n"
        )
        rel_notes_path.write_text(initial_content, encoding="utf-8")
        print(f"sync_version: created {rel_notes_path.name} with version [{current}]")
        return 0

    content = rel_notes_path.read_text(encoding="utf-8")
    unreleased_match = re.search(r"(?ms)^## Unreleased\s*\n(.*?)(?=^## |\Z)", content)
    has_unreleased = bool(unreleased_match and unreleased_match.group(1).strip())

    if has_unreleased:
        if check_only:
            print(
                f"sync_version: [ERROR] {rel_notes_path.name} contains unreleased notes under ## Unreleased.\n"
                "               Run 'python scripts/bump_build_number.py' to promote and version them before pushing.",
                file=sys.stderr,
            )
            return 1
        elif auto_promote:
            _repo_root = Path(__file__).resolve().parents[1]
            if str(_repo_root) not in sys.path:
                sys.path.insert(0, str(_repo_root))
            try:
                from scripts.bump_build_number import bump_version, update_release_notes
            except ImportError:
                parent_dir = str(Path(__file__).resolve().parent)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                import importlib
                _mod = importlib.import_module("bump_build_number")
                bump_version = _mod.bump_version
                update_release_notes = _mod.update_release_notes

            new_version = bump_version(current, mode="build")
            print(f"sync_version: auto-promoting ## Unreleased notes -> [{new_version}]")
            update_release_notes(root, new_version, current)

    latest = extract_latest_version(rel_notes_path)
    if not latest:
        print(f"sync_version: [ERROR] could not parse latest version from {rel_notes_path.name}", file=sys.stderr)
        return 1

    clean_ver = latest.split("+")[0]
    has_build = "+" in latest

    # If the latest release in Release_Notes.md lacks a build timestamp (+buildMMDDYY.HHMMSS),
    # generate one and update Release_Notes.md appropriately so build versions are never missing.
    if not has_build and not check_only:
        now_stamp = datetime.now().strftime("%m%d%y.%H%M%S")
        latest_with_build = f"{clean_ver}+build{now_stamp}"
        r_content = rel_notes_path.read_text(encoding="utf-8")
        updated_r, count_r = re.subn(
            rf'(?m)^##\s+\[{re.escape(clean_ver)}\]',
            f"## [{latest_with_build}]",
            r_content,
            count=1,
        )
        if count_r > 0:
            rel_notes_path.write_text(updated_r, encoding="utf-8")
            latest = latest_with_build
            print(f"sync_version: [OK] attached build metadata to Release_Notes.md -> [{latest}]")

    if latest == current:
        print(f"sync_version: [OK] pyproject.toml version already {current}")
        return 0

    if check_only:
        if current.split("+")[0] == clean_ver:
            print(f"sync_version: [OK] base version {clean_ver} matches (project: {current}, release notes: {latest})")
            return 0
        print(
            f"sync_version: [ERROR] out of sync — Release_Notes.md says {latest}, pyproject.toml says {current}",
            file=sys.stderr,
        )
        return 1

    print(f"sync_version: {current} -> {latest}")
    content = pyproject_path.read_text(encoding="utf-8")

    # Replace version in [project] section
    table = re.search(r"(?ms)^\[project\]\s*\n.*?(?=^\[|\Z)", content)
    if not table:
        print("sync_version: [ERROR] cannot locate [project] table in pyproject.toml", file=sys.stderr)
        return 1
    version_regex = re.compile(r'^(version\s*=\s*["\'])([^"\']+)(["\'])', re.MULTILINE)
    updated, count = version_regex.subn(lambda m: m.group(1) + latest + m.group(3), table.group(0))
    if count != 1:
        print("sync_version: [ERROR] expected exactly one version entry in [project]", file=sys.stderr)
        return 1

    new_content = content[: table.start()] + updated + content[table.end() :]
    pyproject_path.write_text(new_content, encoding="utf-8")

    # Synchronize uv.lock if present
    lock_path = root / "uv.lock"
    if lock_path.is_file():
        try:
            lock_content = lock_path.read_text(encoding="utf-8")
            project_name = tomllib.loads(new_content).get("project", {}).get("name", "bloodborne-pc-custom")
            matches = list(re.finditer(r"(?ms)^\[\[package\]\]\n.*?(?=^\[\[package\]\]|\Z)", lock_content))
            for m in matches:
                pkg_data = tomllib.loads(m.group(0)).get("package", [{}])[0]
                if pkg_data.get("name") == project_name and pkg_data.get("source") in ({"editable": "."}, {"virtual": "."}):
                    v_match = re.search(r'(?m)^version = "([^"]+)"', m.group(0))
                    if v_match:
                        s, e = m.start() + v_match.start(1), m.start() + v_match.end(1)
                        lock_content = lock_content[:s] + latest + lock_content[e:]
                        lock_path.write_text(lock_content, encoding="utf-8")
                    break
        except Exception:
            pass

    # Synchronize bloodborne_pc/__init__.py or abac/__init__.py if __version__ is present
    for init_candidate in [root / "bloodborne_pc/__init__.py", root / "abac/__init__.py"]:
        if init_candidate.is_file():
            init_content = init_candidate.read_text(encoding="utf-8")
            if "__version__" in init_content:
                new_init, c = re.subn(
                    rf'(?m)^(__version__\s*=\s*["\']){re.escape(current)}(["\'])',
                    rf"\g<1>{latest}\g<2>",
                    init_content,
                )
                if c > 0:
                    init_candidate.write_text(new_init, encoding="utf-8")

    # Write version.txt files across repository and dist trees
    clean_ver = latest.split("+")[0]
    # bloodborne_pc/version.txt is the copy the launcher reads (bbport_launcher_win._read_version);
    # nothing else in the source tree holds the version.
    for v_target in [
        root / "bloodborne_pc" / "version.txt",
        root / "bloodborne_pc" / "dist" / "bbport-windows" / "version.txt",
        root / "bloodborne_pc" / "dist" / "bbport-windows" / "launcher" / "version.txt",
        root / "bloodborne_pc" / "out" / "stage" / "bbport-windows" / "version.txt",
        root / "bloodborne_pc" / "out" / "stage" / "bbport-windows" / "launcher" / "version.txt",
    ]:
        try:
            if v_target.parent.is_dir():
                v_target.write_text(f"{clean_ver}\n", encoding="utf-8")
        except Exception:
            pass

    print(f"sync_version: [OK] updated pyproject.toml to {latest}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize version from Release_Notes.md to pyproject.toml")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if out of sync, without writing changes",
    )
    parser.add_argument(
        "--stage",
        action="store_true",
        help="git add the files this run changed (the pre-commit hook), and nothing else",
    )
    args = parser.parse_args()
    root = get_repo_root()
    if not args.stage:
        return sync_version(root, check_only=args.check)
    # Stage only what the sync wrote, so a partial commit never picks up unrelated edits.
    owned = [find_release_notes(root), root / "pyproject.toml", root / "uv.lock",
             root / "bloodborne_pc" / "version.txt", root / "bloodborne_pc" / "__init__.py"]
    before = {f: f.read_bytes() if f.is_file() else None for f in owned}
    result = sync_version(root, check_only=args.check)
    changed = [str(f.relative_to(root)) for f in owned if f.is_file() and f.read_bytes() != before[f]]
    if changed:
        import subprocess
        subprocess.run(["git", "add", "--", *changed], cwd=root, check=False)
    return result


if __name__ == "__main__":
    sys.exit(main())
