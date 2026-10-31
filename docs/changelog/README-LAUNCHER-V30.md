# SunBros Bloodborne launcher guide

Updated **2026-10-26** for the current 3.x source. The filename retains the v3.0 UI milestone; it is not a separate version authority. Package versions come from build metadata. Based on Jgamrot 2.1 and BBSC 0.0.2.

## Start and configure

Extract the entire distribution, open **Bloodborne.exe**, select your decrypted game dump and save folder, then choose Offline, Online or Co-op. **Play Bloodborne.exe** uses the saved play route. Game assets are not bundled.

The launcher includes a Hunter profile, trophy archive, avatar selection and settings/log workspaces. The Home capsule describes **requested** features and a **target** FPS. Use the in-game overlay for runtime results.

| Visuals tab | Main controls |
| --- | --- |
| Display & frame rate | Output resolution, fullscreen/window mode, monitor, **HDR output**, FPS target, frames ahead and presentation mode. |
| Upscaling | Upscaler, quality/model selection and sharpening. |
| Frame generation | Provider, multiplier, fit to display and NVIDIA Reflex. |
| Ray tracing | AO/moon-shadow tiers and Custom options. Reflections/local-light shadows remain unavailable. |
| Image effects | Game AA, SSAO, motion blur, depth of field and other effects. |
| Video memory / Overlay | Memory settings, FPS and diagnostics. |

Save settings before launching. Some engine settings support live changes in the in-game PC menu (`Insert` / `L3+R3`); do not assume every launch-time setting can be changed live.

## HDR with frame generation

1. Enable Windows HDR on the monitor used by the game.
2. Enable **Visuals → Display & frame rate → HDR output**.
3. Select DLSS Frame Generation in **Visuals → Frame generation**, using 2× on a supported RTX 40-series card. Keep Auto model selection initially.
4. For a diagnostic run, disable **Fit frame generation to the display** so the display-refresh policy cannot suppress otherwise valid generation. Re-enable it later if desired.
5. Save, launch and inspect logs plus runtime counters.

Output is **BT.2020 / ST 2084 PQ with 10-bit RGB channels**. FG inputs and overlay composition stay SDR, followed by one final output conversion. Current brightness uses a fixed 600-nit shoulder knee and 1000-nit ceiling; it does not target a 1600-nit OLED peak.

Expected diagnostics include:

```text
Presentation color: HDR10 PQ (10-bit), final conversion after frame generation and overlay; rendered/generated/HUD inputs remain SDR
Frame generation: first successful DLSS evaluation pair, 1 generated frames (presentation counted separately)
```

The first message identifies output mode; the second identifies successful evaluation recording. The overlay's successful/generated/presented counters distinguish output stages. Capability messages alone do not prove generated output or physical display scanout. The first combined HDR+DLSS 2× run on RTX 4090 exited cleanly; repeated toggle/resize, fallback, pacing and physical color checks remain open.

## DLSS, Reflex and RT controls

| Control | Meaning |
| --- | --- |
| DLSS Auto | K on RTX 20/30; M on RTX 40/50, except L for Ultra Performance; runtime default for unknown generations. |
| Manual model | J, K, M, L or runtime default. Old E/F presets are deprecated/rejected. |
| DLSS mip offset | In-game slider -2.0…0.0; `BB_DLSS_MIP_OFFSET` overrides. Adds to DLSS ratio-based bias. |
| FG multiplier | Hardware/runtime dependent; RTX 4090 evidence covers 2×. 3×/4× require supported RTX 50 hardware. |
| Reflex | Off / On / On + Boost. DLSS FG requests at least On, preserving Boost, subject to driver support/acceptance. |
| RT Custom | Half-resolution moon shadows and custom reach. Reach 0 uses tier default; positive values clamp to 1–150 m. |
| Reflections / secondary lights | Unavailable; retained settings do not implement the missing rendering paths. |

Reflex frame-start-to-present marker intervals are not input-to-photon latency. Half-resolution shadows and PGO have no fixed measured performance gain in the current evidence.

## INI example

`bbport.ini` uses flat keys; the example is a diagnostic request, not a default preset. Prefer the launcher for monitor, window and FPS preferences.

```ini
upscaler=dlss
dlss_model=auto
frame_gen=dlss
frame_gen_multiplier=2
frame_gen_fit_display=0
reflex=boost
hdr=1
ray_tracing=off
rt_reflections=0
rt_secondary_lights=0
```

Effective settings can also be affected by saved launcher preferences and environment overrides. Check the startup log's settings path and active values.

## Atlas and co-op

Atlas runtime assets are in `atlas/maps/` and `atlas/art/`; the generator is in `tools/atlas-generator/`. The HDR+FG testing archive has 20 map files and 7 art assets; the runtime reports 16 registered areas. Enable the map through settings and toggle it with `M` or the configured controller combination. Lamp travel is opt-in.

Co-op uses BBSC 0.0.2, with public-server or private/Tailscale configuration. Peers need matching versions. Game simulation is capped at 60 FPS in co-op; generated frames do not raise the simulation rate. Save backups are created in `user/coop-backups/` before sessions. The current testing package omits a custom co-op server and uses the BBSC fallback.

## Troubleshooting and validation

| Symptom | Check |
| --- | --- |
| No generated frames | Provider support, actual ABI 2+ DLLs, first-success message, inactive/fallback reason and display-fit suppression. |
| HDR unavailable or looks wrong | Selected monitor, Windows HDR, active HDR10 output log, overlay/highlights, GPU output mode and display calibration. |
| FSR appears after requesting DLSS-G | Read the retained fallback cause; initialization and a dropdown selection do not establish successful DLSS evaluation. |
| Atlas missing | Runtime `atlas/` directories must be present; the development `ATLAS/` tree is not the package layout. |
| RT capture-full warning | Read the separate slot/capacity/reserve counts. The recovery run has 42,278 reserve exclusions; keep character reserve intact when tuning RT-only capacity. These omit RT geometry. |
| Rendering hitches | The recovery run has one startup stall and frames up to 383 ms. Capture route/loading context and CPU/GPU timing; the cause is not established. |
| Unsure which build ran | Log's settings/Atlas paths, package hash, native binary and bridge ABI. |

No minimum/recommended GPU performance table is certified here. Hardware capability, installed Vulkan driver and selected effects determine support. Settings tests and the offscreen GPU test do not cover all gameplay, QML, network or display behavior.

The verified 3.2.6 recovery ZIP passes package/native/launcher/ABI checks. Its complete saved run includes startup and 18 min 46 s telemetry with concurrent HDR/DLSS 2×, median accepted 60/120 rates and normal quit. Keep `BB_VIDEOOUT_BACKPRESSURE=0`. RT reserve exclusions and occasional hitches remain; the earlier gated GPU fault is unproven at root cause.

[Features](../../features.md) · [Build/tests](../../build.md) · [Release notes](../../Release_Notes.md).

## Full logs and recovery diagnostics

Launch the 3.2.6 baseline with process environment `BB_FPS_LOG=1` and `BB_VIDEOOUT_BACKPRESSURE=0`; these are environment variables, not new INI keys. Verify `VideoOut admission: mode=observe only`, flag zero and zero gated calls. The first default-on 3.2.5 test lost the GPU; the gate remains opt-in pending hardware investigation.

The complete log is **`<saves folder>/last_run.log`**, with previous-run rotation to `last_run.1.log`, `last_run.2.log`, and so on. The screen view keeps only 350,000 characters; Copy Log copies that tail. Attach the saved file for startup-to-quit diagnostics. The saved stdout currently omits the UI-generated exit-code footer, so retain that separately when needed.

[Latest changelog](changelog-2026-10-27.md).
