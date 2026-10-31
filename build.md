# Build, test and package on Windows

Updated **2026-10-27**. Run PowerShell examples from the repository root and Bash examples from an **MSYS2 CLANG64** shell. [Player guide](docs/changelog/README-LAUNCHER-V30.md) · [Features](features.md).

Examples use `C:/bbport` as the checkout location; substitute your own path.

## Toolchains

| Dependency | Purpose |
| --- | --- |
| MSYS2 CLANG64 | Clang, CMake, Ninja, Vulkan/SDL and native libraries. Full package list: [Windows packaging README](bloodborne_pc/packaging/windows/README.md#build). |
| Windows Python | Frozen PySide6/QML launcher and packaging wrapper. `pyproject.toml` declares dependencies; Python 3.11+ is needed for the wrapper's `tomllib` version parsing without its fallback. |
| VS 2026 C++ Build Tools + Windows SDK | MSVC-built NVIDIA SDK bridge; default CMake generator `Visual Studio 18 2026`. |
| Native Windows CMake | Must support the chosen Visual Studio generator. `CMAKE_EXE` selects it for the bridge script. |
| Local NVIDIA DLSS SDK | Optional SDK checkout under `vendor/nvidia-dlss/`, or explicit `DLSS_SDK_ROOT`. |
| Game dump | Needed to run gameplay; not redistributed in packages. |

Initialize dependencies from the repository root:

```powershell
git submodule update --init --recursive
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Use a native Windows Python for launcher freezing. The renderer's dependency environment comes from MSYS2; these are different toolchains.

## Native renderer and optional components

In CLANG64:

```bash
cd /c/bbport/bloodborne_pc
bash tools/fetch_fsr4_assets.sh
bash build.sh
DLSS_SDK_ROOT=../vendor/nvidia-dlss bash packaging/windows/build_dlss.sh
```

`build.sh` configures `out/gpu/`, builds `bb-probe`, `bb-gpu-capabilities`, `bb-play`, and copies executables to `out/`. Windows ThinLTO defaults on. `BB_PGO` accepts `generate`, `use`, `off`; the default uses an existing profile when available. Training counters/profile counts do not establish performance improvement.

The bridge uses its own `out/dlss-bridge-vs18/` cache and runs `bbport-dlss-check.exe` before copying DLLs into `out/`. An explicit older-toolchain override uses a separate cache:

```bash
DLSS_CMAKE_GENERATOR='Visual Studio 17 2022' \
DLSS_BUILD_DIR=out/dlss-bridge-vs17 \
DLSS_SDK_ROOT=../vendor/nvidia-dlss \
bash packaging/windows/build_dlss.sh
```

Optional helpers:

```bash
bash packaging/windows/build_coop_server.sh
bash packaging/windows/build_atlas_generator.sh
```

The co-op server is required: `package.sh` stops without it (`BB_PACKAGE_NO_COOP_SERVER=1` allows a package without it) and the wrapper builds it when missing. Inspect the Atlas generator's log when you build it. The commands above and wrapper below are the current workflow.

## Focused verification

After configuring the native build, in CLANG64:

```bash
cd /c/bbport/bloodborne_pc
cmake --build out/gpu --target hdr-presentation-test dlss-settings-test rt-settings-test nvidia-gpu-test motion-history-test presentation-telemetry-test frame-admission-test frame-handoff-test reflex-handoff-test
out/gpu/hdr-presentation-test.exe
out/gpu/dlss-settings-test.exe
out/gpu/rt-settings-test.exe
out/gpu/nvidia-gpu-test.exe
out/gpu/motion-history-test.exe
out/gpu/presentation-telemetry-test.exe
out/gpu/frame-admission-test.exe
out/gpu/frame-handoff-test.exe
out/gpu/reflex-handoff-test.exe
```

Run the existing launcher regression suite from the root with the Windows environment containing its dependencies:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s bloodborne_pc/tests -p "test_launcher*.py"
```

The HDR test requires a suitable Vulkan GPU and uses the renderer's actual generated shader SPIR-V. It reports whether the Khronos validation layer is installed. The recorded RTX 4090 run passed without that layer. Shader readback does not test live swapchain resizing, NGX evaluation, physical output or the entire launcher/network stack.

The CPU motion-history test covers total-capacity versus character-reserve exhaustion. The presentation-telemetry test covers five-second cadence, independent generation/acceptance counts, rates, idle intervals and counter/clock resets. Live tests must compare `Ray tracing capture:` and `Frame generation telemetry` output against scene/overlay evidence. FG telemetry needs no `BB_FPS_LOG`; that optional flag adds handoff, Reflex, admission and detailed pacing timing. Keep `BB_VIDEOOUT_BACKPRESSURE=0` for the recovery baseline. The six CPU tests do not certify GPU/resource lifetimes.

## Package a release or distinct testing build

To bump the version, edit only the top `## [X.Y.Z+build…]` header in `Release_Notes.md` (or run `scripts/bump_build_number.py`); the commit hook writes `pyproject.toml`, `uv.lock` and `bloodborne_pc/version.txt`, and the launcher reads `version.txt` at run time.

After rebuilding the bridge and any desired helpers, from the root:

```powershell
.\.venv\Scripts\python.exe scripts/build_dist.py --pkg-name bbport-windows-4.2.2
```

Equivalent PowerShell wrapper:

```powershell
.\scripts\build_dist.ps1 -PackageName bbport-windows-4.2.2
```

The wrapper runs native build/package steps, freezes the launcher through `package.sh`, stages runtime files and Atlas assets, creates canonical/versioned ZIPs and extracts a playable folder. Native binaries are rebuilt automatically when the engine sources changed since the last build (`out/build-stamp.txt`; launcher and doc changes don't count). It only auto-builds a missing bridge; rebuild an existing bridge explicitly after bridge/SDK changes. `package.sh` rejects stale/incomplete ABI bundles, but the ABI check is not a freshness or gameplay check.

| Option | Actual behavior |
| --- | --- |
| `--rebuild` | Forces `build.sh` even when the binaries match the sources (for example after changing only `launcher/assets/hunter-icon.ico`). |
| `--build-coop`, `--build-atlas` | Rebuilds the co-op server / builds the Atlas generator. A missing co-op server (`out/coop-server`) is always built, and a package without it stops with an error (seamless co-op guests can't join a host on BBSC's `shadnet.exe`); `BB_PACKAGE_NO_COOP_SERVER=1` allows one. |
| `--skip-build` | Skips both native compilation and `package.sh`; may reuse an old stage/archive. Warns when the binaries don't match the sources. |
| `--no-dlss5` | Skips the local `dist/<pkg>-dlss5` copy. By default every build also makes it from the fresh package plus the DLSS 5 kit in `dlss5-inbox/kit`; the ZIP and `dist/<pkg>` never contain DLSS 5 files and are the ones to publish. |
| `--only-zip` | Skips build/package steps and prefers the existing clean stage. If no stage exists, an existing ZIP may be reused. |
| `--pkg-name` | Selects stage/archive/extracted folder name; use a distinct name for testing. |
| `--msys2-root`, `--output-dir` | Overrides MSYS2 discovery or output location. |

The wrapper may terminate processes running from the target package folder and replace that folder. It backs up selected configuration files and `user/`; it does not promise to retain every mod folder. Prefer a new package name and keep backups. The ZIP excludes user saves, mods, local INI state and prohibited game assets. The extracted folder may regain backed-up local state and therefore differs from the clean ZIP.

## Output layout and audit

```text
bloodborne_pc/
  out/gpu/                         native build and test executables
  out/stage/<package>/             clean packaging stage
  dist/<package>.zip               canonical ZIP
  dist/<package>-v<version>.zip    versioned copy
  dist/<package>/                  extracted playable folder
    Bloodborne.exe
    Play Bloodborne.exe
    bin/                          native renderer, bridge and SDK DLLs
    launcher/                     launcher runtime resources
    atlas/maps/ and atlas/art/    runtime Atlas assets
    tools/atlas-generator/        frozen map generator
    fsr4_shaders/ and patches/    shader/patch resources
```

The development `bloodborne_pc/ATLAS/` directory is not copied verbatim. Runtime assets are collected into the lowercase package `atlas/` directories. The verified HDR+FG archive has 20 map files and 7 art assets; the runtime reports 16 registered areas.

The wrapper writes `out/package-audit-verification.json`. Independently verify CRC and hash rather than treating its `zip_crc` field as an executed CRC test:

```powershell
.\.venv\Scripts\python.exe -m zipfile -t bloodborne_pc/dist/bbport-windows-hdr-fg-testing.zip
Get-FileHash bloodborne_pc/dist/bbport-windows-hdr-fg-testing.zip -Algorithm SHA256
```

Also run the built bridge checker against the DLL actually staged/packaged, compare selected native/launcher/DLL hashes against the playable folder, and retain build logs plus commit/settings/runtime evidence. ZIP bytes are not guaranteed reproducible. A missing stage can leave an older archive in use, so a successful wrapper exit alone does not prove a fresh package.

The current recovery archive is `bloodborne_pc/dist/bbport-windows-3.2.6-recovery.zip`, built from `b6b9810` / `3.2.6+build102626.192649`: 321,675,968 bytes, SHA-256 `92df4665c5a3d81b212092c14c884d3f121e537dc8a20c91a7fc3ea863d2b904`. CRC, matching versioned ZIP, native/frozen-launcher freshness, DLSS ABI 2 SR/FG and Atlas assets passed verification. The recovered full run includes startup and 18 min 46 s of telemetry with HDR/DLSS 2× and normal quit. This documentation pass leaves that ZIP unchanged; the new root architecture guide is staged in future builds.

## Versioning and review

`pyproject.toml` and the newest versioned entry in `Release_Notes.md` are synchronized by `scripts/sync_version.py`. The launcher discovers source/package version metadata. Package `version.txt` and ZIP suffix use the base version; preserve the full build tag and commit in evidence too.

```powershell
python scripts/sync_version.py --check
trail check
```

With `core.hooksPath=.githooks`, pre-commit syncs versions and pre-push checks them. A nonempty `## Unreleased` section triggers automatic build-timestamp promotion; use `python scripts/bump_build_number.py --patch` explicitly for renderer fixes that advance the patch version, as with 3.2.2 HDR/FG integration. Version promotion does not rebuild existing binaries or ZIPs. Use `scripts/bump_build_number.py --help` for other version modes and optional distribution builds. Publishing is separate from packaging; inspect `scripts/publish_release.py --help` / `scripts/publish_release.ps1` for that workflow.

## Preserve complete run logs

The launcher streams full stdout/stderr to `<saves folder>/last_run.log`, rotating older runs to numbered logs. The QML live view and Copy Log retain 350,000 characters; attach the saved file to preserve startup. Its UI-generated exit footer is not currently written to the saved file. The 3.2.6 run's complete output was recovered without rerunning the game.

## Renderer maintenance checks

The new map spatial index, VRAM pressure policy and cache-writer lifecycle are covered by `render-maintenance-test`. `overlay-upload-test` exercises persistent ImGui upload buffers and concurrent Vulkan driver-cache extraction on an offscreen GPU. Build them with `cmake --build out/gpu --target render-maintenance-test overlay-upload-test` from the CLANG64 bloodborne_pc directory, then run both executables. The GPU test does not launch the game or open a window. These checks do not replace the identical-route gameplay comparison.
