# SunBro's Edition: Bloodborne PC feature catalog

Updated **2026-10-31**, for **4.2.8** (the bells after seamless co-op are normal bells again), **4.2.7** (Save settings and a tidier Visuals page; Download BBSC on the Co-op page), **4.2.6** (seamless co-op hosting: the co-op server ships again), **4.2.5** (first start set for your PC) and **4.2.4** (★ DLSS 4 / ★ DLSS 5 preset suggestions; DLSS 5 stays off and says why when ReShade won't load it), on top of **4.0.0** (major release: save backups, HDR brightness controls, DLSS 5 neural rendering through the community route, FSR 4.1.1 on Windows, FSR 1 output upscale; on top of 3.4.0's DLSS roadmap). Based on Jgamrot 2.1 and BBSC 0.0.2. The supplied 3.2.9 renderer run has zero capture exclusions; the user confirmed the corrected co-op UI. Identical-route performance, genuine VRAM-pressure recovery and jump-distance acceptance remain pending. See [build guide](build.md) and [current changelog](docs/changelog/changelog-2026-10-29-4.0.0.md).

## Capability overview

Fixed 60/90/120/144 FPS presets correct running-jump horizontal momentum against the 30 FPS decay rate, with executable/data guards and an opt-out (`BB_RUNNING_JUMP_FIX=0`). Included in the final 3.2.9 package; gameplay-distance validation remains pending. Uncapped correction dynamically scales momentum decay via `0.95 ** (30 * dt)` using runtime measured simulation delta (`BB_JUMP_DT=1`). Physical landing distance equivalence still requires gameplay benchmark comparison.

| Area | Implemented | Remaining qualification |
| --- | --- | --- |
| Launcher | Qt Quick / PySide6 Command Center (`HomePage`), `VisualsStudio`, `DossierWorkspace` (6-axis `StatRadar`, trophy filters), `MultiplayerWorkspace` (`CoopSetupPanel`), `PreferencesPage`, HD Texture Pack builder, save backups (manual, automatic after play, restore with rollback), FSR 4.1.1 download, and opt-in background updater. | Home capsule describes requested settings, HD Texture Pack state, and target FPS. |
| DLSS SR | ABI 3 bridge (SR, FG; DLSS 5 entry points reported unsupported), Auto/manual models per quality mode, mip bias −1 by default and mip-offset control. DLSS 5 neural rendering through the player's own ReShade + dlss5-bridge + renodx-dlss5 (community route), with the add-on's look settings in the launcher. | RTX 4090 at 4K measured in 4.2.0 (every tier with K, M and L, frame generation, DLSS 5; [results](docs/dlss-4.2.0-comparison.md)); other GPUs not tested. |
| Frame generation | DLSS-G and FSR fallback, display fitting, HUD-less inputs and output counters. | RTX 4090 HDR + DLSS 2× ran for 18 min 46 s of telemetry; transitions, fallback and other GPUs remain open. |
| HDR | BT.2020/PQ, 10-bit RGB output after FG and overlay composition; paper white, peak brightness (to 4000 nits, or the display's) and highlight boost settings. | SDR-derived content; the new levels are GPU-tested, not yet checked on an HDR display. |
| Ray tracing | RTAO, moon shadows, half-resolution option and custom reach. | Reflections/local-light shadows unavailable; visual/performance A/B pending. |
| Reflex | Off / On / Boost, DLSS-FG coupling, publication-before-sleep ordering and queue/wait diagnostics. | Experimental admission blocking is off by default after a failed gated run; marker intervals are not input latency. |
| Atlas | Bundled maps/art, live position, opt-in lamp travel, background geometry preparation, viewport culling and reused upload buffers. | The latest drawing optimizations require identical-route testing. |
| Co-op | BBSC 0.0.2 relay/rejoin integration, public/private modes and backups. | Matching peer builds required; Chalice synchronization remains a roadmap item. |

## 4.2.7 Save settings; Download BBSC on the Co-op page

- Visuals > **Save settings** stores what the Visuals page sets (`MY_SETTINGS_INI` and `MY_SETTINGS_APP` in `bbport_launcher_win.py`) in the launcher settings (`my_settings`), loaded at every launcher start. A preset stays that preset; anything else is the **Custom** pill. The tuned presets have their own line after `RTX 4090 | RTX 4080` (4080 greyed out), each with a hover "?"; HDR and the shortcuts sit in a right column.
- Co-op setup has two steps, Account and Connection; Connection starts the game (Play co-op). Its **connection details** check BBSC, the firewall rule, the network and the host's ports, and show BBSC's relay, join and session events from the newest session; **Open ports (admin)** makes the firewall rules with one administrator prompt. **Download BBSC 0.0.2** (again) on the Account step calls `coopSetup`, lost in the 4.1.0 launcher rewrite. Downloading the client again keeps `bbsc/logs`, `bbsc/save-backups` and `bbsc/captures` (`CLIENT_KEEP`). [Changelog](docs/changelog/changelog-2026-10-30-4.2.7.md).

## 4.2.6 Seamless co-op hosting: the co-op server ships again

- The package carries `bin\coop-server` again: the shadNet server seamless co-op hosts run, with the STUN fix for this port's P2P signaling. 4.2.5 shipped without it, so hosts ran BBSC's `shadnet.exe` and guests never joined (`OnRoomTimeOut`). `package.sh` now stops without it and `scripts/build_dist.py` builds it when missing (`BB_PACKAGE_NO_COOP_SERVER=1` opts out). [Changelog](docs/changelog/changelog-2026-10-31-4.2.6.md).

## 4.2.5 First start set for your PC

- A new install (no `bbport.ini`, no saved settings) creates `bbport.ini` from this PC once the launcher's GPU check reports: the primary display's resolution as the output, DLSS on an NVIDIA RTX card and FSR 3.1 otherwise, and the ★ suggested preset. The setup wizard says what was set; the player can pick another preset or change anything, and later starts keep their choices. Before, every new install got one PC's defaults (3840 × 2160 output, DLSS). [Changelog](docs/changelog/changelog-2026-10-30-4.2.5.md).

## 4.2.4 DLSS 4 and DLSS 5 preset suggestions; DLSS 5 and ReShade's app list

- On a GeForce RTX 40 / 50 card with 12 GB or more, the graphics presets mark **★ DLSS 4** on Remastered (4K output held 60 → 120 at about 8.7 ms GPU on an RTX 4090, the sharpest picture) and **★ DLSS 5** on DLSS 5 ready (2560 × 1440 output on a 4K display, 59–60 FPS at 14–15 ms), the second only where the card is offered DLSS 5. Other cards keep one ★ suggestion.
- DLSS 5 with its files in `bin\` but `bin\bb-probe.exe` missing from `C:\ProgramData\ReShade\ReShadeApps.ini` stays off: `run.py` sets `BB_DLSS5_PROBLEM`, the game logs `DLSS 5: off - ReShade is not set to load for bin\bb-probe.exe`, and the launcher warns. Before, the game logged "DLSS 5: on (community bridge)" while the add-ons never loaded. [Changelog](docs/changelog/changelog-2026-10-30-4.2.4.md).
- 4K with NR upscaling, measured again: DLSS Performance held 60 → 120 with ray tracing Ultra and DLSS 2×; Balanced and Quality missed 60, and matched screenshots were no sharper than 2560 × 1440 output.

## 4.0.0 Major release: save backups, HDR brightness, DLSS 5 neural rendering, FSR 4.1.1, FSR 1 output upscale

4.0.0 is the 3.4.1 follow-up renamed; 3.4.1 was never published.

- HDR output levels: `hdr_white_nits` (paper white, 80–400 nits or Windows' SDR content brightness), `hdr_peak_nits` (400–4000 nits or the display's; the shoulder starts at 60 %) and `hdr_highlight_boost` (0–1 of the 6.5× expansion), with `BB_HDR_WHITE` / `BB_HDR_PEAK` / `BB_HDR_BOOST` and three launcher rows under HDR output. Defaults are the old fixed levels (120 / 1000 / 1.00). HDR guide.
- DLSS 5 neural rendering through the community route: the `dlss5` switch in Visuals > Neural rendering (DLSS 5) keeps ReShade's layer when the player's own `nvngx_dlssnr.dll`, `dlss5-bridge.addon64` and `renodx-dlss5.addon64` are in `bin\`, and PLAY writes the NR look rows (upscaling, intensity, preset, style, local structure / tone, skin structure, automatic mask, UI correction) to `[RenoDX.DLSS5]`. DLSS 5 ready depends on the output size (4K → 2560 × 1440 output, Cinematic, local structure 2.00: 60 → 120 on an RTX 4090). Nothing third-party is shipped or downloaded. [Player setup guide](docs/dlss5-setup.md) · Control map and results.
- A minimized game window no longer leaves the presenter on a 0 × 0 swapchain (frame generation at 0 generated frames, +15–20 ms latency); the launcher no longer hangs on Exit to desktop (game output reaches the log in 100 ms batches).
- A presentation image that can't be allocated no longer stops the game: the frame keeps its previous image (frame generation without its HUD-free copy, one frame without the HDR10 encode). With a previous image it never stops: it backs off (1, 2, 4… frames, up to 2 s) and frame generation pauses meanwhile. `BB_TEST_FRAME_ALLOC_FAILS=N[@M]` injects failures for testing.
- DLSS 5 Detail (`dlss5_detail`, Structure Intensity, default 0.50) and Colour change (`dlss5_tone`, Tone Intensity, default 0.00: the game's own grading), with `BB_DLSS5_DETAIL` / `BB_DLSS5_TONE`, for the built-in DLSS 5 route; `bbport.ini` only (no launcher row).
- Output below the display (e.g. 1440p on 4K) is upscaled with AMD FidelityFX FSR 1 EASU instead of a bilinear stretch: `bbport.ini` `present_upscale = easu | linear` (default `easu`, only when the output is smaller) and `present_rcas` (extra FSR RCAS sharpening in stops, default 0 = off, e.g. 0.5), with `BB_PRESENT_UPSCALE` / `BB_PRESENT_RCAS`. Equal sizes are unchanged. Launcher: Settings > Visuals > Display & frame rate, rows "Upscale to the display" (FSR 1 EASU / Bilinear) and "Extra sharpening after upscale" (Off, 2.0, 1.0, 0.5, 0.25 stops). Details and the in-game A/B.
- DLSS texture mip bias defaults to −1 on top of log2(render ÷ output), as NVIDIA advises: finer texture detail, no measured GPU cost; `dlss_mip_offset=0` keeps the older look.
- Custom output sizes work end to end: any `output_res=WxH` from 256x144 to 7680x4320 (an odd side rounds down to even; it used to fall back to 1080p) and `BB_OUTPUT_RES` over the file; the launcher lists 2880 × 1620 and 3200 × 1800.
- Startup logos, title and loading menus above 1080p: their bitmaps (low-resolution artwork, magnified 2x-4x at 4K) are sampled with Catmull-Rom instead of bilinear where magnified, for slightly crisper edges and smooth curves; 1080p output is unchanged, `BB_UI_BITMAP_FILTER=linear` keeps bilinear.
- Save backups in the launcher (Settings > Game & Saves > Save backups): Back up now (with an optional label) zips `savedata` into `<saves folder>\save-backups`; each backup lists its date, label, kind (manual, automatic, before restore), size, file count and characters; Restore backs up the current saves first and puts them back if anything fails; Delete and Restore confirm in the row; Open backups folder. "Back up saves after playing" (on by default) keeps the last 10 automatic backups; manual ones are never deleted. Buttons that touch the saves are blocked while the game runs.
- FSR 4.1.1 on Windows (experimental) through the fsr4vk provider DLL (`amd_fidelityfx_upscaler_vk.dll` in `binsr4vk`, or `BB_FSR4VK_DIR`), loaded at run time; the Linux replay (`fsr4_411` assets, `VK_VALVE_shader_mixed_float_dot_product`) is unchanged and preferred where it can run. Launcher: Settings > Visuals > Upscaling > "Download FSR 4.1.1". On NVIDIA it is limited to 1920 × 1080 output (fsr4vk's 2160 tier loses the device; FSR 3.1 is used above that, `BB_FSR4VK_ANY_SIZE=1` overrides). DLSS-G and FSR 3.1 frame generation work with it. `BB_FSR4VK=0` disables it.
- Results: [4.0.0 changelog](docs/changelog/changelog-2026-10-29-4.0.0.md), follow-up results, present upscale A/B, FSR 4.1.1 through fsr4vk, DLSS 5 neural rendering.

## 3.4.0 DLSS roadmap: GPU time, a DLSS 5 ready preset, DLSS through Streamline

- Render targets the game reads back as buffers are tiled into game memory in one pass, and DLSS sharpening writes the UI image directly: about 1.6 ms less GPU time per frame at 4K DLSS Quality with Ultra ray tracing (RTX 4080 SUPER).
- "DLSS 5 ready" preset (1440p output, DLSS Quality, ray tracing Low, DLSS 2× at a fixed 60) on cards offered DLSS 5; a saved DLSS 5 request at another rate shows a warning.
- Experimental `BB_DLSS_BACKEND=streamline`: DLSS Super Resolution through NVIDIA Streamline 2.14.16 (`bin\streamline`); frame generation falls back to FSR 3.1 on it. NGX stays the default.
- Fewer shader-compile hitches: boss-fight pipelines added to the shipped catalog, and new effect and object pipelines built in the background (toggle bit 61). Worst case (nothing pre-built, empty driver cache): Cathedral Ward's worst frame 250 → 18 ms.
- Results: roadmap results.

## 3.3.3 DLSS model per quality mode and DLSS 5 kept off

- The DLSS bridge sends the selected model only for the active quality mode (manual L no longer also applies at Quality); Auto is unchanged.
- The launcher disables ReShade's Vulkan layer on every start while the DLSS 5 community bridge is paused; the DLSS 5 reasons no longer name a missing guide.
- A missing `nvngx_dlssg.dll` is reported at start; frame generation still falls back to FSR 3.1.
- RTX 4090 checks T1–T6 pass: DLSS test results.

## 3.3.2 HD Texture Pack setup fix

- The launcher builds the HD Texture Pack by itself once all its downloads are in, never while the game runs.
- Browse works for the HD Texture Pack folder and its downloads folder.
- An `hd-pack-downloads` folder beside the launcher's folder is found without any setting.

## 3.3.1 Remastered quality and FPS target fixes

- Remastered explicitly applies DLSS Quality, Ultra ray tracing with object motion, highest model detail, screen-space reflections, 16x filtering, and the installed HD Texture Pack. Keeps the output resolution and cosmetic choices.
- Selecting Remastered restores a 60 FPS base with DLSS 2× and Reflex, clears conflicting advanced FPS overrides and resets a manual frame cap. Home distinguishes base/output targets and exposes a remaining advanced override. Actual generated output requires gameplay confirmation.
- Prepared background updates survive launcher restarts and are offered for installation with confirmation when background downloads are enabled.
- Packaging cleans only the requested package's staging folder.
- Title presentation follow-up: fill the original artwork's baked side padding on 16:9 screens using a generated movie layer; apply smoother filtering to movie-only bitmap draws. Keeps menu commands and gameplay sampling intact. The title artwork is uniformly zoomed with a small top/bottom crop.

## 3.3.0 Command Center launcher, HD Texture Pack, 16x filtering and ray-tracing views

- Launcher Command Center: modular QML workspaces (`HomePage`, `VisualsStudio`, `DossierWorkspace` with `StatRadar`, `MultiplayerWorkspace` with `CoopSetupPanel`, `PreferencesPage`), `DepthCard` 3D tilt effects, and opt-in background update downloading (`download_updates`).
- HD Texture Pack: the launcher downloads three Nexus Mods texture mods on the player's PC and builds one picture-only pack (no game changes). Needs about 45 GB free while installing and a 10 GB graphics card.
- 16x anisotropic filtering by default and a Remastered graphics preset (`VisualsStudio` and `SettingsWorkspace`).
- Ray tracing: debug views and compare split, stronger AO controls, ray-traced-only moon shadows and the game's depth as the alpha test for see-through geometry.
- HDR is the presentation-time conversion only; the game log also reports Windows' SDR content brightness and the display's peak.
- DLSS 5 readiness is present but paused (greyed out).

## 3.2.10 uncapped jump decay and vendor-partitioned catalog

- Horizontal running-jump momentum scaling at uncapped frame rates dynamically evaluates 0.95 ** (30 * dt) via hooked vmulps operand displacement redirection, preserving original vector constants and on-disk binary integrity. Frame delta is sampled from the game manager with high-precision QPC fallback clamped between 1/480 s and 1/20 s. Emits interval telemetry every 10 seconds by default (silenced with BB_FPS_LOG=0).
- Shader pre-build catalog is partitioned by GPU vendor PCI ID (NVIDIA 0x10DE, AMD 0x1002, Intel 0x8086), preventing cross-vendor translation stalls. User caches are stored in vendor-isolated directories (user/cache/CUSA03173/<vendor>/) with automatic legacy migration and invalidation upon GPU architecture switch. Cold-start profile copy fix eliminates spurious size mismatch warnings.

## 3.2.9 renderer maintenance

Atlas builds a floor-triangle spatial index on its background worker, selecting visible geometry without changing draw order or fog/height checks. Its Vulkan backend retains mapped per-frame upload buffers with growth headroom; non-coherent flushes, frame lifetimes and texture-upload synchronization remain in place.

Texture/buffer garbage collection and periodic RT retirement already existed. RT now also samples current device-wide usage/budget, enters pressure at 90% and exits below 85%, retires at most 128 eligible cold entries per sweep, and restricts new static allocations during pressure. Recent entries and dynamic-character exceptions remain protected. Retired resources use deferred GPU destruction; reclaimed accounting is not instantaneous free VRAM. Compare scene coverage under pressure.

The pipeline cache prunes invalid key records at startup, retains deliberately deferred motion variants, and checkpoints compatible driver data in the background for repeat-run reuse. Controlled shutdown drains accepted writes. Hard termination may interrupt recent writes. New shader/pipeline variants still require compilation; these changes do not eliminate all first-visit hitches. `BB_FPS_LOG=1` exposes slow compilation and overlay draw counts for comparison.

Native/CPU and RTX 4090 offscreen GPU checks passed. Actual gameplay improvements, genuine VRAM-pressure behavior and broader hardware coverage remain unverified.

## Rendering and ray tracing

The native runtime translates the game's GCN shaders and command stream into Vulkan rendering. Output resolution, aspect ratio, frame-rate target, image effects and memory controls are exposed in the launcher. Pipeline caching reduces repeated compilation work; it does not guarantee stutter-free traversal.

RTAO and directional moon shadows have Off / Low / Medium / High / Ultra / Custom presets. Torch/lamplight retains the game's existing shadows.

| Control | Behavior |
| --- | --- |
| `rt_shadow_half` | Custom override for half-resolution moon tracing; other presets use tier defaults. GPU savings depend on scene and hardware. |
| `rt_shadow_reach_custom` | Custom-only distance: 0 uses tier default; positive overrides clamp to 1–150 m. |
| Shadow tier distances | Low 6 m; Medium/High 15 m; Ultra 40 m. |
| `rt_ao_strength` | Adjusts AO contribution. |
| RTG-5 filtering | Scalar occlusion/shadow-history clamp, including unsampled checkerboard pixels with valid same-depth neighbors. Residual trails require capture testing. |
| `rt_reflections` | Disabled prototype, including old INI/environment requests; no production reflected-radiance composition. INI key kept; no launcher or in-game control since 4.2.1. |
| `rt_secondary_lights` | Not implemented: no dynamic torch/lantern extraction. INI key kept; no launcher or in-game control since 4.2.1. |

Core stages include instance/BVH updates, tracing, filtering and application. The filter clamps scalar history, rather than scene color. Settings availability does not imply that the disabled prototype features render.

## HDR output: BT.2020, PQ and 10-bit RGB

The HDR swapchain uses **`VK_FORMAT_A2B10G10R10_UNORM_PACK32`** and **`VK_COLOR_SPACE_HDR10_ST2084_EXT`**: 10 bits per R/G/B channel, with 2 alpha bits. The shader converts linear BT.709 primaries into BT.2020 and encodes ST 2084 PQ.

The integration keeps scene, HUD-less and FG color buffers SDR RGBA8. For every rendered/generated image it letterboxes into an SDR attachment, composites the actual PC overlay/Atlas/FPS, then performs one final floating-point HDR conversion directly into the 10-bit swapchain. It avoids storing PQ in an 8-bit intermediate and keeps SDK color contracts unchanged. Plain SDR and SDR-on-HDR desktop compensation remain supported.

This is SDR highlight expansion into HDR output. Converting primaries does not recover native wide-gamut scene information, and a 10-bit output does not remove quantization already present in SDR inputs.

Current `ToneMapBloodborneHDR` constants are a 120-nit scale, 600-nit shoulder knee and asymptotic 1000-nit ceiling. The scale is not a user paper-white control. Neutral white measured **742.757 nits by decoding GPU readback**; physical panel brightness was not measured. There is no current 1600-nit setting, automatic panel-peak selection or user calibration control.

## Upscaling, frame generation and diagnostics

### DLSS models and mip offset

The Windows bridge is built against the local NVIDIA SDK and checked for ABI 3 and its SR, Frame Generation and neural-rendering (DLSS 5) entry points before packaging; the renderer still loads ABI 1/2 bridges. Runtime hardware support and successful evaluation remain separate checks.

| Auto policy | Selected model |
| --- | --- |
| RTX 20 / 30 | K (preset 11). |
| RTX 40 / 50 | NVIDIA's defaults: K (preset 11) for DLAA, Quality and Balanced; M (preset 13) for Performance; L (preset 12) for Ultra Performance. Since 4.2.0; before, M in every mode but Ultra Performance ([measurements](docs/dlss-4.2.0-comparison.md)). |
| Unknown GPU generation | Runtime default (preset 0). |

This is project policy, not a universal performance ranking. Manual J/K/M/L/default choices are supported; deprecated E/F are rejected. The bridge sends the chosen model only for the active quality mode; other modes keep the driver's choice. `dlss_mip_offset` is bounded to -2.0…0.0 and adds to the render/output-ratio bias only for DLSS. `BB_DLSS_MIP_OFFSET` has precedence. Native/TAA use zero scene bias; other active upscalers retain their base ratio bias.

### Frame generation

`frame_gen`, `frame_gen_multiplier` and `frame_gen_fit_display` control the request. DLSS-G 2× was observed on RTX 4090; 3×/4× require supported RTX 50 hardware/runtime and were not tested here. The renderer has FSR 3.1 interpolation fallback and FSR 4 upscaling/shader paths; do not infer identical support from the labels.

HDR no longer suppresses FG. Display fitting can still suppress generation when unnecessary for the display refresh rate. HUD-less capture remains part of interpolation resource preparation.

Runtime status describes the latest attempt and distinguishes:

- Successful evaluation pairs by provider.
- Generated output count.
- Generated outputs accepted by the presentation path.
- Inactive and fallback reasons.

A failed/zero-output attempt clears stale activity. Automatic DLSS→FSR fallback retains its cause across successful FSR pairs; changing provider or successful DLSS recovery clears it. Accepted presentation counts do not establish physical scanout.

### Reflex and status

DLSS FG requests at least Reflex On; requested Boost is preserved. Availability and driver acceptance are checked separately. The current frame is published/notified to VideoOut before next-frame Reflex sleep; the producer copies its frame ID before transferring ownership. The wait runs outside the Reflex mutex and pending pacing IDs are invalidated during swapchain recreation.

**`BB_VIDEOOUT_BACKPRESSURE` defaults to off in 3.2.6.** Queue observation continues, while an explicit process environment value of `1` enables experimental dequeue admission when Reflex is active. The first gated 3.2.5 hardware run failed with GPU device loss/invalid write; the faulting command is unproven. Keep the tested value `0` for the baseline. The gate's requested 100 ms timeout does not make it a hard queue-depth guarantee.

With `BB_FPS_LOG=1`, five-second CPU handoff, Reflex pacing and admission reports separate queue/dispatch, API/semaphore and next-work waits. The complete recovery run has a 29.45 ms median VideoOut queue window average and 54.2 ms median of 37 Reflex marker averages. These are different measurements; workload and marker boundaries prevent a controlled physical-latency claim.

`BbSettings::RuntimeStatus` publishes bounded per-field atomics to the in-game overlay, with a 2000 ms stale threshold. It is not an atomic snapshot across every field. The launcher's Home capsule shows requested features and a target FPS, rather than measured runtime activity.

## Launcher, profile and gameplay

The Qt Quick launcher includes a gothic theme, artwork, custom controls, immediate startup, a Hunter Dossier and a 40-trophy archive with unlock information where available. Custom avatar selection supports a file dialog, path entry and automatic `user/avatar.*` discovery, with refresh across profile views.

Settings cover visuals, controls, game/save paths, online/co-op, mods/patches and system logs. Co-op account/server settings use one guided editor set while retaining search navigation. The logs view has horizontal/vertical scrolling. Full stdout/stderr is saved to **`<saves folder>/last_run.log`**, with numbered previous-run rotation. The QML view keeps only the last 350,000 characters and Copy Log copies that tail; attach the saved file to include startup. The saved stdout currently omits the launcher-generated exit-code footer. Save decoding supplies profile information when supported decrypted saves are available.

## Hunter's Atlas

The HDR+FG testing archive contains **20 map files, 7 art assets and the frozen Atlas generator** in `atlas/` and `tools/atlas-generator/`. A supplied runtime reports **16 registered areas**; this is not a contradictory file count. The source directory named `bloodborne_pc/ATLAS/` is not shipped as a verbatim development tree.

The map overlay supports player positioning, optional exploration/item displays and opt-in lamp travel queued to the main game thread. Selected travel and clean exits were observed; zero stalls or universal travel safety have not been measured.

## Multiplayer and runtime services

Offline mode, The Hunter's Dream online mode and BBSC 0.0.2 seamless co-op are separate choices. Co-op supports public-server or private/Tailscale configuration, relay fallback/rejoin changes and pre-session backups in `user/coop-backups/`. The launcher caps co-op game simulation at 60 FPS. Public-server availability and interoperability require live testing.

The native runtime also supplies memory/thread/synchronization services, AJM jobs and ATRAC9 audio decoding. These are part of the inherited port, not new HDR/FG functionality.

## Build and validation tooling

MSYS2 CLANG64 builds the renderer; MSVC builds the SDK bridge. ThinLTO defaults on in the Windows build; Clang PGO can generate atomic instrumentation profiles or use existing profiles. Profile execution counts are not timings; the older 10–15% performance claim lacks a controlled A/B benchmark.

The packaging wrapper creates ZIPs, filters game assets/local state, stages runtime DLLs and copies Atlas runtime assets. It reuses existing binaries/stage in some modes, so package freshness and CRC must be checked explicitly. ZIP hashes identify a particular build; archives are not guaranteed byte-reproducible. See [build.md](build.md).

Verified during integration: renderer build, `dlss-settings-test`, `rt-settings-test`, `nvidia-gpu-test`, and RTX 4090 `hdr-presentation-test` using actual shader SPIR-V. Vulkan validation layers were absent. The 3.2.6 build also passes `frame-admission-test`, `frame-handoff-test`, `reflex-handoff-test`, `motion-history-test`, `presentation-telemetry-test` and `dlss-settings-test`; CPU tests do not certify GPU/resource lifetimes.

## Historical 3.2.6 recovery evidence

| 3.2.6 recovery observation | Result |
| --- | --- |
| Complete saved run | Startup and 225 telemetry windows totaling 18 min 46 s; normal quit. |
| HDR / provider | HDR10 on, DLSS 2×; no FSR fallback. |
| Accepted presentation rates | Median 60 game images / 120 total images per second; physical scanout is unmeasured. |
| Generated / accepted generated | Final sampled totals 65,951 / 65,936; 13 explicitly unpresented outputs and zero failed presents. |
| Recovery policy | All reports observation-only, flag zero, zero gated/blocked calls and no admission/Reflex timeouts or errors. |
| GPU / resource-table errors | No device loss or unmapped SRT warnings in the full recovery log. The earlier 3.2.5 fault's root cause remains open. |
| RT capture | 42,278 character-reserve exclusions in three windows; zero slot/total-capacity exclusions. |
| Pacing | One startup rendering-stall message and a 383 ms maximum reported frame; steady medians do not imply hitch-free play. |

Capture reports split slot, vertex and reserve exclusions; periodic FG telemetry separates evaluation/output from accepted presentations without needing `BB_FPS_LOG`. Since 3.2.7, `BB_RT_CAPTURE_BUDGET` independently controls RT vertex capacity (1–64 Mi vertices, with the base capacity as its floor), preserving the 15% character reserve. Defaults remain 4 Mi base / 12 Mi RT. Reserve exclusions omit RT geometry; RT build-budget counters are a different limit.

## Latest gameplay evidence and acceptance

The supplied 3.2.8 Atlas run contains 22 min 1 s of telemetry: zero capture exclusions at 16 Mi vertices, 85,333 generated/accepted outputs, zero unpresented outputs or failed presents, and no device-loss/SRT fault markers. No measured PresentImage call reaches 50 ms; 36 smaller overlay calls of 20–43 ms and startup intervals of 134/182 ms remain. These observations apply to that package, not the later 3.2.8 co-op/setup source changes or the new 3.2.9 renderer maintenance.

**Next:** compare 3.2.9 on the same route/settings and perform a separate long-session VRAM-pressure run. Keep admission blocking off. HDR calibration, transition/fallback validation and broader hardware testing remain open. [Release notes](Release_Notes.md) · [October 27 changelog](docs/changelog/changelog-2026-10-27.md).
