# Changelog — October 27, 2026

## 3.2.10 — 3.2.10+build102726.114500

- **Uncapped FPS Dynamic Simulation Timestep Hook:** Hooked running-jump horizontal momentum vector multiply (`0x1a4abca`). The on-disk executable is unmodified; in-memory instruction displacement is redirected to an isolated hook cell in the stub area. Dynamically scales horizontal decay by `0.95 ** (30 * dt)` using the game's measured frame delta (`[manager + 0x264]`) with high-precision wall-clock fallback (`QueryPerformanceCounter`), clamped between 1/480 s and 1/20 s. The original constant vector at `0x490b5b0` and vertical jump impulses are preserved. Controlled via `BB_JUMP_DT=1` (auto-enabled when uncapped unless disabled via `running_jump_fix=0` in `bbport.ini` or `BB_RUNNING_JUMP_FIX=0`). Configurable source via `BB_JUMP_DT_SOURCE=clock|game`. Interval telemetry now reports every 10 seconds by default (silenced via `BB_FPS_LOG=0`).
- **GPU Vendor-Partitioned Shader Catalog & Isolated Cache Storage:** Partitioned `shader_catalog/` into `nvidia/` (PCI ID `0x10DE`, 1,953 records) and `amd/` (PCI ID `0x1002`, ready for AMD records), with Intel (`0x8086`) and common fallback support. User pipeline caches are stored in vendor-isolated directories (`user/cache/CUSA03173/<vendor>/`) with automatic legacy cache migration. `BB_GPU_VENDOR` strictly overrides hardware detection before copying, preventing cross-vendor flattening. Cross-vendor profile mismatches automatically clear stale architecture records. Fixed cold-start profile copy to eliminate spurious `unexpected size (0 != 64)` warnings.
- **Pipeline Variant Qualification:** Pre-building seeds known permutations ahead of time, eliminating startup and traversal hitches for cataloged shaders. Uncataloged variants (including 229 session-local motion pipelines, which are deferred to runtime by design to prevent binding stale session addresses) compile on first use.
- **Validation:** 63 Python tests passed, native `jump-decay-test.exe` passed. Packaged in `bbport-windows-3.2.10.zip` (SHA-256: `fadeca188d7d33039a0aa489d6237f579a9f6f41a5d118c4fa06c473a806d5e4`).

## 3.2.9 final — 3.2.9+build102726.105142

- Co-op UI correction is confirmed by the user. Retain the renderer/cache changes below and keep admission blocking off.
- Replace the FPS presets' existing four horizontal-momentum damping writes with `0.95 ** (30 / fps)` at fixed 60/90/120/144 FPS. The lists previously held the same 90 FPS value for all four rates. Require a matching movement instruction/original vector and precisely the expected four writes.
- Keep 30 FPS and external FPS replacements intact. Add `running_jump_fix=0` / `BB_RUNNING_JUMP_FIX=0` for comparison. No jump-height multiplier is introduced.
- Leave uncapped unchanged, with a diagnostic explaining that measured frame time is required. An arbitrary 120 FPS value would change momentum incorrectly at other achieved rates.
- Validation: patch regression suite and prepared-game preset checks pass. Pyrefly diagnostics were resolved with explicit optional-value narrowing and required XML attribute access. Included in the final `bbport-windows-3.2.9` package; same-location gameplay distance measurements remain pending.

## Earlier 3.2.9 renderer-maintenance testing builds

Version: **3.2.9+build102726.102043**. This is a patch release for renderer/cache performance and reliability work; no major/minor compatibility change is intended.

### Atlas drawing and backend cost

- Build an order-preserving per-layer floor-triangle spatial index on the background map worker. UI rendering selects viewport-overlapping triangles while retaining fog/height tests and fallback coverage for large geometry.
- Retain mapped per-frame ImGui vertex/index upload memory and non-coherent flushes. Grow capacity with 50% headroom, then unmap at resize/destruction. Frame-ring synchronization and texture-upload queue waits remain intact.
- Include vertex/index counts in slow-overlay reports to make route comparisons interpretable.

### VRAM and pipeline maintenance

- Extend the existing texture/buffer collectors and periodic RT retirement with RT response to current device-wide memory pressure. Enter at 90% of budget, recover below 85%, and retire at most 128 eligible cold entries per sweep using existing deferred destruction. Restrict new static allocation during pressure; retain recent-frame protection and dynamic-character exceptions.
- Prune structurally corrupt or version-invalid pipeline-key records at startup. Retain valid but unavailable records; report session-address motion deferrals separately from invalid keys.
- Restore Vulkan driver-cache data only for matching vendor/device/driver UUID. Bound cache blobs to 256 MiB and checkpoint changed cache data in the background for repeat-run reuse. New variants still compile when first encountered.
- Drain accepted FIFO cache writes during controlled close. Periodic checkpoints are required because the window shutdown path terminates without renderer destructors; forced termination may still interrupt recent writes.
- Log runtime shader/graphics/compute compilation taking at least 10 ms under BB_FPS_LOG. Keep admission blocking off.

### Co-op settings correction and first gameplay follow-up

The original 3.2.9 package still drew account/server controls twice: the generic FieldRow repeater and the guided form both owned the same registered keys. Backend navigation metadata remains intact, while generic row generation now excludes the guided editors. Search focuses the guided control and inactive controls refresh after settings changes. A headless rendered-QML test traverses both visual and QObject trees; it detects all three duplicate controls in the old path and passes with a single set after correction. No credential migration or reset is needed.

The supplied original 3.2.9 log contains 147 telemetry windows / 12 min 16 s. All 50,124 generated outputs were accepted, with zero unpresented outputs, failed presents or capture exclusions. No measured PresentImage call reaches 50 ms. Six 20–26 ms overlay events all have texture updates, and no runtime compile event reaches the 10 ms logging threshold. All 89 memory sweeps are below pressure, so actual pressure reclamation remains untested. Three rendering-stall messages and intervals up to 424.8 ms remain outside slow PresentImage calls. This is not an identical-route performance measurement.

A refreshed `bbport-windows-3.2.9-coop-settings-testing` package includes the UI correction; the original renderer-testing artifact remains separately identified.

### Validation and acceptance

Native build and CPU regressions passed for spatial equivalence/order, pressure hysteresis and target bounds, driver-cache identity checks, and deterministic FIFO drain/failure handling. The RTX 4090 offscreen GPU test passed across 24 frames: 12 upload-buffer reuses, 12 growth events, exact CPU payload checks, successful GPU submission/shutdown, concurrent driver-cache extraction during pipeline creation, and cache restoration. These are not gameplay FPS or physical-latency measurements, and do not certify all hardware/GPU lifetimes.

The original renderer distribution is `bbport-windows-3.2.9-render-maintenance-testing` (`3.2.9+build102726.094719`); the refreshed UI build is `bbport-windows-3.2.9-coop-settings-testing` (`3.2.9+build102726.102043`). Archive integrity and binary checks are performed separately after packaging. Identical-route gameplay and a separate long-session VRAM-pressure test are pending. Real pressure may reduce static RT coverage; compare coverage and build-budget reports as well as memory. Do not re-enable admission blocking to reduce a marker interval.

## 3.2.8 — Atlas background preparation and launcher/co-op updates

- Move JSON parsing and initial cut/interior geometry-cache construction off the presentation thread into one isolated CPU worker, with loading feedback and non-blocking result adoption.
- Add overlay substage timing; fix the capture report's literal percent sign.
- Source updates also integrate BBSC 0.0.2 packages, public-server/private configuration and host data migration; restore setup artwork/gradient blending and adjust wizard width.

### Preserve artifact provenance

The supplied game log was produced by **3.2.8+build102726.002419**, archive `bbport-windows-3.2.8-atlas-hitch-testing.zip`, 321,803,588 bytes, SHA-256 `2fdf83eabacd0d3750ab58875bf61022ab3e73fb090e214e2c97c859ccc68b61`. Later source metadata **3.2.8+build102726.085821** includes the co-op/setup-artwork changes and must not be described as the artifact exercised by that log.

That 22 min 1 s sample contains 264 telemetry windows, zero capture exclusions at 16 Mi vertices, and 85,333 generated/accepted outputs with zero unpresented outputs or failed presents. Admission stayed observe-only; no GPU-loss/WriteInvalid/unmapped-SRT markers were found. No measured PresentImage call reached 50 ms, while 36 overlay calls of 20–43 ms, seven rendering-stall messages and startup intervals of 134/182 ms remained. It ends with Quit Game but has no recorded process exit-code footer.

## 3.2.7 — RT capture control and hitch localization

- Add RT-only capacity override BB_RT_CAPTURE_BUDGET (1–64 Mi vertices, base-capacity floor) and preserve the 15% character reserve even with equal budgets or failed growth. Defaults remain 4 Mi base / 12 Mi RT.
- Add same-image slow-present diagnostics. The supplied 27 min 42 s sample at 16 Mi vertices has zero capture exclusions and localizes four 50–326 ms events to overlay rendering, prompting the background Atlas work. Internal attribution and routes/settings were not controlled.

[Feature catalog](../../features.md) · [Release notes](../../Release_Notes.md) · [Build and checks](../../build.md) · [Earlier changelog](changelog-2026-10-26.md) · [Launcher guide](README-LAUNCHER-V30.md).
