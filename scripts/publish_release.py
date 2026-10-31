#!/usr/bin/env python3
"""
scripts/publish_release.py
--------------------------
Automates publishing a GitHub Release directly from your local system using the GitHub CLI (`gh`).

Workflow:
1. Extracts the latest release version, subtitle, and markdown body from Release_Notes.md.
2. Locates the pre-built release package zip in bloodborne_pc/dist/.
3. Computes the package SHA-256 checksum and appends an Asset Integrity table to release notes.
4. Verifies git status (on main branch and clean working tree, unless overridden).
5. Creates the git tag (e.g. v3.2.1) and pushes it to GitHub.
6. Publishes the GitHub Release via `gh release create` with the release notes and attaches the zip.

The launcher shows a short changelog when it offers an update: put it in the release's section of
Release_Notes.md as a `<!-- launcher: ... -->` block (a "###" title and a few bullets). GitHub hides
the comment and shows the full notes; without the block the launcher lists each bullet's bold lead-in.

Usage:
    python scripts/publish_release.py
    python scripts/publish_release.py --dry-run
    python scripts/publish_release.py --draft
    python scripts/publish_release.py --tag v3.2.1
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def format_size(num_bytes: float) -> str:
    """Format bytes into human-readable size."""
    size = float(num_bytes)
    for unit in ["B", "KiB", "MiB", "GiB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TiB"


def run_command(cmd: list[str], cwd: Path | None = None, capture_output: bool = True) -> tuple[int, str, str]:
    """Execute a shell command safely."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=capture_output,
        encoding="utf-8",
        errors="replace",
    )
    stdout = proc.stdout.strip() if proc.stdout else ""
    stderr = proc.stderr.strip() if proc.stderr else ""
    return proc.returncode, stdout, stderr


def parse_latest_release_notes(notes_path: Path) -> tuple[str, str, str, str]:
    """
    Parses the topmost release from Release_Notes.md.
    Returns: (raw_version, base_version, title, body_markdown)
    """
    if not notes_path.is_file():
        raise FileNotFoundError(f"Release notes file not found: {notes_path}")

    content = notes_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    start_idx = -1
    raw_version = ""
    date_str = ""

    header_re = re.compile(r"^##\s+\[([0-9a-zA-Z.+_-]+)\](?:\s*—\s*(.*))?$")

    for i, line in enumerate(lines):
        m = header_re.match(line.strip())
        if m and "unreleased" not in m.group(1).lower():
            start_idx = i
            raw_version = m.group(1)
            date_str = m.group(2) or ""
            break

    if start_idx == -1:
        raise ValueError("Could not find any release header (e.g. '## [x.y.z]') in Release_Notes.md")

    # Extract subtitle if available on the next non-empty line (### ...)
    title_line = ""
    body_start_idx = start_idx + 1
    for j in range(start_idx + 1, min(start_idx + 6, len(lines))):
        stripped = lines[j].strip()
        if stripped.startswith("### "):
            title_line = stripped[4:].strip()
            body_start_idx = j + 1
            break
        elif stripped and not stripped.startswith("<!--"):
            break

    # Collect body lines until next '---' or '## '
    body_lines: list[str] = []
    for k in range(body_start_idx, len(lines)):
        line = lines[k]
        stripped = line.strip()
        if stripped == "---" or stripped.startswith("## "):
            break
        body_lines.append(line)

    body_markdown = "\n".join(body_lines).strip()
    base_version = raw_version.split("+")[0]

    return raw_version, base_version, title_line, body_markdown


def find_release_zip(repo_root: Path, base_version: str, raw_version: str) -> Path | None:
    """
    Find matching version-tagged release zip in bloodborne_pc/dist/.
    Strictly ensures the tagged archive (e.g. bbport-windows-v3.2.1.zip) is selected,
    rejecting unzipped directories and canonical unversioned archives.
    """
    dist_dir = repo_root / "bloodborne_pc" / "dist"
    if not dist_dir.is_dir():
        return None

    # Priority 1: Exact versioned zip (e.g., bbport-windows-v3.2.1.zip)
    tagged_candidates = [
        dist_dir / f"bbport-windows-v{base_version}.zip",
        dist_dir / f"bbport-windows-{base_version}.zip",
        dist_dir / f"bbport-windows-v{raw_version}.zip",
    ]

    for c in tagged_candidates:
        if c.is_file() and c.suffix.lower() == ".zip":
            return c

    # Priority 2: If only canonical bbport-windows.zip exists, create the tagged copy
    canonical_zip = dist_dir / "bbport-windows.zip"
    if canonical_zip.is_file() and canonical_zip.suffix.lower() == ".zip":
        target_tagged_zip = dist_dir / f"bbport-windows-v{base_version}.zip"
        print(f"[PACKAGE] Canonical archive found. Creating tagged copy: {target_tagged_zip.name}")
        shutil.copy2(canonical_zip, target_tagged_zip)
        return target_tagged_zip

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish Bloodborne PC release directly to GitHub with release notes and zip asset."
    )
    parser.add_argument("--tag", help="Explicit tag to use (default: v<base_version>)")
    parser.add_argument("--zip", help="Path to custom distribution .zip archive")
    parser.add_argument("--draft", action="store_true", help="Create as a draft release on GitHub")
    parser.add_argument("--prerelease", action="store_true", help="Mark release as a pre-release")
    parser.add_argument("--dry-run", action="store_true", help="Inspect notes, tag, and commands without executing")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow uncommitted local changes")
    parser.add_argument("--allow-branch", action="store_true", help="Allow publishing from a non-main branch")
    parser.add_argument("--skip-tag", action="store_true", help="Skip creating and pushing git tag (use existing tag)")
    parser.add_argument("--attach-source", action="store_true", help="Generate and attach clean source zip (omits custom/ via .gitattributes)")
    args = parser.parse_args()

    repo_root = get_repo_root()
    print("=" * 70)
    print(" Bloodborne PC - Publish Release to GitHub")
    print(f" Repository Root: {repo_root}")
    print("=" * 70)

    # 1. Verify GitHub CLI (gh)
    gh_path = shutil.which("gh")
    if not gh_path:
        print("[ERROR] GitHub CLI (`gh`) is not installed or not in PATH.")
        print("        Install it from https://cli.github.com/ or via winget: winget install GitHub.cli")
        return 1

    code, out, _ = run_command(["gh", "auth", "status"])
    if code != 0:
        print("[ERROR] GitHub CLI is not authenticated. Please run: gh auth login")
        return 1
    print("[OK] GitHub CLI is installed and authenticated.")

    # 2. Check Git Branch & Status
    code, current_branch, _ = run_command(["git", "branch", "--show-current"], cwd=repo_root)
    if current_branch != "main" and not args.allow_branch:
        print(f"[WARNING] You are on branch '{current_branch}', not 'main'.")
        print("          Releases are typically published from 'main' after a PR is merged.")
        print("          To publish from this branch anyway, re-run with --allow-branch.")
        return 1

    if not args.allow_dirty:
        code, status_out, _ = run_command(["git", "status", "--porcelain"], cwd=repo_root)
        if status_out:
            print("[WARNING] Working directory has uncommitted modifications:")
            for line in status_out.splitlines()[:5]:
                print(f"          {line}")
            print("          Commit your changes or pass --allow-dirty to proceed.")
            return 1

    # 3. Parse Release Notes
    notes_file = repo_root / "Release_Notes.md"
    try:
        raw_ver, base_ver, title_line, body_md = parse_latest_release_notes(notes_file)
    except Exception as e:
        print(f"[ERROR] Failed to parse release notes: {e}")
        return 1

    tag = args.tag or f"v{base_ver}"
    # Releases are named by the edition and version; the "###" subtitle heads the notes instead.
    release_title = f"SunBro's Edition: {tag}"

    print(f"[VERSION] Raw: {raw_ver} | Base: {base_ver} | Git Tag: {tag}")
    print(f"[TITLE]   {release_title}")

    # 4. Locate Distribution Zip
    zip_path = Path(args.zip) if args.zip else find_release_zip(repo_root, base_ver, raw_ver)
    if not zip_path or not zip_path.is_file():
        print(f"[ERROR] Release zip archive not found in {repo_root / 'bloodborne_pc' / 'dist'}")
        print("        Build the package first using: .\\scripts\\build_dist.ps1")
        return 1

    zip_size_bytes = zip_path.stat().st_size
    zip_size_str = format_size(zip_size_bytes)
    print(f"[PACKAGE] Found archive: {zip_path.name} ({zip_size_str})")
    print("[SHA256]  Computing integrity checksum...")
    sha256_hash = compute_sha256(zip_path)
    print(f"[SHA256]  {sha256_hash}")

    source_zip_path: Path | None = None
    src_size_str: str = ""
    src_sha256: str = ""
    if args.attach_source:
        dist_dir = repo_root / "bloodborne_pc" / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)
        source_zip_path = dist_dir / f"bbport-source-{tag}.zip"
        print(f"[SOURCE] Generating clean source archive (omitting custom/ via .gitattributes): {source_zip_path.name}")
        code, _, err = run_command(
            ["git", "archive", "--worktree-attributes", f"--prefix=bbport-{tag}/", "--format=zip", "-o", str(source_zip_path), "HEAD"],
            cwd=repo_root,
        )
        if code != 0:
            print(f"[ERROR] Failed to create source archive: {err}")
            return 1
        src_size_str = format_size(source_zip_path.stat().st_size)
        src_sha256 = compute_sha256(source_zip_path)
        print(f"[SOURCE] Created source archive: {source_zip_path.name} ({src_size_str})")
        print(f"[SHA256] {src_sha256}")

    # 5. Assemble Full Release Notes Markdown
    full_notes_md = []
    if title_line:
        full_notes_md.append(f"### {title_line}\n")
    if body_md:
        full_notes_md.append(body_md)
        full_notes_md.append("")

    full_notes_md.append("---")
    full_notes_md.append("### Package Integrity & Verification")
    full_notes_md.append("| Artifact | Size | SHA-256 Checksum |")
    full_notes_md.append("| :--- | :--- | :--- |")
    full_notes_md.append(f"| `{zip_path.name}` | {zip_size_str} | `{sha256_hash}` |")
    if source_zip_path:
        full_notes_md.append(f"| `{source_zip_path.name}` | {src_size_str} | `{src_sha256}` |")
    full_notes_md.append("")
    full_notes_md.append("> Clean standalone distribution for Windows (x86_64). Contains launcher, translation runtime, and shader caches.")

    assembled_notes = "\n".join(full_notes_md)

    if args.dry_run:
        print("\n" + "=" * 30 + " DRY RUN PREVIEW " + "=" * 30)
        print(f"Git Tag:       {tag}")
        print(f"Release Title: {release_title}")
        print(f"Asset File:    {zip_path} ({zip_size_str})")
        print("\nRelease Notes Content:\n" + "-" * 70)
        print(assembled_notes)
        print("-" * 70)
        print("[DRY RUN] Complete. No changes were made.")
        return 0

    # 6. Create & Push Git Tag
    if not args.skip_tag:
        code, tag_check, _ = run_command(["git", "tag", "-l", tag], cwd=repo_root)
        if tag not in tag_check.split():
            print(f"[GIT] Creating annotated tag '{tag}'...")
            code, _, err = run_command(["git", "tag", "-a", tag, "-m", f"Release {tag}: {title_line}"], cwd=repo_root)
            if code != 0:
                print(f"[ERROR] Failed to create git tag: {err}")
                return 1

        print(f"[GIT] Pushing tag '{tag}' to origin...")
        code, _, err = run_command(["git", "push", "origin", tag], cwd=repo_root)
        if code != 0:
            print(f"[WARNING] Failed to push tag (it might already exist on remote): {err}")

    # 7. Publish GitHub Release via `gh release create`
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as tmp_file:
        tmp_file.write(assembled_notes)
        tmp_notes_path = tmp_file.name

    try:
        gh_cmd = [
            "gh", "release", "create", tag,
            str(zip_path),
            "--title", release_title,
            "--notes-file", tmp_notes_path,
        ]
        if source_zip_path:
            gh_cmd.append(str(source_zip_path))
        if args.draft:
            gh_cmd.append("--draft")
        if args.prerelease:
            gh_cmd.append("--prerelease")

        upload_files = [zip_path.name]
        if source_zip_path:
            upload_files.append(source_zip_path.name)
        print(f"\n[UPLOAD] Uploading {', '.join(upload_files)} and publishing release to GitHub...")
        print(f"[EXEC]   gh release create {tag} {' '.join(upload_files)} --title \"{release_title}\"")

        proc = subprocess.run(gh_cmd, cwd=repo_root, text=True)
        if proc.returncode == 0:
            print("\n" + "=" * 70)
            print(" SUCCESS! Release successfully published to GitHub.")
            print("=" * 70)
            return 0
        else:
            print(f"\n[ERROR] gh release create failed with exit code {proc.returncode}")
            return proc.returncode
    finally:
        if os.path.exists(tmp_notes_path):
            try:
                os.remove(tmp_notes_path)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
