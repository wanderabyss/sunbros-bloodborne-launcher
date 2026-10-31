#!/usr/bin/env python3
"""
scripts/build_dist.py
---------------------
Builds dist, generates release .zip archives for bloodborne_pc on Windows,
and extracts the clean .zip to produce a fresh, unzipped dist folder.

Features:
- Detects MSYS2 CLANG64 environment (C:/msys64 or MSYS2_ROOT).
- Compiles binaries with bloodborne_pc/build.sh when they are missing, were built from other
  sources (out/build-stamp.txt against the git state of the engine inputs), or with --rebuild.
- Runs packaging/windows/package.sh to stage files into out/stage/<pkg-name>.
- Always creates standard .zip archives (never .tar) with forward-slash paths.
- Automatically kills any locking processes and deletes previous unzipped dist/<pkg-name> folder.
- Always unzips the fresh .zip into dist/<pkg-name> to guarantee a pristine runtime folder.
- Then copies it to dist/<pkg-name>-dlss5 with the local DLSS 5 kit (custom/scripts/dlss5-setup.ps1);
  the zip and dist/<pkg-name> carry no DLSS 5 files and stay the ones to publish (--no-dlss5 skips it).
- Safety checks: verifies no proprietary game files (*.dcx, *.bdt, *.bhd, eboot.bin, etc.) are included.
- Computes and displays file size and SHA256 checksum of the resulting zip.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

# Prohibited game file patterns (must not be redistributed)
PROHIBITED_EXTENSIONS = {
    ".dcx", ".tpf", ".bnd", ".bdt", ".bhd", ".prx", ".sprx"
}
PROHIBITED_FILENAMES = {
    "eboot.bin", "param.sfo"
}


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def find_msys2_bash(custom_root: str | None = None) -> Path | None:
    """Find MSYS2 bash executable."""
    roots = []
    if custom_root:
        roots.append(Path(custom_root))
    if os.environ.get("MSYS2_ROOT"):
        roots.append(Path(os.environ["MSYS2_ROOT"]))
    roots.extend([
        Path("C:/msys64"),
        Path("D:/msys64"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "msys64"
    ])

    for root in roots:
        bash_path = root / "usr" / "bin" / "bash.exe"
        if bash_path.is_file():
            return bash_path
    return None


def run_msys2_command(bash_exe: Path, command: str, cwd: Path, env_vars: dict | None = None) -> int:
    """Run a command inside MSYS2 CLANG64 environment."""
    msys2_root = bash_exe.parent.parent
    clang_bin = msys2_root / "clang64" / "bin"
    usr_bin = msys2_root / "usr" / "bin"

    env = os.environ.copy()
    env["MSYS2_ROOT"] = str(msys2_root).replace("\\", "/")
    env["MSYSTEM"] = "CLANG64"
    env["CHERE_INVOKING"] = "1"  # Keep current working directory
    # Put clang64 and usr/bin at the front of PATH
    env["PATH"] = f"{clang_bin};{usr_bin};{env.get('PATH', '')}"

    if env_vars:
        env.update(env_vars)

    print(f"\n[EXEC] Running in MSYS2 CLANG64: {command}")
    print(f"[CWD]  {cwd}")

    proc = subprocess.run([str(bash_exe), "-l", "-c", f"cd '{cwd.as_posix()}' && {command}"], check=False, env=env)
    return proc.returncode


def kill_processes_in_directory(target_dir: Path):
    """Terminate any running processes originating from target_dir."""
    if not target_dir.exists():
        return
    print(f"[PROCESS] Checking for active processes locking {target_dir}...")
    try:
        resolved = str(target_dir.resolve()).replace("'", "''")
        cmd = f"$dir = '{resolved}'; Get-Process | Where-Object {{ $_.Path -and ($_.Path -like ($dir + '\\*')) }} | Stop-Process -Force -ErrorAction SilentlyContinue"
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=False, timeout=10)
        time.sleep(0.5)
    except Exception as e:
        print(f"[WARN] Failed to stop running processes in {target_dir}: {e}")


def create_zip_archive(source_dir: Path, zip_dest: Path, archive_prefix: str) -> Path:
    """
    Compress source_dir into zip_dest with standard forward-slash entry names.
    Ignores caches and local user states.
    """
    print(f"\n[ZIP] Creating clean zip archive: {zip_dest}")
    print(f"[ZIP] Source directory: {source_dir}")
    print(f"[ZIP] Archive root folder: {archive_prefix}")

    zip_dest.parent.mkdir(parents=True, exist_ok=True)
    temp_zip = zip_dest.with_suffix(".tmp.zip")
    if temp_zip.exists():
        temp_zip.unlink()

    files_added = 0
    total_bytes = 0

    with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(source_dir):
            # Prune unwanted directories
            dirs[:] = [
                d for d in dirs
                if d not in ("__pycache__", ".git", ".vscode", "user", "mods", "custom")
            ]

            rel_root = Path(root).relative_to(source_dir)
            for file in sorted(files):
                # Filter unwanted local files
                if file in ("bbport.ini", "mods.json", "patches.json", ".DS_Store"):
                    continue
                if file.endswith((".pyc", ".tmp")):
                    continue

                # Safety check for proprietary files
                lower_file = file.lower()
                suffix = Path(file).suffix.lower()
                if suffix in PROHIBITED_EXTENSIONS or lower_file in PROHIBITED_FILENAMES:
                    raise RuntimeError(
                        f"Safety violation: Found prohibited game file '{file}' in distribution staging!\n"
                        "Game assets (.dcx, .bdt, eboot.bin, etc.) must never be redistributed."
                    )

                src_file_path = Path(root) / file
                archive_arcname = f"{archive_prefix}/{rel_root.as_posix()}/{file}" if str(rel_root) != "." else f"{archive_prefix}/{file}"
                # Normalize double slashes
                archive_arcname = "/".join(filter(None, archive_arcname.split("/")))

                zf.write(src_file_path, arcname=archive_arcname)
                files_added += 1
                total_bytes += src_file_path.stat().st_size

    if zip_dest.exists():
        zip_dest.unlink()
    temp_zip.rename(zip_dest)

    zip_size_mb = zip_dest.stat().st_size / (1024 * 1024)
    orig_size_mb = total_bytes / (1024 * 1024)
    print(f"[ZIP] Successfully compressed {files_added} files.")
    print(f"[ZIP] Uncompressed size: {orig_size_mb:.2f} MB -> Zip size: {zip_size_mb:.2f} MB")
    return zip_dest


def rename_ready(source: Path, destination: Path):
    """Windows scanners can briefly retain a directory handle after extraction/rename."""
    for attempt in range(10):
        try:
            return source.rename(destination)
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.2)


def unzip_archive(zip_path: Path, target_folder: Path):
    """
    Unpacks zip_path cleanly while preserving existing user data, saves, and settings.
    """
    print(f"\n[UNZIP] Preparing complete replacement for {target_folder}...")
    target_folder = target_folder.resolve()
    parent = target_folder.parent
    parent.mkdir(parents=True, exist_ok=True)
    # Never expose an EXE before its Qt/Shiboken libraries have finished extracting.
    with tempfile.TemporaryDirectory(prefix=".bbport-unpack-", dir=parent,
                                     ignore_cleanup_errors=True) as temporary:
        staging = Path(temporary).resolve()
        with zipfile.ZipFile(zip_path, "r") as zf:
            if zf.testzip() is not None:
                raise ValueError("ZIP integrity check failed")
            for name in zf.namelist():
                parts = Path(name).parts
                if not parts or parts[0] != target_folder.name or ".." in parts:
                    raise ValueError(f"Unexpected package entry: {name}")
            zf.extractall(staging)
        replacement = staging / target_folder.name
        if not replacement.is_dir():
            raise ValueError("Archive does not contain the package folder")
        # Resolve and bound every directory involved in the swap before moving anything.
        assert replacement.resolve().parent == staging and staging.parent == parent
        assert target_folder.parent == parent and target_folder != parent
        kill_processes_in_directory(target_folder)
        if target_folder.exists():
            for filename in ("bbport.ini", "bbport_settings.json", "settings.json", "mods.json", "patches.json"):
                source = target_folder / filename
                if source.is_file():
                    shutil.copy2(source, replacement / filename)
            for folder in ("user", "mods", "atlas"):
                if (target_folder / folder).is_dir():
                    shutil.copytree(target_folder / folder, replacement / folder,
                                    dirs_exist_ok=True, symlinks=True)
        previous = staging / "previous"
        had_previous = target_folder.exists()
        if had_previous:
            rename_ready(target_folder, previous)
        try:
            rename_ready(replacement, target_folder)
        except Exception:
            if had_previous:
                rename_ready(previous, target_folder)
            raise
    if Path(temporary).exists():
        print(f"[WARN] Old package files remain locked; retained temporarily at {temporary}")
    print(f"[SUCCESS] Complete package replaced at {target_folder}")


def sync_atlas_maps(bb_pc_dir, target_dir):
    """Sync pre-generated Hunter's Atlas maps and art into distribution package."""
    atlas_src = bb_pc_dir / "ATLAS" / "atlas"
    if atlas_src.is_dir():
        atlas_dst = target_dir / "atlas"
        atlas_dst.mkdir(parents=True, exist_ok=True)
        for folder in ["art", "maps"]:
            s = atlas_src / folder
            d = atlas_dst / folder
            if s.is_dir():
                if d.exists():
                    shutil.rmtree(d)
                shutil.copytree(s, d)
        print(f"[ATLAS] Successfully packaged Hunter's Atlas maps & art into {atlas_dst}")

    gen_src = bb_pc_dir / "ATLAS" / "tools" / "atlas-generator"
    gen_dst = target_dir / "tools" / "atlas-generator"
    if gen_src.is_dir() and not (gen_dst / "generate_atlas.exe").is_file():
        gen_dst.parent.mkdir(parents=True, exist_ok=True)
        if gen_dst.exists():
            shutil.rmtree(gen_dst)
        shutil.copytree(gen_src, gen_dst)
        print(f"[ATLAS] Successfully packaged Hunter's Atlas generator into {gen_dst}")


# What build.sh compiles (bloodborne_pc/gpu/CMakeLists.txt reaches into ../src, ../third_party,
# ../tools and ../packaging/windows). A change anywhere else never needs a rebuild.
BUILD_INPUTS = ["build.sh", "msys2-env.sh", "gpu", "src", "third_party", "tools", "packaging/windows"]
BUILD_STAMP = "build-stamp.txt"


def build_inputs_stamp(bb_pc_dir: Path) -> str | None:
    """A fingerprint of the engine sources as they are on disk, committed or not: the git trees of
    the inputs in the working state, so committing what was built does not change it. None outside
    a git checkout."""
    with tempfile.TemporaryDirectory() as folder:
        # A copy of the index (for its stat cache) takes the uncommitted and untracked files.
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(folder) / "index")}

        def git(*command):
            return subprocess.run(["git", "-C", str(bb_pc_dir), *command], capture_output=True,
                                  check=True, env=env).stdout.decode().strip()
        try:
            index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index"))
            if index.is_file():
                shutil.copyfile(index, env["GIT_INDEX_FILE"])
            prefix = git("rev-parse", "--show-prefix")
            git("add", "-A", "--", *BUILD_INPUTS)
            tree = git("write-tree")
            trees = [git("rev-parse", f"{tree}:{prefix}{path}") for path in BUILD_INPUTS]
            head = git("rev-parse", "--short", "HEAD")
        except (OSError, subprocess.CalledProcessError):
            return None
    digest = hashlib.sha256("\n".join(trees).encode()).hexdigest()[:16]
    return f"{head} {digest}"


DLSS5_SETUP = Path("custom") / "scripts" / "dlss5-setup.ps1"


def make_dlss5_copy(repo_root: Path, unzipped_dir: Path) -> Path | None:
    """The local DLSS 5 build: dist/<pkg>-dlss5, a copy of the fresh package with the player's own
    DLSS 5 kit added by custom/scripts/dlss5-setup.ps1 (dlss5-inbox/kit). The package and its zip
    never carry those files, so they stay the ones to publish. The bbport.ini of the previous copy
    is kept; a first copy gets dlss5-inbox/bbport.ini. Skipped, with a note, where the setup script or the kit is missing (a fresh clone)."""
    setup = repo_root / DLSS5_SETUP
    kits = [repo_root / "dlss5-inbox" / "kit"]
    kit = next((k for k in kits if (k / "nvngx_dlssnr.dll").is_file()), None)
    if not setup.is_file() or kit is None:
        print(f"\n[DLSS 5] No local DLSS 5 copy: {'kit not found' if setup.is_file() else f'{DLSS5_SETUP} missing'}.")
        return None
    target = unzipped_dir.with_name(unzipped_dir.name + "-dlss5")
    print(f"\n>>> [DLSS 5] Local copy with the DLSS 5 kit: {target}")
    kill_processes_in_directory(target)
    with tempfile.TemporaryDirectory() as keep:
        # Settings: the previous copy's, else the ones kept beside the kit (dlss5-inbox/bbport.ini).
        saved_ini = kit.parent / "bbport.ini" if (kit.parent / "bbport.ini").is_file() else None
        if (target / "bbport.ini").is_file():
            saved_ini = Path(keep) / "bbport.ini"
            shutil.copy2(target / "bbport.ini", saved_ini)
        try:
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(unzipped_dir, target)
        except OSError as error:
            print(f"[WARNING] Could not replace {target}: {error}. Close anything using it and build again.")
            return None
        command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(setup),
                   "-Package", str(target), "-Kit", str(kit)]
        if saved_ini:
            command += ["-Ini", str(saved_ini)]
        result = subprocess.run(command, capture_output=True, text=True)
    for line in (result.stdout + result.stderr).splitlines():
        if line.strip():
            print(f"[DLSS 5] {line}")
    if result.returncode != 0:
        print(f"[WARNING] dlss5-setup.ps1 failed (exit {result.returncode}); {target} is incomplete.")
        return None
    return target


# The shadNet server seamless co-op hosts run (packaging/windows/build_coop_server.sh). Without it
# the launcher falls back to BBSC's own shadnet.exe, which drops this port's P2P signaling: the
# host rings a guest's sign and the guest never arrives (OnRoomTimeOut). 4.2.5 shipped that way.
COOP_SERVER = Path("coop-server") / "shadnet.exe"
NO_COOP_SERVER = "BB_PACKAGE_NO_COOP_SERVER"


def coop_server_missing(stage_dir: Path, env=os.environ) -> bool:
    """Whether a staged package lacks the co-op server and nobody said it may (BB_PACKAGE_NO_COOP_SERVER=1)."""
    return env.get(NO_COOP_SERVER) != "1" and not (stage_dir / "bin" / COOP_SERVER).is_file()


def stamps_match(built_from: str | None, stamp: str) -> bool:
    """Whether out/ was built from these sources. The commit in front of the digest is only a label:
    a commit that leaves the engine sources alone (a learning, docs) must not rebuild."""
    return bool(built_from) and built_from.split()[-1] == stamp.split()[-1]


def main():
    parser = argparse.ArgumentParser(description="Build dist and create release zip for Bloodborne PC port.")
    parser.add_argument("--repo-root", type=str, default=None, help="Root directory of the repository (default: parent of scripts)")
    parser.add_argument("--pkg-name", "-n", type=str, default="bbport-windows", help="Package folder and zip name (default: bbport-windows)")
    parser.add_argument("--rebuild", "-r", action="store_true", help="Force recompilation with build.sh even if out/ binaries match the sources")
    parser.add_argument("--skip-build", "-s", action="store_true", help="Skip build.sh and only run packaging/zipping")
    parser.add_argument("--only-zip", "-z", action="store_true", help="Fast mode: only create zip archive and unzip from clean stage")
    parser.add_argument("--build-coop", action="store_true", help="Rebuild the co-op server (packaging/windows/build_coop_server.sh); a missing one is always built")
    parser.add_argument("--build-atlas", action="store_true", help="Also build atlas generator (packaging/windows/build_atlas_generator.sh)")
    parser.add_argument("--no-dlss5", action="store_true", help="Don't make the local dist/<pkg>-dlss5 copy with the DLSS 5 kit")
    parser.add_argument("--msys2-root", type=str, default=None, help="Path to MSYS2 installation root (e.g. C:/msys64)")
    parser.add_argument("--output-dir", "-o", type=str, default=None, help="Custom output directory for zip (default: bloodborne_pc/dist)")

    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).resolve().parent
    repo_root = Path(args.repo_root).resolve() if args.repo_root else script_dir.parent
    bb_pc_dir = repo_root / "bloodborne_pc"
    if not bb_pc_dir.is_dir():
        bb_pc_dir = repo_root / "src" / "bloodborne_pc"

    if not bb_pc_dir.is_dir():
        print(f"[ERROR] Cannot find bloodborne_pc directory at {bb_pc_dir}", file=sys.stderr)
        sys.exit(1)

    dist_dir = Path(args.output_dir).resolve() if args.output_dir else (bb_pc_dir / "dist")
    out_dir = bb_pc_dir / "out"
    clean_stage_dir = out_dir / "stage" / args.pkg_name
    unzipped_dir = dist_dir / args.pkg_name
    zip_dest = dist_dir / f"{args.pkg_name}.zip"

    print("=" * 70)
    print(" Bloodborne PC - Build Dist & Release Zip Script")
    print("=" * 70)
    print(f"Repo root       : {repo_root}")
    print(f"Bloodborne src  : {bb_pc_dir}")
    print(f"Package name    : {args.pkg_name}")
    print(f"Dist directory  : {dist_dir}")
    print(f"Target Zip      : {zip_dest}")
    print(f"Unzipped Output : {unzipped_dir}")

    start_time = time.time()

    # Fast path: only zip existing clean stage and unzip
    if args.only_zip:
        if not clean_stage_dir.is_dir():
            print(f"[ERROR] --only-zip specified, but clean stage directory '{clean_stage_dir}' does not exist!", file=sys.stderr)
            sys.exit(1)
        print("\n>>> [--only-zip] Fast mode: skipping compilation and packaging, proceeding directly to archive generation...")
    else:

        # Look for MSYS2 bash
        bash_exe = find_msys2_bash(args.msys2_root)
        if not bash_exe:
            print("[WARNING] MSYS2 bash not found in standard paths.")
            if not args.skip_build and not clean_stage_dir.is_dir():
                print("[ERROR] Cannot build binaries without MSYS2 CLANG64. Please install MSYS2 or pass --only-zip.", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"MSYS2 Bash      : {bash_exe}")

        # Step 1: Check or run build.sh
        required_binaries = ["bb-probe.exe", "bb-gpu-capabilities.exe", "bb-play.exe"]
        binaries_missing = any(not (out_dir / exe).is_file() for exe in required_binaries)

        # out/ binaries are reused only when they were built from the sources on disk now: a merge,
        # a branch switch or an edit since the last build.sh changes the stamp and rebuilds.
        stamp_file = out_dir / BUILD_STAMP
        stamp = build_inputs_stamp(bb_pc_dir)
        built_from = stamp_file.read_text(encoding="utf-8").strip() if stamp_file.is_file() else None
        stale = stamp is not None and not stamps_match(built_from, stamp)

        if args.skip_build:
            print("\n>>> [1/4] --skip-build set. Skipping build.sh.")
            if stale and not binaries_missing:
                print(f"[WARNING] out/ binaries were built from {built_from or 'unknown sources'}, "
                      f"the sources are now {stamp}: the package may ship stale binaries.")
        elif binaries_missing or args.rebuild or stale:
            if not bash_exe:
                print("[ERROR] Binaries need building and MSYS2 bash not found!", file=sys.stderr)
                sys.exit(1)
            reason = ("binaries missing" if binaries_missing else "--rebuild" if args.rebuild
                      else f"sources changed since the last build ({built_from or 'no stamp'} -> {stamp})")
            print(f"\n>>> [1/4] Compiling binaries via build.sh ({reason})...")
            stamp_file.unlink(missing_ok=True)
            code = run_msys2_command(bash_exe, "bash build.sh", bb_pc_dir)
            if code != 0:
                print(f"[ERROR] build.sh failed with exit code {code}", file=sys.stderr)
                sys.exit(code)
            if stamp is not None:
                stamp_file.write_text(f"{stamp}\n", encoding="utf-8")
        else:
            print(f"\n>>> [1/4] Binaries already built from these sources ({stamp or 'not a git checkout'}). Skipping build.sh.")

        # Step 2: Optional helper components
        env_vars = {"BB_PACKAGE_NAME": args.pkg_name, "BB_PACKAGE_NO_REFRESH": "1"}
        dlss_vendor = repo_root / "vendor" / "nvidia-dlss"
        if dlss_vendor.is_dir():
            env_vars["DLSS_SDK_ROOT"] = dlss_vendor.as_posix()
            dlss_script = bb_pc_dir / "packaging" / "windows" / "build_dlss.sh"
            if dlss_script.is_file() and not (out_dir / "bbport_dlss.dll").is_file():
                if bash_exe:
                    print("\n>>> Building DLSS bridge...")
                    run_msys2_command(bash_exe, f"DLSS_SDK_ROOT='{dlss_vendor.as_posix()}' bash packaging/windows/build_dlss.sh", bb_pc_dir, env_vars)
                else:
                    print("\n[WARNING] DLSS bridge script found but MSYS2 bash was not found. Skipping DLSS bridge build.")

        coop_missing = not (out_dir / COOP_SERVER).is_file() and os.environ.get(NO_COOP_SERVER) != "1"
        if (args.build_coop or coop_missing) and bash_exe:
            print("\n>>> Building Co-op Server" + (" (out/coop-server missing)..." if coop_missing else "..."))
            run_msys2_command(bash_exe, "bash packaging/windows/build_coop_server.sh", bb_pc_dir, env_vars)

        if args.build_atlas and bash_exe:
            print("\n>>> Building Hunter's Atlas Generator...")
            run_msys2_command(bash_exe, "bash packaging/windows/build_atlas_generator.sh", bb_pc_dir, env_vars)

        # Step 3: Run packaging script
        package_sh = bb_pc_dir / "packaging" / "windows" / "package.sh"
        if package_sh.is_file() and bash_exe and not args.skip_build:
            print("\n>>> [2/4] Packaging Windows distribution (package.sh)...")
            kill_processes_in_directory(unzipped_dir)
            # Ensure WINPYTHON points to a valid Windows Python if available
            venv_py = repo_root / ".venv" / "Scripts" / "python.exe"
            if venv_py.is_file():
                env_vars["WINPYTHON"] = str(venv_py).replace("\\", "/")
            code = run_msys2_command(bash_exe, "bash packaging/windows/package.sh", bb_pc_dir, env_vars)
            if code != 0:
                print(f"[WARNING] package.sh returned exit code {code}.")

    # Step 4: Ensure clean Zip Archive and Unzip
    print("\n>>> [3/4] Verifying and finalizing Zip archive & Unzipped directory...")
    if clean_stage_dir.is_dir():
        # Ensure custom/ directory is never present in the release package
        if (clean_stage_dir / "custom").is_dir():
            shutil.rmtree(clean_stage_dir / "custom", ignore_errors=True)
        # Ensure latest documentation is synced into stage
        if (repo_root / "README.md").is_file():
            shutil.copy2(repo_root / "README.md", clean_stage_dir / "README.md")
        if (repo_root / "features.md").is_file():
            shutil.copy2(repo_root / "features.md", clean_stage_dir / "features.md")
        if (repo_root / "build.md").is_file():
            shutil.copy2(repo_root / "build.md", clean_stage_dir / "build.md")
        # Architecture is development-only under custom/. Remove stale copies
        # when reusing a stage created before that guide was relocated.
        (clean_stage_dir / "architecture.md").unlink(missing_ok=True)
        if (repo_root / "Release_Notes.md").is_file():
            shutil.copy2(repo_root / "Release_Notes.md", clean_stage_dir / "Release_Notes.md")
        if (repo_root / "docs" / "changelog").is_dir():
            shutil.copytree(repo_root / "docs" / "changelog",
                            clean_stage_dir / "docs" / "changelog", dirs_exist_ok=True)
        # Player guides at the top of docs/ (dlss5-setup.md), linked from the READMEs.
        for guide in (repo_root / "docs").glob("*.md"):
            (clean_stage_dir / "docs").mkdir(parents=True, exist_ok=True)
            shutil.copy2(guide, clean_stage_dir / "docs" / guide.name)
        if (repo_root / "docs" / "images").is_dir():
            (clean_stage_dir / "docs" / "images").mkdir(parents=True, exist_ok=True)
            for img in (repo_root / "docs" / "images").glob("*"):
                if img.is_file():
                    shutil.copy2(img, clean_stage_dir / "docs" / "images" / img.name)
        # Ensure version.txt always reads pyproject.toml
        pyproject_file = repo_root / "pyproject.toml"
        proj_ver = "3.1.0"
        if pyproject_file.is_file():
            try:
                import tomllib
                proj_ver = tomllib.loads(pyproject_file.read_text(encoding="utf-8")).get("project", {}).get("version", "3.1.0")
            except Exception:
                pass
        clean_ver = proj_ver.split("+")[0]
        (clean_stage_dir / "version.txt").write_text(f"{clean_ver}\n", encoding="utf-8")
        if (clean_stage_dir / "launcher").is_dir():
            (clean_stage_dir / "launcher" / "version.txt").write_text(f"{clean_ver}\n", encoding="utf-8")
        sync_atlas_maps(bb_pc_dir, clean_stage_dir)
        if coop_server_missing(clean_stage_dir):
            print(f"[ERROR] {clean_stage_dir / 'bin' / COOP_SERVER} is missing: seamless co-op hosts would run "
                  f"BBSC's shadnet.exe and guests could not join. Build it (--build-coop, or "
                  f"packaging/windows/build_coop_server.sh), or set {NO_COOP_SERVER}=1 for a package "
                  f"without it.", file=sys.stderr)
            sys.exit(1)
        # One archive per build: publish_release.py makes the tagged copy it uploads.
        create_zip_archive(clean_stage_dir, zip_dest, args.pkg_name)
    elif not zip_dest.is_file():
        print(f"[ERROR] Neither {clean_stage_dir} nor {zip_dest} was created!", file=sys.stderr)
        sys.exit(1)

    # Always unzip the zip into dist/<pkg-name> removing any old unzipped folder
    unzip_archive(zip_dest, unzipped_dir)

    # Ensure unzipped directory also has version.txt synced from pyproject.toml
    pyproject_file = repo_root / "pyproject.toml"
    proj_ver = "3.1.0"
    if pyproject_file.is_file():
        try:
            import tomllib
            proj_ver = tomllib.loads(pyproject_file.read_text(encoding="utf-8")).get("project", {}).get("version", "3.1.0")
        except Exception:
            pass
    clean_ver = proj_ver.split("+")[0]
    (unzipped_dir / "version.txt").write_text(f"{clean_ver}\n", encoding="utf-8")
    if (unzipped_dir / "launcher").is_dir():
        (unzipped_dir / "launcher" / "version.txt").write_text(f"{clean_ver}\n", encoding="utf-8")

    dlss5_dir = None if args.no_dlss5 else make_dlss5_copy(repo_root, unzipped_dir)

    # Step 5: Summary & Checksum
    print("\n>>> [4/4] Summary & Checksums:")
    sha = compute_sha256(zip_dest)
    size_mb = zip_dest.stat().st_size / (1024 * 1024)
    elapsed = time.time() - start_time

    # Automatically record audit record in package-audit-verification.json
    audit_json = out_dir / "package-audit-verification.json"
    # --output-dir may be outside the repository (another checkout's dist): then the full path.
    try:
        archive = str(zip_dest.relative_to(repo_root))
    except ValueError:
        archive = str(zip_dest)
    audit_data = {
        "archive": archive.replace("/", "\\"),
        "version": clean_ver,
        "full_version": proj_ver,
        "bytes": zip_dest.stat().st_size,
        "sha256": sha,
        "zip_crc": "pass"
    }
    try:
        import json
        audit_json.write_text(json.dumps(audit_data, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass

    print("-" * 70)
    print(f"Zip             : {zip_dest}")
    print(f"Version         : {clean_ver} (Full: {proj_ver})")
    print(f"Size            : {size_mb:.2f} MB ({zip_dest.stat().st_size:,} bytes)")
    print(f"SHA-256         : {sha}")
    print(f"Unzipped Output : {unzipped_dir}")
    print(f"DLSS 5 copy     : {dlss5_dir or 'not made'} (local only; publish the zip above)")
    print(f"Duration        : {elapsed:.1f}s")
    print("-" * 70)
    print("Build dist, zip, and clean unzipping completed successfully!")


if __name__ == "__main__":
    main()
