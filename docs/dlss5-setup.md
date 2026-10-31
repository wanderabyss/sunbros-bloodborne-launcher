# Setting up DLSS 5 neural rendering yourself

Updated **2026-10-29** for **4.0.0**. DLSS 5 neural rendering runs through a **community route**:
ReShade with two add-ons, plus NVIDIA's neural rendering runtime. **The port does not ship,
download or check any of these files**; you add them yourself, at your own risk. Without them,
everything else in the port works as usual and DLSS 5 stays off.

> NVIDIA has not released a DLSS 5 runtime that a Vulkan game like this one can call directly.
> The port's own DLSS 5 entry points therefore report "unsupported", and the route below is the
> only way to use it today. It is experimental.

## What you need

| | Needed | Notes |
|---|---|---|
| Graphics card | NVIDIA GeForce **RTX 40** (4080 / 4090 class recommended) or **RTX 50** | Neural rendering costs about 6–7 ms a frame at 1440p and 14–16 ms at 4K on an RTX 4090. |
| Driver | A current NVIDIA Game Ready driver | |
| Port | **4.0.0** or newer, with **DLSS** as the upscaler | The add-ons build on the game's own DLSS call. |
| [ReShade](https://reshade.me/) | **6.8 or newer, the build "with full add-on support"** | Tested: 6.8.0. Installed for Vulkan (a global layer under `C:\ProgramData\ReShade`). |
| dlss5-bridge add-on | `dlss5-bridge.addon64` (+ its `dlss5-bridge.cfg`) | From [NIGos/dlss5-bridge](https://github.com/NIGos/dlss5-bridge). Tested: 1.4.13-pre8. |
| renodx-dlss5 add-on | `renodx-dlss5.addon64` | From the [RenoDX](https://github.com/clshortfuse/renodx) project. Tested: v2.5. It holds the neural rendering look settings. |
| NVIDIA neural rendering runtime | `nvngx_dlssnr.dll` | NVIDIA's DLSS 5 runtime. Use a copy you are entitled to; the port does not say where to get one. |

## Where the files go

Everything goes in the package's `bin` folder, next to `bb-probe.exe` (the game itself):

```text
bbport-windows-4.2.0\
├── Bloodborne.exe                 (the launcher)
└── bin\
    ├── bb-probe.exe               (the game; this is the program ReShade must hook)
    ├── nvngx_dlssnr.dll           ← you add
    ├── dlss5-bridge.addon64       ← you add
    ├── dlss5-bridge.cfg           ← you add, or the bridge writes it on first start
    ├── renodx-dlss5.addon64       ← you add
    ├── ReShade.ini                ← ReShade writes it on first start
    └── reshade-shaders\           (may stay empty; no effects are needed)
```

The launcher checks for exactly three of them: `nvngx_dlssnr.dll`, `dlss5-bridge.addon64` and
`renodx-dlss5.addon64`. If any is missing, DLSS 5 stays off and the game says which.

## Step by step

1. **Close** the launcher and the game.
2. **Install ReShade** (the add-on support build). In its installer, choose
   this package's `bin\bb-probe.exe` (for example `bbport-windows-4.2.4\bin\bb-probe.exe`), then
   **Vulkan** as the rendering API. When it offers effect packs you can skip them all: the add-ons
   don't need any. This adds `bb-probe.exe` to ReShade's app list,
   `C:\ProgramData\ReShade\ReShadeApps.ini`. ReShade's Vulkan layer only loads into programs on
   that list, and every new package folder is a new path: add it again when you update.
3. **Copy** `nvngx_dlssnr.dll`, `dlss5-bridge.addon64` and `renodx-dlss5.addon64` into `bin\`.
4. **Bridge settings.** If you have no `dlss5-bridge.cfg`, start the game once with DLSS 5 on (steps
   5–6) and the bridge writes one with its defaults. Then make sure it has:
   - `vk_mirror=1`: hooks the Vulkan NGX entry points, which is how a Vulkan game's own DLSS is
     mirrored. Read once at start.
   - `synth=0`: the game provides real DLSS inputs, so the bridge's substitute (made from depth and
     optical flow, visibly worse) must stay off.

   The rest of the tested file: `synth_after=0`, `source=auto`, `ofa_grid=2`, `ofa_perf=20`,
   `mv_sign_x=0`, `mv_sign_y=0`, `vk_present=0`, `vk_sync=0`, `stage=3`, `mode=2`, `skip_game=1`,
   `flags=-1`, `subrects=1`, `reset_every=0`, `pixels=0`, `dred=1`, `skip_exe=1`, `unwrap=1`.
5. **Turn it on** in the launcher: **Settings > Visuals > Neural rendering (DLSS 5)** (or the
   **DLSS 5 neural** button on the Visuals page) and switch **DLSS 5** to **On**. The status line
   should list all three files as found and `bb-probe.exe` as listed in ReShade's app list. If
   `bb-probe.exe` isn't listed, DLSS 5 stays off (from 4.2.4): the launcher warns, and the game's
   log says `DLSS 5: off - ReShade is not set to load for bin\bb-probe.exe`. Earlier versions
   logged "DLSS 5: on" even though the add-ons never loaded.
6. **Pick settings that hold 60 FPS.** The easiest is the **DLSS 5 ready** preset (marked
   **★ DLSS 5** on RTX 40 and 50 cards with 12 GB or more; **★ DLSS 4** marks Remastered, the
   sharpest picture without DLSS 5):
   - up to 1440p output: your output, DLSS Quality, ray tracing High;
   - 4K: 2560 × 1440 output (upscaled to the display with FSR 1), DLSS Quality, ray tracing High,
     NR style Cinematic, local structure 2.00, NR upscaling off. This held 60 → 120 FPS with DLSS
     frame generation on an RTX 4090. In 4.2.0's tests in dense foliage (Forbidden Woods) it
     mostly held 60 → 120, with dips ([results](dlss-4.2.0-comparison.md)).

   DLSS 5 is tuned for a fixed **60 FPS** base. Other rates and native-4K output show a warning.
7. **Play.** Before each start the launcher writes `NeuralUplift=1` and your look settings into
   `bin\ReShade.ini` under `[RenoDX.DLSS5]`. ReShade has to have written that file once (step 2's
   first start does it). The game's log and menu should report **"DLSS 5: on (community bridge)"**.

## Look settings

All in **Visuals > Neural rendering (DLSS 5)**. Each has **Add-on default**, which writes nothing and
leaves renodx-dlss5's own value; **Reset to add-on defaults** sets them all back.

| Launcher row | Written as | What it does |
|---|---|---|
| NR upscaling | `NREnableUpscaling` | Neural rendering also upscales, from the DLSS render size. Cheaper at 4K, softer. In 4.2.0's 4K tests on an RTX 4090 (Forbidden Woods) it held 60 FPS with DLSS Balanced or Performance, 60 → 120 with frame generation only at Ultra Performance, and 57 FPS with Quality. Off (neural rendering at the full 4K output): 41 FPS. |
| NR intensity | `NRIntensity` | Strength of the effect (up to 2.00). |
| NR preset | `NRPreset` | NVIDIA's render preset. |
| NR style | `NRStyle` | Default / Natural / Cinematic. |
| Local structure | `NRLocalStructure` | Fine detail (up to 2.00). |
| Local tone | `NRLocalTone` | Local contrast. |
| Skin structure | `NRSkinStructure` | Detail on faces and skin. |
| Automatic mask, UI correction | `NRAutoMask`, `NRUICorrection` | Leave at the default: this port draws the HUD after DLSS, so no HUD reaches neural rendering. |

In game, ReShade's overlay (**F2** with the tested `ReShade.ini`; ReShade's default key is Home)
shows renodx-dlss5's panel with the values in use.

## Turning it off

Switch **DLSS 5** to **Off**. The launcher then keeps ReShade's Vulkan layer off for this port on
every start (even if ReShade is still installed) and never touches `ReShade.ini`. To remove it
entirely, delete the files you added to `bin\` and uninstall ReShade or take `bb-probe.exe` off its
app list.

## Troubleshooting

| You see | Cause and fix |
|---|---|
| "missing in bin: …" in the status line or log | Copy the named file(s) into `bin\`, next to `bb-probe.exe`. |
| Status says `bb-probe.exe` is not in ReShade's app list, or the log says `DLSS 5: off - ReShade is not set to load for bin\bb-probe.exe` | Run the ReShade installer again and pick this package's `bin\bb-probe.exe`. A new package folder needs this again: the path changed. |
| `dlss5-bridge.log` says nothing ever called DLSS | Set the upscaler to DLSS. Also check that log is from `bb-probe.exe`: the launcher's GPU check, `bb-gpu-capabilities.exe`, loads ReShade too and never calls DLSS. |
| The look settings don't change anything | Check that `bin\ReShade.ini` exists and has a `[RenoDX.DLSS5]` section after a start; if it doesn't, start the game once so ReShade writes it, then start again. |
| Under 60 FPS at 4K | Use DLSS 5 ready (2560 × 1440 output). Or turn on NR upscaling with DLSS Performance: on an RTX 4090 it held 60 → 120 with ray tracing Ultra and frame generation (4.2.4's runs), but it was no sharper than 2560 × 1440 output; Balanced and Quality miss 60. |
| The game won't start or crashes on start | Switch DLSS 5 off to confirm it's the add-ons, then update ReShade, the add-ons and the NVIDIA driver. |

For a bug report, attach `user\last_run.log` and `bin\ReShade.log` (and `bin\dlss5-bridge.log`).
