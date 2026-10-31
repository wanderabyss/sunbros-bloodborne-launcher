# Bloodborne PC Custom — Release Changelog (2026-10-25)

> Historical v3.0 release narrative. Current capabilities, disabled reflection/local-light prototypes, unmeasured performance claims and the 3.2.6 recovery policy are described in the [feature catalog](../../features.md) and [latest dated changelog](changelog-2026-10-26.md). Earlier claims below are retained as history rather than current acceptance evidence. **DLSS correction:** the first 4K 120 FPS runs used the FSR 3.1 fallback (old ABI 1 bridge), not DLSS-G; DLSS-G 2× was first observed after the ABI 2 rebuild (DLSS review §1, §7). The SDK runtime in the plans is 310.9.16.

**Milestone**: Release v3.0 (SunBros Custom RT & DLSS Edition)  
**Base Target**: Jgamrot 2.1 (`af2baf3`) + BBSC 0.0.2  
**Date**: October 25, 2026  

---

## Summary of Changes

Version 3.0 represents a major milestone for the Bloodborne PC port, combining the atmospheric **SunBros Custom UI Launcher** with the high-performance **Vulkan Ray Tracing** and **NVIDIA DLSS 4.5** rendering pipelines into a unified, stable release.

---

### 1. Repository & Directory Structure
- **Root Directory Cleanup**:
  - Eliminated the redundant `src/` wrapper directory. The game source and launcher now reside directly under [`bloodborne_pc/`](../../bloodborne_pc).
- **Configuration & Script Updates**:
  - Updated [`scripts/build_dist.py`](../../scripts/build_dist.py), [`scripts/build_dist.ps1`](../../scripts/build_dist.ps1), and legacy build helpers to resolve paths relative to `bloodborne_pc/`.
  - Updated [`pyproject.toml`](../../pyproject.toml) version to `3.0.0` and adjusted all tool paths.

---

### 2. Vulkan Real-Time Ray Tracing
- **Hardware-Accelerated Compute Pipeline**:
  - Introduced 7 specialized Vulkan compute shaders in `gpu/shadps4/video_core/host_shaders/`:
    - `rt_trace.comp`: Traverses scene BVH and dispatches occlusion rays.
    - `rt_filter.comp`: Edge-preserving spatio-temporal bilateral filter.
    - `rt_instances.comp`: High-frequency dynamic instance updates.
    - `rt_gather.comp`: Accumulates ambient occlusion and directional moon shadow terms.
    - `rt_apply.comp`: Screen-space deferred composite with native G-buffer.
    - `rt_check.comp`: Hardware validation and fallback verification.
    - `rt_common.glsl`: Common data structures, ray packing, and math helpers.
- **RTAO (Ray-Traced Ambient Occlusion)**:
  - Adds physical contact shadows and ambient depth across Yharnam geometry.
  - Configurable quality tiers (Off, Low, Medium, High, Ultra) and strength scaling (0.1 to 2.0).
- **Ray-Traced Moon Shadows**:
  - Directional ray-traced shadows cast by the pale moon, overlaid on character dynamic shadows.
  - Native torch and lamppost lighting preserved for atmospheric fidelity.
- **Screen-Space Ray-Traced Water Reflections (`rt_reflections`)**:
  - Added hybrid planar/ray-traced reflection pass against TLAS with Schlick Fresnel ($F_0 \approx 0.04$) and fallback lighting for wet cobblestones and puddles in Central Yharnam and Fishing Hamlet.
  - Dedicated `Kind::Reflection` screen effect pipeline in `vk_rt_screen_effect.cpp` and `vk_rt_effects.cpp` with a-trous spatial/temporal filtering.
- **Anti-Ghosting Temporal History Clamping (RTG-5)**:
  - 3×3 color neighborhood bounding box history clamp in `rt_filter.comp` eliminating 16–24 frame ghost trails on fast-moving casters and dynamic cloaks.
- **Dynamic Hot-Swapping**:
  - Presets apply immediately at runtime without requiring a game restart.
- **Dynamic Secondary Lights (`rt_secondary_lights`)**:
  - Integrated engine toggle, launcher backend support, and in-game ImGui overlay menu.

---

### 3. True HDR (High Dynamic Range) & Rec. 2020
- **Native Hardware HDR Swapchain**:
  - Native `VK_COLOR_SPACE_HDR10_ST2084_EXT` support with SMPTE ST 2084 PQ EOTF transfer function.
  - Custom luminance tonemapper in `post_process.frag` tuned for Bloodborne's deep blacks and incandescent firelight with BT.709-to-BT.2020 color primary matrix conversion.
  - Presenter-isolated swapchain recreation with 10-bit (`VK_FORMAT_A2B10G10_UNORM_PACK32`) ImGui compatibility.

---

### 4. Compiler & Performance Optimizations (PGO & ThinLTO)
- **Profile-Guided Optimization (PGO)**:
  - Integrated Clang IR instrumentation and profile ingestion via `llvm-profdata merge` in `build.sh` and `CMakeLists.txt`.
  - Captured 108B execution count profile across 18,203 functions in gameplay tours, generating `pgo/bbgpu.profdata` (5.0 MB) to optimize branch layouts in core GPU paths (`PostDraw`, `RecorderThread`, `ApplyGraphicsRegisterPacket`, `ImageResource::Fetch`).
- **Thin Link-Time Optimization (ThinLTO)**:
  - Defaulted `BB_LTO=ON` with persistent compiler cache for optimal codegen.

---

### 5. NVIDIA DLSS 4.5 & NVIDIA Reflex
- **DLSS Frame Generation**:
  - Packaged native `nvngx_dlssg.dll` from DLSS SDK 310.9.1 with custom `bbport_dlss.dll` bridge for 4K 120 FPS targets.
  - Removed duplicate loose copies in repository root; staged directly from `nvngx_dlss_310.9.1/`.
- **DLSS Model Selection**:
  - Added `Auto: recommended for your GPU` to automatically select Model K on RTX 20/30 (avoiding FP8 penalties) and Model M/L on RTX 40/50.
  - Manual model selection: Auto, Model K, Model M, Model L, Model J, Default.
- **NVIDIA Reflex Low Latency**:
  - Integrated low-latency frame pacing (`Off`, `On`, `On + Boost`) via `vk_reflex.cpp` to minimize parry input delay.
  - Automatically couples with DLSS Frame Generation to prevent frame queue latency buildup.
- **AMD FSR 4 Fallback**:
  - Preserved FSR 3.1 & FSR 4 compute shader fallback (`fsr4_shaders/`) for non-RTX graphics cards.

---

### 4. SunBros Custom UI Launcher (v3.0)
- **Instant Launcher Launch**:
  - Removed the legacy 3-second startup countdown toast. Clicking `Bloodborne.exe` opens directly into the launcher interface.
- **Typography & Aesthetics**:
  - Authentic gothic typography using official **`fleshandblood`** font.
  - Textured ivory header title logo with dimensional atmospheric drop shadow.
  - High-resolution Hunter battle artwork with cinematic vignette scrims.
- **Compact Hunt Mode Selector**:
  - Replaced stacked buttons with a sleek popup selector: **Offline**, **Online**, and **Co-op**.
- **Hunter Dossier & Trophy Archive**:
  - Real-time character profile status card decoding decrypted save data (`user/savedata/`).
  - Interactive popup modal showcasing all 40 PlayStation trophies with rarity badges and lore descriptions.
- **Obsidian Dark Theme**:
  - Modern dark obsidian palette with ivory text, eliminating all legacy black-on-black contrast bugs.
- **Clean Interface Layout**:
  - Removed redundant lower-left version watermark on the Settings page to eliminate visual overlap.
  - Version updated to **v3.0** throughout UI, backend, and documentation.

---

### 5. Multiplayer & Co-op (BBSC 0.0.2)
- **Relay Fallback**: Automatic UDP port 3478 relay routing when direct P2P connections are NAT-restricted.
- **Rejoin Stability**: Fixed dropped peer rejoin logic ported from BBSC 0.0.2.
- **Public & Private Servers**: Choice between public match server (`play.seamlesshunt.com`) and Tailscale VPN.
- **60 FPS Multi-Hunter Lock**: Enforces 60 FPS in multiplayer while leaving solo campaign uncapped.
- **Automated Save Backups**: Automatic timestamped backups to `user/coop-backups/` before each session.

---

### 6. Packaging & Release Infrastructure
- **Clean `.zip` Pipeline**: Completely removed `.tar` archive creation; standard `.zip` files generated with clean forward-slash entries.
- **Process Lock Management**: Automatic detection and termination of locking processes on `dist/bbport-windows`.
- **Automated Unpacking**: Automatically unzips fresh build to `dist/bbport-windows` to verify pristine runtime state.

---

### 7. Verification & Automated Test Status
- `test_launcher_ray_tracing.py`: **5/5 passed**
- `test_coop.py`: **24/24 passed**
- `test_launcher_updates.py`: **8/8 passed**
- `test_patches.py`: **51/51 passed**
- `test_dlss_model_settings.cpp`: **All tests passed** (EffectiveReflexMode, auto-promotion, RuntimeStatus metrics, staleness)
- QML Component Validation (`Main`, `HomePage`, `SettingsWorkspace`, `CharacterPage`, `CharacterInfoModal`): **0 errors**

---

### 8. DLSS Review Post-Audit Fixes & Live Hardware Verification (2026-10-26)
- **DLSS-G ABI 2 Native Bridge**:
  - Upgraded DLSS bridge interface to ABI 2 supporting Frame Generation lifecycle, parameter propagation, and swapchain recreation callbacks.
  - Verified on NVIDIA RTX 4090 (driver 621.01): native DLSS-G 2x active at 4K 120 FPS output, DLSS 4.5 Model M selected, zero FSR fallback, zero old-bridge warnings.
- **Unified Reflex Low Latency Coupling**:
  - Enforced coupling policy where DLSS Frame Generation requires effective Reflex On minimum (preserving Boost).
  - Integrated live latency telemetry querying `vkGetLatencyTimingsNV` (measured at 9.5–12.7 ms frame-start to present latency).
- **Bounded Lock-Free Runtime Status Channel (`BbSettings::RuntimeStatus`)**:
  - Real-time telemetry tracking active upscaler, quality preset, DLSS model, upscaler problems, FG provider, multiplier, fallback reason, effective Reflex, forced Reflex, measured latency in ms, render/present FPS, and HDR swapchain.
  - Integrated into in-game ImGui overlay (`bbport_overlay.cpp`).
- **Ray Tracing Prototype Isolation & Scalar History Clamping**:
  - Isolated reflection prototype from shadow mask pass to prevent corrupting directional moon shadows; disabled unsafe UI controls with clear hints.
  - Extended scalar history clamping to checkerboard-unsampled pixels using same-depth neighbors in `rt_filter.comp`.
  - Added bounded highlight shoulder to HDR tonemapper in `post_process.frag`.
- **Hunter's Atlas Bundled Release & In-Game Lamp Travel**:
  - Packaged 16 pre-compiled area maps and vector art directly into `dist/bbport-windows/atlas/`.
  - Verified live in-game native lamp travel executing on the main game thread (`queued to 2402950`) without stalling or crashing.
- **Distribution Package Audit**:
  - Built pristine release archive `dist/bbport-windows.zip` (321,505,186 bytes / 306.61 MiB, SHA-256 `fefdaed8a92a894c90548a4df98a2f9b77122d4e420ec7da6272404a240d32e4`).
  - Automated audit verification recorded in `bloodborne_pc/out/package-audit-verification.json`.
  - Verified clean exit code 0 via in-game PC Menu (`Quit Game`).

---

### 9. Priority 3 Quality Controls Implementation & Validation (2026-10-26)
- **Live Texture Mip Bias Offset (`dlss_mip_offset`)**:
  - Reused `TemporalUpscaler::SceneMipBias()` with dynamic querying of `BbSettings::Get().dlss_mip_offset` bounded to `[-2.0f, 0.0f]` (default `0.0f`).
  - Implemented live per-draw updates in `vk_rasterizer.cpp` so slider changes take effect immediately on subsequent frames without restarting the engine.
  - Added "DLSS texture mip offset" slider to the in-game ImGui overlay.
  - Verified environment override precedence via `BB_DLSS_MIP_OFFSET`.
  - Guaranteed `SceneMipBias() == 0.0f` on native/TAA rendering and non-DLSS passes.
- **Auto Models Selection Policy**:
  - Formalized GPU generation policy: Model K (preset 11) for RTX 20/30 (Turing/Ampere) to avoid non-FP8 performance penalty; Model M (preset 13) for RTX 40/50 with Model L (preset 12) for Ultra Performance; driver default 0 on unknown GPUs.
  - Preserved manual choices (J, K, M, L) and rejected deprecated presets E and F.
  - Verified via unit test suite `nvidia-gpu-test`.
- **Custom Ray-Traced Shadow Reach Override (`rt_shadow_reach_custom`)**:
  - Introduced `rt_shadow_reach_custom` bounded to `[0.0f, 150.0f]` in `bbport_settings.h` and `bbport_settings.cpp`.
  - Strictly preserved quality tier defaults across standard presets (`RtLow`, `RtMedium`, `RtHigh`, `RtUltra`).
  - Custom reach applies only when `ray_tracing == RtCustom` and `rt_shadow_reach_custom > 0.0f` (clamped to `[1.0f, 150.0f]`). Setting `0.0f` cleanly delegates back to the shadow tier default.
  - Added "Custom shadow distance" slider in in-game overlay with dynamic `Default (X m)` label when $\le 0.0\text{ m}$.
  - Maintained 100% backward compatibility for legacy `rt_shadow_reach` migration.
- **Unit Test Coverage**:
  - Added test cases in `test_dlss_model_settings.cpp` and `test_rt_settings.cpp` covering parsing, clamping, persistence, tier preservation, custom overrides, and environment precedence. All tests passed.
- **Distribution Package Audit (v3.2.1)**:
  - Rebuilt pristine release archive `dist/bbport-windows.zip` (321,507,050 bytes / 306.61 MiB, SHA-256 `9b484407e480df925f74cd7690b4125557638f9996f804047c99b0b7a5cea906`).
  - Automatically unzipped into `dist/bbport-windows/` preserving user save data and custom settings.
  - Recorded verification hashes in `bloodborne_pc/out/package-audit-verification.json`.

