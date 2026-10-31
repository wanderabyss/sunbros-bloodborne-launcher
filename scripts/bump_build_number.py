#!/usr/bin/env python3
"""Automatically bump version, update Release_Notes.md, and sync pyproject.toml.

Supports semantic patch/minor increments, datetime build numbers,
and explicit version overrides.

Usage:
    python scripts/bump_build_number.py [--patch] [--minor] [--version <ver>] [--dry-run]
    python scripts/bump_build_number.py --check
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys
import tomllib

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from scripts.sync_version import find_release_notes, sync_version
except ImportError:
    parent_dir = str(Path(__file__).resolve().parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    import importlib
    _mod = importlib.import_module("sync_version")
    find_release_notes = _mod.find_release_notes
    sync_version = _mod.sync_version


def get_repo_root() -> Path:
    current = Path(__file__).resolve().parent.parent
    if (current / "pyproject.toml").is_file():
        return current
    return Path.cwd()


def bump_version(
    current: str,
    mode: str = "build",
    explicit: str | None = None,
    stamp_format: str = "%m%d%y.%H%M%S",
    include_build_tag: bool = True,
) -> str:
    """Compute new version string according to project convention (major.minor.patch+buildMMDDYY.HHMMSS)."""
    now_stamp = datetime.now().strftime(stamp_format)

    if explicit:
        val = explicit.strip()
        if include_build_tag and "+" not in val:
            return f"{val}+build{now_stamp}"
        return val

    base = current.split("+")[0]
    parts = base.split(".")
    while len(parts) < 3:
        parts.append("0")

    major = int(parts[0]) if parts[0].isdigit() else 1
    minor = int(parts[1]) if parts[1].isdigit() else 0
    patch = int(parts[2]) if parts[2].isdigit() else 0

    if mode == "major":
        new_base = f"{major + 1}.0.0"
    elif mode == "minor":
        new_base = f"{major}.{minor + 1}.0"
    elif mode == "patch":
        new_base = f"{major}.{minor}.{patch + 1}"
    elif mode == "build":
        new_base = f"{major}.{minor}.{patch}"
    else:
        new_base = f"{major}.{minor}.{patch}"

    if include_build_tag:
        return f"{new_base}+build{now_stamp}"
    return new_base


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def update_release_notes(root: Path, new_version: str, old_version: str) -> bool:
    """Promote ## Unreleased to ## [new_version] or prepend a new section."""
    rel_notes_path = find_release_notes(root)
    content = rel_notes_path.read_text(encoding="utf-8") if rel_notes_path.exists() else "# Release Notes\n\n## Unreleased\n"
    if f"## [{new_version}]" in content:
        return False

    today_str = datetime.now().strftime("%Y-%m-%d")

    # If ## Unreleased exists and has content, promote it
    unreleased_match = re.search(r"(?ms)^## Unreleased\s*\n(.*?)(?=^## |\Z)", content)
    curated_content = ""
    if unreleased_match:
        curated_content = unreleased_match.group(1).strip()

    if not curated_content:
        # Collect recent commits since previous release
        commits: list[str] = []
        try:
            history = git(root, "log", "-5", "--pretty=format:%h %s")
            for line in history.splitlines():
                if " " in line:
                    h, m = line.split(" ", 1)
                    if not m.startswith("chore(release):") and not m.startswith("Merge"):
                        commits.append(f"- {m} (`{h}`)")
        except Exception:
            pass

        bullets = "\n".join(commits) if commits else "- Routine maintenance and verification updates"
        curated_content = f"### Automated Build Release\n\n{bullets}"

    new_section = f"## [{new_version}] — {today_str}\n{curated_content}\n\n---\n"

    if unreleased_match:
        start = unreleased_match.start()
        end = unreleased_match.end()
        new_content = content[:start] + new_section + "\n" + content[end:].lstrip()
    else:
        if content.startswith("# Release Notes"):
            prefix, sep, rest = content.partition("\n\n")
            new_content = prefix + "\n\n" + new_section + "\n" + rest.lstrip()
        else:
            new_content = "# Release Notes\n\n" + new_section + "\n" + content

    rel_notes_path.write_text(new_content, encoding="utf-8")
    print(f"Updated {rel_notes_path.name} with release [{new_version}]")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump version in pyproject.toml and Release_Notes.md")
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Explicit version string to set",
    )
    parser.add_argument(
        "--major",
        action="store_true",
        help="Increment semantic major version (e.g. 3.2.1 -> 4.0.0)",
    )
    parser.add_argument(
        "--minor",
        action="store_true",
        help="Increment semantic minor version (e.g. 3.2.1 -> 3.3.0)",
    )
    parser.add_argument(
        "--patch",
        action="store_true",
        help="Increment semantic patch version (e.g. 3.2.0 -> 3.2.1)",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Bump build timestamp metadata only",
    )
    parser.add_argument(
        "--format",
        choices=["mmddyy", "yymmdd"],
        default="mmddyy",
        help="Build timestamp date format: mmddyy (MMDDYY.HHMMSS) or yymmdd (YYMMDD.HHMMSS)",
    )
    parser.add_argument(
        "--no-build-tag",
        action="store_true",
        help="Omit +build timestamp suffix (bare semver)",
    )
    parser.add_argument(
        "--dist",
        "--build-dist",
        action="store_true",
        dest="build_dist",
        help="Automatically trigger scripts/build_dist.py to build versioned distribution archives",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if Release_Notes.md and pyproject.toml are synchronized",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Stage and commit changes after bumping",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print updated version without modifying files",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Real-time release note generation and version staging during git commit",
    )
    parser.add_argument(
        "--pre-push",
        action="store_true",
        help="Deprecated: pre-push release creation is disabled; version sync belongs in pre-commit",
    )
    args = parser.parse_args()

    root = get_repo_root()

    if args.pre_push:
        print("[bump_version] Note: pre-push release creation is deprecated. Version sync runs in pre-commit.")
        return 0

    if args.check:
        return sync_version(root, check_only=True)

    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found.", file=sys.stderr)
        return 1

    content = pyproject_path.read_text(encoding="utf-8")
    project = tomllib.loads(content)["project"]
    old_version = project["version"]

    if args.major:
        mode = "major"
    elif args.minor:
        mode = "minor"
    elif args.patch:
        mode = "patch"
    else:
        mode = "build"

    stamp_fmt = "%m%d%y.%H%M%S" if args.format == "mmddyy" else "%y%m%d.%H%M%S"
    new_version = bump_version(
        old_version,
        mode=mode,
        explicit=args.version,
        stamp_format=stamp_fmt,
        include_build_tag=not args.no_build_tag,
    )

    print(f"Bumping version: {old_version} -> {new_version}")
    if args.dry_run:
        print("Dry run: no files modified.")
        return 0

    # Update Release_Notes.md first
    update_release_notes(root, new_version, old_version)

    # Sync pyproject.toml and targets to match
    sync_version(root)

    # Automatically build distribution packages if requested
    if args.build_dist:
        print("\n[bump_version] Automatically building clean versioned distribution package...")
        build_dist_py = root / "scripts" / "build_dist.py"
        code = subprocess.run([sys.executable, str(build_dist_py), "--rebuild"], cwd=root).returncode
        if code != 0:
            print(f"[bump_version] [WARNING] build_dist.py exited with code {code}", file=sys.stderr)
        else:
            print("[bump_version] [SUCCESS] Versioned distribution archives created automatically!")

    if args.commit:
        rel_notes = find_release_notes(root)
        rel_notes_rel = rel_notes.relative_to(root).as_posix()
        to_stage = [rel_notes_rel, "pyproject.toml"]
        if (root / "uv.lock").exists():
            to_stage.append("uv.lock")
        git(root, "add", *to_stage)
        commit_msg = f"chore(release): bump version to {new_version}"
        git(root, "commit", "-m", commit_msg, "--", *to_stage)
        print(f"Committed: {commit_msg}")
    elif args.auto:
        rel_notes = find_release_notes(root)
        rel_notes_rel = rel_notes.relative_to(root).as_posix()
        to_stage = [rel_notes_rel, "pyproject.toml"]
        if (root / "uv.lock").exists():
            to_stage.append("uv.lock")
        git(root, "add", *to_stage)
        print(f"[bump_version] Real-time release notes & version updated for [{new_version}]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
