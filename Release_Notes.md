# Release Notes

## [4.2.8+build103026.192936] — 2026-10-30
### Co-op bells back to normal outside co-op
<!-- launcher:
### Co-op bells fixed outside co-op

- **Bells after seamless co-op:** playing offline or online after seamless co-op showed "?GoodsName?" items with no icon, and the Beckoning Bell and the other bells were gone. The launcher now turns BBSC's co-op bells back into the normal bells before the game starts (your saves are backed up first).
-->

4.2.8 is launcher only, on top of 4.2.7: a fix for the bells after seamless co-op.

- **Bells after seamless co-op:** BBSC gives each character its own co-op kit (Hunt Bell, Kin Bell, Bloodlust Bell, Duel Bell, Parting Blank) and takes the Beckoning Bell, Small Resonant Bell, Sinister Resonant Bell and Silencing Blank away. Those kit items only exist while BBSC runs, so starting offline or online afterwards showed them as **?GoodsName?** with a blank icon and left you with no bells. Before every offline or online launch the launcher now changes them back in your saves: Hunt Bell to Beckoning Bell, Kin Bell to Small Resonant Bell, Bloodlust Bell to Sinister Resonant Bell, Parting Blank to Silencing Blank. The Duel Bell has no normal counterpart and is removed. Your quick-item slots keep the bell they held. The saves are copied to `coop-backups` first. The next co-op launch, BBSC gives you its kit again.

## [4.2.7+build103026.164629] — 2026-10-30
### Save settings: your Visuals setup at every start
<!-- launcher:
### Save settings

- **Save settings:** on the Visuals page, one button saves everything you set there. The launcher starts with it every time: saved on Ultra, it starts on Ultra; your own mix shows as Custom.
- **A cleaner Visuals page:** the tuned presets sit on their own line after the card they were tuned on (RTX 4090), each with a ? for what it does. HDR, HD textures, DLSS 5 and Advanced settings moved to the right.
-->

4.2.7 is launcher only, on top of 4.2.6: your Visuals setup saved and loaded at every start, a tidier Visuals page, and the BBSC download back on the Co-op page. Nothing in the game changes.

- **Save settings:** the button at the top of the Visuals page's right column saves what the page sets: upscaler and output resolution, upscaling preset and DLSS model, model detail and effects, ray tracing and its tiers, frame generation and Reflex, sharpening, HDR levels, the upscale to the display, DLSS 5 and its look, and the frame rate. The launcher loads them at every start, whatever you tried last time. A saved preset stays that preset (saved on Ultra, it starts on Ultra).
- **Custom:** one pill at the end of the preset row for your own settings. It lights up when your settings match no preset, saved or not. Pressing it loads your saved mix after you tried another preset, or opens Advanced settings when you have none saved or are changing things.
- **Tuned presets on their own line:** `RTX 4090 | RTX 4080` then `Remastered DLSS 4 | DLSS 5`. They were tuned on an RTX 4090; RTX 4080 is greyed out until it has settings of its own. Each has a **?** that shows on hover what it sets and why it is suggested for your card, instead of a paragraph under the rows.
- **Right column:** HDR output, HD textures, DLSS 5 neural and Advanced settings sit beside the settings on wide windows (below them on narrow ones).
- **The preset row follows your edits:** changing one setting now lights Custom straight away; before, the row kept showing the old preset until something else refreshed the page.
- **Download BBSC on the Co-op page again:** the launcher redesign in 4.1.0 lost the button that downloads seamless co-op (BBSC 0.0.2), while the status line still told you to press it. **Download BBSC 0.0.2** is back (in the Co-op page's side column on the Account step), and once installed it reads **Download BBSC 0.0.2 again** to replace a broken copy. Play co-op and Start hosting still download it when it's missing. Downloading again keeps BBSC's own logs, save backups and captures.
- **Co-op connection details:** on the Connection step, **Show connection details** opens a short view instead of the full logs. **Check connection** marks each part as ready or not: BBSC installed, the Windows firewall rule for this game, your network (Tailscale or local), and, when you join, each of the host's ports (account server 31313, web API 31315, game server 20443, relay 20444), or your own servers when you host. Below it, BBSC's connection events from your newest session refresh every few seconds: relay connected or lost, signs rung and claimed, joins and session changes. **Open ports (admin)** makes this PC's co-op firewall rules with one Windows administrator prompt (Tailscale and your home network only; any address on the public server), then checks again. It lights up when the check finds the rule missing, and pressing it again repairs the rules.
- **No bundled external patch:** the package no longer includes Nerkuu's title-menu Exit Game patch (`Bloodborne_exit_game.xml`); its author's permission covers local test builds only. Workshop > External patches still loads any patch you add yourself, including that one. Exit to desktop from the in-game menu is unchanged.
- **Co-op in two steps:** Account, then Connection, where you play. The separate Launch step only repeated your choices, so it's gone. On the Co-op page, the side column holds the actions: **Download BBSC** under Before you play on the Account step, **Play co-op** and **Return home** on the Connection step.

## [4.2.6+build103126.013938] — 2026-10-31
### Seamless co-op hosting works again
<!-- launcher:
### Seamless co-op hosting works again

- **Guests can join your world:** 4.2.5 was missing the port's co-op server, so a host's bell found the guest's sign but the guest never arrived. The server is back in the package.
- **Nothing to set up:** start hosting from the launcher as before. Your co-op accounts stay as they are.
-->

4.2.6 fixes seamless co-op hosting. Nothing in the game changes.

- **Guests arrive again:** the 4.2.5 package had no `bin\coop-server`, the shadNet server this port builds for seamless co-op hosts. The launcher then started BBSC's own `shadnet.exe`, which drops this port's P2P signaling: the host's bell rang the guest's sign every minute, the guest never joined, and the session ended with `OnRoomTimeOut`. The co-op server is in the package again.
- **It can't go missing again:** `package.sh` now stops when the co-op server isn't built (it used to print a warning and carry on), and `scripts/build_dist.py` builds it whenever `out/coop-server` is missing, then refuses a package without it. `BB_PACKAGE_NO_COOP_SERVER=1` allows a package without it on purpose.
- **Already on 4.2.5?** The launcher keeps its co-op server and accounts in `%LOCALAPPDATA%\bbport-coop\shadnet-bbport`. A 4.2.5 host's accounts were made on BBSC's server (`BBSC-0.0.2-Server\server\db`); copy that `db` folder and `shadnet.cfg` into `shadnet-bbport` with the launcher closed, or players make their accounts again.

## [4.2.5+build103026.142640] — 2026-10-30
### First start set for your PC
<!-- launcher:
### Set for your PC from the first start

- **No more one-size settings:** the first time the launcher starts, it reads your graphics card and display and creates your settings from them: your display's resolution, DLSS on NVIDIA RTX cards (FSR 3.1 on others), and the preset suggested for your card.
- **Your choice from there:** the setup wizard shows what was set; pick another preset or change anything. Later starts keep your own settings.
-->

4.2.5 changes how a new install picks its settings. Nothing in the game changes.

- **Settings from your PC on the first start:** with no settings file yet, the launcher used built-in defaults that suited one PC: 3840 × 2160 output and DLSS for everyone, even on a 1080p screen or an AMD or Intel card. Now, once the graphics card check reports, it creates `bbport.ini` with your primary display's resolution as the output, DLSS on an NVIDIA RTX card and FSR 3.1 (every GPU) otherwise, and the graphics preset suggested for your card (the ★ one: Remastered on an RTX 40 or 50 card with 12 GB, then Ultra, High, Balanced or Low by video memory).
- **You stay in charge:** the setup wizard says what was set ("Set for your PC: …"). Pick another preset or change any setting. An existing `bbport.ini`, or settings saved from an earlier install, are never replaced.

## [4.2.4+build103026.125307] — 2026-10-30
### DLSS 4 and DLSS 5 suggestions, and DLSS 5 that says when it can't load
<!-- launcher:
### Two suggestions for your RTX card

- **★ DLSS 4 and ★ DLSS 5:** on a GeForce RTX 40 or 50 card with 12 GB or more, the graphics presets now mark one suggestion for each: Remastered for the sharpest picture, DLSS 5 ready for neural rendering.
- **DLSS 5 tells you when ReShade won't load it:** if ReShade's setup never added this folder's game, the launcher says so and the game turns DLSS 5 off instead of reporting it on.
-->

4.2.4 changes the launcher's graphics suggestions and how DLSS 5 starts. Nothing in the renderer changes.

- **Two suggestions on RTX 40 and 50 cards with 12 GB or more:** the preset buttons show **★ DLSS 4** on Remastered and **★ DLSS 5** on DLSS 5 ready (the second only where your card is offered DLSS 5). Measured on an RTX 4090: Remastered at 4K held 60 FPS with 120 shown, using about 8.7 ms of GPU a frame, and is the sharpest picture; DLSS 5 ready on a 4K display renders 2560 × 1440 and held 59-60 FPS. Other cards keep their single ★ suggestion.
- **DLSS 5 needs ReShade to load for this folder:** ReShade loads only for the programs its setup listed, and each version's folder needs its own entry. When DLSS 5 is on and this folder's `bin\bb-probe.exe` isn't listed, the launcher now warns, and the game starts with "DLSS 5: off" and the reason instead of claiming it is on. Add the folder in ReShade's setup (Vulkan) to use DLSS 5.
- **4K with NR upscaling, measured again:** with ray tracing Ultra and frame generation, DLSS Performance held 60 → 120; Balanced and Quality missed 60. In matched screenshots it was no sharper than 2560 × 1440 output, so the launcher still suggests 2560 × 1440 for DLSS 5 on a 4K display.

## [4.2.3+build103026.011954] — 2026-10-30
### Your PC at a glance in the launcher
<!-- launcher:
### Your PC at a glance

- **Your rig in the top bar:** graphics card, processor, memory and display, next to SunBro's Edition.
- **Hover or click it for the details:** video memory, driver, whether DLSS 5 is offered on your card, cores and threads, and your display's resolution and refresh rate.
-->

4.2.3 adds one thing to the launcher's Home page on top of 4.2.2. Nothing in the game changes.

- **Your PC in the top bar:** a pill between "SunBro's Edition" and the text size control shows the graphics card the game runs on, the processor, installed memory and the display (resolution, refresh rate, and HDR when it is on). On a narrow window it drops the display first, then memory, and never covers the other controls.
- **Details on hover or click:** the graphics card with its video memory, the driver version, whether DLSS 5 is offered on that card, the processor with its cores and threads, memory, and the display's exact size and refresh rate.

## [4.2.2+build103026.002741] — 2026-10-30
### Build and maintenance: one copy of the version, translations and DLSS model choices
<!-- launcher:
### Behind the scenes

- **More reliable builds and translations:** maintenance work so future updates ship with the right files and every language keeps its labels in place.
- **DLSS model "Default"** now reads "Default: the driver's choice", the same as in the in-game menu.
- **New launcher icon:** the gold Hunter's Mark on the taskbar and the launcher window.
-->

4.2.2 is maintenance on top of 4.2.1. Nothing in the renderer or the settings you choose changes.

- **One copy of the version:** the launcher reads the version from `version.txt`, so a release no longer has to change it in six places.
- **Packages always match their sources:** the release build now rebuilds the game files whenever their sources changed since the last build, instead of reusing older ones.
- **Translations kept in place:** every launcher language now names each text it translates, so adding a text can no longer shift the labels after it.
- **New launcher icon:** the taskbar and the launcher window show the gold Hunter's Mark from the launcher's Home page. The game window keeps its own icon.
- **DLSS model choices written once:** the launcher and the in-game menu take the DLSS model names, order and help from one table. The "Default" label now reads the same in both.

## [4.2.1+build103026.001435] — 2026-10-30
### Unbuilt ray tracing options removed from the menus
<!-- launcher:
### Tidier ray tracing settings

- **Two unavailable options removed:** dynamic secondary lights and ray-traced water reflections were never built, so their greyed-out rows are gone.
-->

4.2.1 is a small follow-up to 4.2.0. Nothing in the renderer changes.

- **Removed two ray tracing options that never worked:** "Dynamic secondary light sources" and "Ray-traced water reflections" are gone from the launcher (Visuals > Advanced settings > Ray tracing) and the in-game menu. Both had been greyed out as unavailable since 3.3.1, and no work on either is planned. Old settings files that have them still load.
- The README no longer says the port has ray-traced water reflections.
- [4.2.1 changelog](docs/changelog/changelog-2026-10-30-4.2.1.md).

## [4.2.0+build102926.203823] — 2026-10-29
### NVIDIA DLSS: DLSS 4.5 and DLSS 5 measured at 4K, the automatic DLSS model fixed
<!-- launcher:
### DLSS, measured at 4K

- **Faster DLSS on RTX 40 and 50:** Auto now picks NVIDIA's own model per quality mode. DLAA holds 60 FPS at 4K again.
- **DLSS 5 Balanced holds 60 at 4K** with NR upscaling on an RTX 4090.
- **Measured:** every DLSS tier, frame generation and DLSS 5 at 4K, with recommendations.
-->

4.2.0 is the DLSS release. Built on 4.1.0; in the launcher only the DLSS model choices change.

- **Faster DLSS on RTX 40/50 (automatic model):** with the DLSS model on Auto (the default), the game used DLSS 4.5's model M at DLAA, Quality and Balanced. NVIDIA's own defaults are model K there (M for Performance, L for Ultra Performance), and Auto now follows them. On an RTX 4090 at 4K, M cost 0.7–2.7 ms more GPU time per frame than K at those settings and up to 92 W more power. DLAA with M fell to 55 FPS under the 60 cap. With K it holds 60, and DLSS 5 at Balanced with NR upscaling now holds 60 too (it ran at 54). RTX 20 and 30 cards keep K everywhere, and a model you chose yourself is unchanged.
- **DLSS 4.5 against DLSS 5 at 4K, measured:** every DLSS tier with and without DLSS frame generation, native TAA, and DLSS 5 through the community route, on an RTX 4090. The recommendations: at 4K, DLSS Quality with frame generation (60 → 120, about 10 ms of GPU time per frame). DLSS 5 at a 4K output holds 60 only with NR upscaling at Balanced or below (60 → 120 with frame generation at Ultra Performance); NR at the full 4K output ran at 41 FPS. The **DLSS 5 ready** preset (2560 × 1440 output, NR upscaling off, Cinematic) mostly holds 60 → 120 in dense foliage, with dips. Full results, screenshots and clips: [DLSS 4.5 vs DLSS 5 at 4K](docs/dlss-4.2.0-comparison.md).
- **DLSS model choices say what Auto does:** the launcher (Visuals > Advanced settings > Upscaling) and the in-game menu now read "Auto: NVIDIA's pick per quality mode", "K: DLSS 4, for DLAA, Quality and Balanced", "M: DLSS 4.5 for Performance" and "L: DLSS 4.5 for Ultra Performance" (Russian too). They used to call M "best on RTX 40 and 50".
- [4.2.0 changelog](docs/changelog/changelog-2026-10-29-4.2.0.md) · [DLSS 4.5 vs DLSS 5 at 4K](docs/dlss-4.2.0-comparison.md).

## [4.1.0+build102926.161820] — 2026-10-29
### The new launcher: frosted glass over Bloodborne, one tab bar, shorter settings
<!-- launcher:
### A new launcher

- **A new look:** frosted glass over Bloodborne art, with one tab bar for every page.
- **Home at a glance:** Play, quick settings and your hunt's progress side by side.
- **Sized for your screen:** sharp at 4K; A− / A+ makes the launcher smaller or larger.
- **Shorter settings:** Visuals, Online, Co-op, Workshop and Settings split into single-topic pages.
- **Updates show what's new,** like this, and the launcher opens in half the time.
-->

4.1.0 replaces the launcher's look and layout. Built on 4.0.0; the game itself is unchanged.

- **A new look:** every page sits on full-window Bloodborne art, with frosted glass panels, round pill buttons and switches. One floating tab bar on every page: Home, Visuals, Online, Co-op, Dossier, Workshop and Settings; the highlight slides to the open tab, and Ctrl+1 to Ctrl+7 switch tabs.
- **Home:** SunBros Edition, your hunter, Play and how to play (Solo, Online or Co-op) on the left, over moonlit Yharnam. On the right, **Quick settings** tiles (frame rate, frame generation, ray tracing, HDR, display, FPS counter) that change with a tap, and **Your hunt**: trophy progress, HD textures and mods, each opening its page.
- **Sized for your screen, sharp at 4K:** the launcher opens as a centred window at about 40 % × 45 % of the desktop (about 1460 × 940 on a 4K screen), and everything scales with the window. **A− / A+** on Home (and Settings > System > Launch) makes it 80–130 %; Ctrl − / Ctrl + / Ctrl 0 do the same, and the size is remembered. Icons are drawn as vectors, so they stay crisp at any size or Windows scaling; menus and tooltips scale with the rest.
- **Visuals:** a page with the presets (one segmented control) and the six settings most players touch, plus HD textures, DLSS 5 and Advanced settings. Advanced settings has a sidebar of short, single-topic sections: Resolution, Window, HDR, Frame rate, Upscaling, Sharpening, Neural rendering (DLSS 5), Frame generation, Ray tracing, Detail, Post-processing, High-resolution textures, Video memory and Overlay. HDR output and its three brightness rows now have their own section.
- **Online and Co-op are separate pages.** Online is The Hunter's Dream. Co-op keeps the account, connection and launch steps (done steps get a check); the session frame rate is chosen with the connection, and the launch step sums up what you picked before Play. The account card's status names what is still missing ("Invite code needed", "Start hosting") instead of a bare "Setup needed".
- **First-time setup** resizes to fit each step, and marks found game files and data with a check instead of a dot.
- **Updates show what's new:** a new release is offered with a short changelog, its date and Download / Install now / Later; one downloaded in the background is offered the same way the next time the launcher opens (no bare "Install now?" box). After updating, the first start shows what's new in this version once. The full notes stay on the release page. **Check now** no longer says "You have the latest version" when no release can be found (for example while the release repository is private).
- **Workshop:** an overview of mods, built-in enhancements, Hunter's Atlas and patches, each opening its own section. Gameplay tweaks and Cheats are separate sections.
- **Settings:** Controls, Game & Saves and System in one sidebar with search. "Save settings now" is under System > Maintenance and "Reduce motion in the launcher" under System > Launch (both were on the old top bar).
- **Faster:** the launcher window opens in about 0.5 s instead of 1.3 s; each page is built the first time you open it. Backgrounds are blurred once when the release is built, and 16 MB of unused card art is gone.
- **Fixes:** Home showed "HDR10 On" with HDR off, and its HDR switch could not turn HDR on. Switches now line up with the dropdowns and buttons in the same list.
- [4.1.0 changelog](docs/changelog/changelog-2026-10-29-4.1.0.md) · Launcher design.

## [4.0.0+build102926.153214] — 2026-10-29
### Major release: save backups, HDR brightness controls, DLSS 5 neural rendering, FSR 4.1.1 on Windows

4.0.0 is the release the 3.4.1 follow-up grew into (it was never published as 3.4.1). Built on 3.4.0 (the DLSS roadmap).

- **Save backups in the launcher:** Settings > Game & Saves > Save backups. "Back up now" (with an optional label) saves a zip of your saves in `save-backups` inside the saves folder, and the list shows each backup's date, label, kind, size and characters. "Restore…" replaces your saves with a backup after first backing up the current ones ("before restore"); if anything goes wrong, your saves are put back. "Delete…" removes a backup; both ask in the row first. "Back up saves after playing" (on by default) makes a backup each time the game closes and keeps the last 10 of those; your own backups are never deleted. Backing up and restoring wait until the game is closed.
- **HDR brightness controls:** HDR output used fixed levels (SDR white at 120 nits, highlights rolling off to a 1000-nit ceiling, a 6.5× highlight expansion). Three launcher rows under Settings > Visuals > Display & frame rate > HDR output now set them: **HDR paper white** (`hdr_white_nits`, 80–400 nits, or *Match Windows' SDR content brightness*), **HDR peak brightness** (`hdr_peak_nits`, 400–4000 nits, or *From the display*; the shoulder starts at 60 % of it) and **HDR highlight boost** (`hdr_highlight_boost`, 0–1). `BB_HDR_WHITE` / `BB_HDR_PEAK` / `BB_HDR_BOOST` override them. The defaults are the old values, so the picture is unchanged until you pick one. Checked on the GPU in tests, not yet on an HDR display.
- **DLSS 5 neural rendering (community route):** a new Settings > Visuals > Neural rendering (DLSS 5) section, also reachable from a "DLSS 5 neural" button on the Visuals page. The `dlss5` switch at its top turns it on: with your own `nvngx_dlssnr.dll`, ReShade's `dlss5-bridge` and RenoDX's `renodx-dlss5` add-ons in `bin\`, the game keeps ReShade's Vulkan layer and reports "DLSS 5: on (community bridge)"; if a file is missing it stays off and says which. The section sets the add-on's look before each start: NR upscaling, intensity and local structure (up to 2.00), preset, style (Default / Natural / Cinematic), local tone, skin structure, automatic mask and UI correction, each with an *Add-on default* that writes nothing. A status line checks the three files and ReShade's app list. The port never ships or downloads these files: **DLSS 5 ready** now depends on the output: up to 1440p it keeps your output with DLSS Quality and ray tracing High; above that (4K) it sets 2560 × 1440 output, Cinematic style and local structure 2.00, which held 60 → 120 FPS on an RTX 4090 and looked sharper than NR upscaling at any 4K setting that held 60. A 4K output warns that neural rendering costs 14–16 ms a frame there. Presets keep Reflex On + Boost.
- **FSR 4.1.1 on Windows (experimental):** the FSR 4.1.1 upscaler used to need a Vulkan extension only Linux has, so on Windows it never ran. It now runs through [fsr4vk](https://github.com/dvj5411/fsr4vk) (v0.4.3 with the AMD Windows driver fix, from 0xCydral/bloodborne_pc), a separate program the game loads only when it is installed. Install it with Settings > Visuals > Upscaling > "Download FSR 4.1.1" (about 14 MB, SHA-256 checked), then choose FSR 4.1.1 as the upscaler. **On NVIDIA it runs up to 1920 × 1080 output:** above that fsr4vk's larger model crashes the GPU (RTX 4090 at 1440p and 4K), so the game uses FSR 3.1 instead and says why. DLSS and FSR 3.1 frame generation both work with it (60 → 120 FPS at 1080p on an RTX 4090). `BB_FSR4VK=0` leaves it off; `BB_FSR4VK_ANY_SIZE=1` tries larger outputs anyway.
- **A failed presentation image no longer stops the game:** when the GPU can't make a new presentation image (seen as `ErrorInitializationFailed` on a resize and on entering a new area), the frame keeps its previous image and the next frame tries again. Frame generation goes on without its HUD-free copy, and the HDR10 encode is skipped for that one frame. A first image is retried a few times. With a previous image to fall back on it never stops: it retries after 1, 2, 4… frames (up to 2 s apart), and frame generation pauses while a frame keeps its old size. The game still stops if a first image can't be made after a few tries. `BB_TEST_FRAME_ALLOC_FAILS=N[@M]` makes N allocations fail (after M presented frames), for testing.
- **DLSS 5 Detail and Colour change (built-in route):** `bbport.ini` `dlss5_detail` (NVIDIA's Structure Intensity, default 0.50) and `dlss5_tone` (Tone Intensity, default 0.00, which keeps Bloodborne's own grading), with `BB_DLSS5_DETAIL` / `BB_DLSS5_TONE` overrides, for the port's own DLSS 5 path once NVIDIA ships a runtime it can call. They have no launcher row: the community route above uses the add-on's settings instead.
- **Finer texture detail under DLSS:** the texture mip bias now defaults to NVIDIA's recommendation, log2(render ÷ output) − 1, instead of stopping at log2(render ÷ output). Across a 12-area tour on an RTX 4090 (4K DLSS Quality, RT Ultra, frame generation 2×) it resolved finer stone, cloth and sacking with no measured GPU cost (mean GPU busy 11.96 ms both ways). `bbport.ini` `dlss_mip_offset=0` (or the in-game slider) brings back the older, softer look; `BB_DLSS_MIP_OFFSET` overrides it. A file that already names a value keeps it.
- **Sharper picture when the output is below the display:** a 2560 × 1440 output on a 4K display used to be stretched with plain bilinear filtering. It is now upscaled with AMD FidelityFX FSR 1 EASU, before frame generation and the HDR10 encode, for about 0.15–0.2 ms on an RTX 4090. `bbport.ini` `present_upscale=linear` brings back the old stretch, and `present_rcas` adds FSR's RCAS sharpening on top (stops; default 0 = off, because the port's own sharpening already runs and RCAS 0.2 on top of it looked over-sharpened); `BB_PRESENT_UPSCALE` / `BB_PRESENT_RCAS` override both. Both are also launcher rows under Settings > Visuals > Display & frame rate: "Upscale to the display" and "Extra sharpening after upscale". Outputs at the display's size are unchanged. In game at 1440p on a 4K display with DLSS Quality and DLSS frame generation: 60/120 held, 0 failed presents.
- **Custom output sizes:** a size outside the launcher's list with an odd side (for example `output_res=3682x2071`) used to fall back to 1920 × 1080 for the game, the upscaler and the window; odd sides now round down to even (3682 × 2070), and `BB_OUTPUT_RES` now sets the game's render size too, not only the upscaler's output. The launcher lists 2880 × 1620 and 3200 × 1800. In game at 3200 × 1800 on a 4K display with DLSS Quality and DLSS frame generation: DLSS 2136 × 1200 → 3200 × 1800, FSR 1 EASU to the display, 60/120 held, 0 failed presents.
- **Smoother startup logos and title at 4K:** above 1080p the logos, title and loading menus are drawn at the output size from small bitmaps (the logo artwork is about half the 1080p stage size), and bilinear magnification left soft, blocky edges. Those bitmaps are now sampled with a Catmull-Rom (bicubic) filter where magnified: edges are slightly crisper and curves smoother (it cannot add detail the artwork does not have). No measurable GPU cost; 1080p output is unchanged; `BB_UI_BITMAP_FILTER=linear` brings back bilinear. The shader cache rebuilds once.
- **Fixes:** the launcher no longer hangs for minutes (Windows' "not responding") on Exit to desktop: the game's output reaches its log window in batches instead of one GUI update per line. Minimizing the game no longer leaves it presenting into a 0 × 0 swapchain, which dropped frame generation to 0 generated frames and raised Reflex latency from 57 to 72–77 ms; it now skips presenting until the window has an area and remakes the swapchain. With `BB_DLSS_BACKEND=streamline`, frame generation names the Streamline backend as the reason it uses FSR 3.1. Shorter labels in the launcher's cards: FSR 4.1.1 points to Visuals > Upscaling, frame generation reads "FSR 3.1 + 4.1.1" and "DLSS (RTX 40+)".
- [Features](features.md) · [4.0.0 changelog](docs/changelog/changelog-2026-10-29-4.0.0.md) · [DLSS 5 setup](docs/dlss5-setup.md) · DLSS 5 neural rendering · HDR guide · FSR 4.1.1 results · Follow-up results · Present upscale A/B.

---

## [3.4.0+build102826.180002] — 2026-10-28
### DLSS roadmap: about 1.6 ms of GPU time back, a "DLSS 5 ready" preset, DLSS through Streamline

- **Faster frames (A5):** render targets that the game reads back as buffers are now copied into game memory in one GPU pass instead of two. Sharpening after DLSS now writes the final image directly, skipping an extra copy. On an RTX 4080 SUPER at 4K with DLSS Quality and Ultra ray tracing, GPU time per frame drops by about 1.6 ms (image transfers 1.48 → 0.41 ms, sharpen + copy 0.52 → 0.12 ms). Uncapped, that's about 94 → 104 FPS. The images are the same: a word-by-word check matched the old path.
- **"DLSS 5 ready" preset (A6):** shown only on cards that are offered DLSS 5 (RTX 4080 / 4090 desktop, RTX 50 from the 5070 Ti). It sets 2560 × 1440 output, DLSS Quality, ray tracing Low, Reflex and DLSS 2× frame generation at a fixed 60 FPS, leaving the room DLSS 5 needs. DLSS 5 itself turns on only once NVIDIA ships it for these cards. A saved DLSS 5 request at any rate other than 60 FPS now shows a warning on the frame-rate and DLSS 5 rows.
- **DLSS through NVIDIA Streamline (A1, experimental):** `BB_DLSS_BACKEND=streamline` runs DLSS Super Resolution through Streamline 2.14.16 (`bin\streamline`), NVIDIA's route for DLSS 5. It matches NGX in speed and image. On this backend, frame generation uses FSR 3.1 and Reflex stays on the port's own path. NGX remains the default.
- **HDR input for DLSS (A4):** measured, not changed. Feeding DLSS the linear HDR image (as live resolution does) gave a visibly softer picture at 4K, so the default stays.
- **Fewer shader-compile hitches:** the first time a boss fight, effect or object appears, the game used to stop for up to ~120 ms per new pipeline while NVIDIA's driver built it.
  - **Bigger catalog:** the shipped shader catalog gained the boss fights' pipelines, and they're built at startup. In those fights the worst frames went from 100–117 ms to 18–34 ms.
  - **Background builds:** new pipelines for effects and objects are built on two background threads. The effect or object appears a few frames later the first time, instead of the game stopping.
  - **Worst case** (nothing pre-built, empty driver cache): Cathedral Ward's worst frame went from 250 ms to 18 ms, with no frame over 40 ms in any area tested.
  - Toggle bit 61 turns background builds off.
- **Smaller fixes:** `BB_DLSS5` is now only the `dlss5` setting's override; the community bridge uses `BB_DLSS5_ROUTE_A`. A presentation frame whose allocation fails is retried once before the game stops.
- [Features](features.md) · [3.4.0 changelog](docs/changelog/changelog-2026-10-28-3.4.0.md) · Roadmap results · Roadmap.

---

## [3.3.3+build102826.011409] — 2026-10-28
### DLSS model per quality mode, DLSS 5 kept off, audit follow-up

- **DLSS model per quality mode (DLSS-4):** `bbport_dlss.dll` sends the selected model only for the active quality mode. Before this, a manual choice such as L also applied at Quality. Auto already chose per mode, so its behavior is unchanged.
- **DLSS 5 stays off:** while the community bridge is paused, the launcher (`run.py`) disables ReShade's Vulkan layer on every start and ignores inherited `BB_DLSS5` / `BB_DLSS5_PROBLEM`. Use `bbport.ini dlss5=` rather than `BB_DLSS5` to change the saved request.
- **Clearer DLSS 5 status:** the in-game reason no longer points to a setup guide that doesn't exist; the launcher hint adds the graphics-card check's reason. The future native DLSS 5 hook also covers DLSS's 16-bit output path (no runtime change today).
- **DLSS 5 groundwork:** the DLSS bridge is ABI 3, with DLSS 5 neural-rendering entry points (reported unsupported until NVIDIA ships a Vulkan runtime for RTX 40), and the DLSS 5 hook now receives colour, depth, motion, jitter and the camera. Nothing changes in game today.
- **Documentation:** DLSS docs vs code audit, hardware test protocol, corrected DLSS 5 plan statuses and the 3.0 changelog's DLSS-G claim.
- **Validation:** on an RTX 4090, in-game checks T1–T6 pass (model per mode incl. a live change, mip-offset precedence, FSR 3.1 fallback, Reflex promotion, SDR, ReShade kept off unless opted in), and a 15.4-minute run of this package (HDR10, DLSS-G 2×, Ultra RT, lamp travel) holds a median 60/120 with 53,172 DLSS-G pairs, 0 failed presents and no faults. Native tests (28/28 runnable on Windows), the Python suite (453 tests; Linux-only tests skip on Windows) and the DLSS bridge ABI 3 check pass.
- [Features](features.md) · [3.3.3 changelog](docs/changelog/changelog-2026-10-28-3.3.3.md) · DLSS test results.

---

## [3.3.2+build102826.102118] — 2026-10-28
### HD Texture Pack setup fix

- **Builds by itself:** once every Nexus download for the HD Texture Pack is in its downloads folder and no pack is built yet, the launcher starts the build on its own: when its window opens, after a downloads folder is chosen, or when the last download arrives. It never builds while the game runs; Play waits for the build or its cancellation.
- **Browse works for the HD Texture Pack folders:** Browse beside *HD Texture Pack folder* and *HD Texture Pack downloads folder* did nothing; it now opens a folder picker that starts in the folder in use.
- **Downloads beside the launcher:** with no downloads folder chosen, an `hd-pack-downloads` folder next to the launcher's own folder is used when the pack's own `downloads` folder is missing, so zips kept outside the launcher are found without any setting.
- Validation: the 8 HD Texture Pack launcher tests pass, including a new one for the folder beside the launcher and the automatic build. Distribution: `bbport-windows-3.3.2`.
- [Features](features.md) · [3.3.2 changelog](docs/changelog/changelog-2026-10-28-3.3.2.md).

---

## [3.3.1+build102726.205608] — 2026-10-27
### Remastered quality, frame-generation FPS overrides and clearer output targets

- **Remastered quality:** explicitly selects DLSS Quality with the automatic DLSS model, Ultra ray tracing, required object motion vectors, highest model detail, 16x filtering, screen-space reflections, and AO intensity restored to 100%. Keeps the chosen output resolution and cosmetic effects; enables the HD Texture Pack when installed, independently of ordinary mods.
- **Frame-generation configuration:** retains the 60 game FPS + DLSS 2× target with Reflex and display fitting. Selecting Remastered now resets conflicting advanced FPS overrides and the manual frame cap. An old `BB_FPS=uncap` override could otherwise defeat the 60 FPS base and leave no generation budget on a 120 Hz display. Unrelated advanced variables are preserved.
- **Clear FPS targets:** Home now shows **60 base → 120 FPS** under **BASE → OUTPUT TARGET**, reflects the selected DLSS multiplier, and exposes an advanced FPS override instead of showing a misleading preset target. The tooltip distinguishes configured targets from measured performance; conflicting effective FPS settings show as Custom.
- **Downloaded updates:** restores a prepared newer update across launcher restarts even without the release cache, keeps its ready-to-install notice, and offers installation on the next launcher start when background downloads are enabled. Home shows an update banner with download/install and update-details actions. Installation still requires confirmation.
- **Packaging:** cleans only the current package's staging folder, preventing another build's locked files from breaking packaging.
- **Title/startup presentation:** generated copies of the original title movies zoom only their padded background artwork uniformly to fill a 16:9 screen, with a small top/bottom crop; menu commands stay in place and the original game files are untouched. Movie-only bitmap sampling uses linear filtering to reduce enlarged logo pixel steps. Gameplay/depth samplers retain their filtering. Other aspect ratios retain their existing title layout. `BB_TITLE_FILL=0` keeps the original title artwork framing.
- **Unavailable graphics:** secondary-light and water-reflection rows now disable and dim the whole control, explicitly distinguishing saved On requests from active effects. Implementation requirements. DLSS 5's paused backend is now explicitly shown as unavailable and the launcher control is disabled, including when an older settings file contains an On request. Ordinary DLSS upscaling and frame generation remain separate selectable features.
- **In-game menus:** the injected Achievements / PC Graphics / PC Display / PC Effects / PC Settings sections are off by default; use the launcher for PC settings. `BB_PC_MENU=1` explicitly restores the older menu. The local test package includes the user-supplied Nerkuu Exit Game 1.01 XML as a separate title-only patch, enabled by default. That third-party XML requires the author's permission before public redistribution.
- **Applying the fix:** open the 3.3.1 launcher, select Remastered again, then restart the game. Existing saved preferences are not silently rewritten on upgrade.
- **Runtime validation:** the supplied 3.3.1 log now confirms 60 game FPS and 120 accepted-image FPS with increasing DLSS-generated counts during gameplay. Title-only frames have no captured 3D scene to interpolate. The title-fill and bitmap-filtering follow-up still needs visual confirmation in the new package; smoothing does not add detail absent from the original logo bitmaps.
- Follow-up validation: 103 focused Python/QML tests and 65 subtests pass; 5 optional game-fixture tests skipped. Distribution: `bbport-windows-3.3.1`.
- [Features](features.md) · [3.3.1 changelog](docs/changelog/changelog-2026-10-27-3.3.1.md).

### In-game desktop exit and documentation follow-up

- Confirming the in-game Exit Game hides the game window, preserves its original save/return action, and requests normal desktop shutdown when the title menu is reached. No forced process termination or save timeout is used. Canceling does not hide or quit. `BB_EXIT_TO_DESKTOP=0` keeps the original visible return-to-title behavior.
- The native Exit confirmation pointer and title call are checked before patching. A mismatch leaves that hook unavailable and logs the reason. This path is independent of the optional PC menus and the separately installed title-menu Exit XML.
- User confirms the separate title-menu Exit Game works. The new hidden save-then-exit flow still needs in-game verification.
- README now shows current full-width launcher screenshots with example profile data, and the changelog index exposes 3.3.1 directly.

### Exit wording and package refresh

- Generated message archives now say **Exit to desktop**, **Save your progress and exit to desktop.**, and **Save your progress and exit to desktop?** The original game archives remain unchanged. The wording follows the desktop-exit opt-out and does not add PC menu sections.
- The user confirmed the hidden in-game exit works. Its previous return-to-title wording is replaced in the new package.
- Windows build extraction completes in a temporary folder before the playable package is swapped into place, with rollback on swap failure and settings/save preservation. This avoids opening an EXE while its Qt/Shiboken files are still extracting, which can trigger the classic Tk fallback. Its background is bundled launcher/art/hero.png, not a cached screenshot.

---

## [3.3.0+build102826.025304] — 2026-10-28
### 3.3.0 — SunBros Launcher Command Center, HD Texture Pack, 16x filtering, Remastered preset, and ray-tracing views

- **Launcher Command Center & Workspaces:** Redesigned Qt Quick / PySide6 launcher with the `HomePage` Command Center dashboard (Hunter's Dossier card, Co-op Altar, System Ready summary, sticky Launch Dock, and HD Texture Pack status chip), dedicated top-level workspaces (`VisualsStudio` with presets, before/after comparison, and HD Texture Pack shortcut; `DossierWorkspace` with 6-axis `StatRadar` and searchable trophy filters; `MultiplayerWorkspace` with guided `CoopSetupPanel`; `Mods` workspace; and `PreferencesPage`), `DepthCard` 3D tilt effects with motion toggle, and opt-in background update downloading (`download_updates`).
- **HD Texture Pack (launcher):** downloads BB Reborne, Upscaled Skybox and Clouds and SFX Texture Overhaul from Nexus Mods on the player's PC (a link per file) and builds one picture-only pack in its own folder, apart from the launcher folders. 4x Upscaled Armors is left out (area-travel stalls). Maps, enemies, items, events and co-op are unchanged. Needs about 45 GB free while it installs, 20 GB after, and a card with 10 GB of video memory or more.
- **16x anisotropic texture filtering** (`anisotropic_filtering`, default 16) and the **Remastered** graphics preset (`preset=1`, `model_lod=-2`, `ray_tracing=ultra`, `anisotropic_filtering=16`, `fps_mode=60`, `frame_gen=auto`, `frame_gen_multiplier=2`, `frame_gen_fit_display=1`, plus auto-enabling the HD Texture Pack when installed).
- **Ray tracing:** debug views and the compare split, stronger ambient occlusion with combine/reach/full/direct controls, moon shadows "ray traced only" (`rt_shadow_replace`), and the game's depth as the alpha test for see-through geometry. The AO history keeps the fast-band clamp and then the RTG-5 neighbour clamp. The water-reflection prototype stays disabled.
- **HDR:** output stays the presentation-time BT.2020/PQ conversion after frame generation and the overlay. The game log still reports the display's SDR brightness and peak.
- **DLSS 5 readiness (paused):** the experimental switch, greyed out unless the card, DLSS and 60 FPS allow it; nothing of the bridge is packaged.
- **Online code restored:** the top-level `.gitignore`'s bare `vendor/` hid `bloodborne_pc/gpu/bbnet/vendor` (shadPS4 network, NP and shadNet sources), so a clean checkout could not build. The rule is anchored (`/vendor/`, `/reference/`) and the 131 files are in the repository.
- **FSR:** local frame-generation and FSR 4 input fixes in the vendored `fsr-vulkan`.
- **Mods:** overlays left by killed starts are removed.
- **Launcher:** the HD Texture Pack folder no longer fails to resolve when `LOCALAPPDATA` is unset (it stays beside the launcher's data); `coopPlay` now shares `play`'s setup and HD-pack build guards.
- Validation: native build passes; focused C++ unit tests (`test_dlss_model_settings`, `test_nvidia_gpu`, `test_rt_settings`) pass; Python & QML integration suite (104 tests + 63 subtests across workspaces, dashboard, co-op, background updates, graphics presets, HD texture pack, and ray tracing) passes. Package: `bbport-windows-3.3.0`. [Features](features.md) · [Changelog](docs/changelog/changelog-2026-10-28.md).

---

## [3.2.10+build102726.114500] — 2026-10-27
### 3.2.10 — Uncapped dynamic jump decay hook and vendor-partitioned shader catalog

- **Uncapped FPS dynamic simulation timestep hook:** Hooked running-jump horizontal momentum vector multiply (`0x1a4abca`). The on-disk executable is unmodified; in-memory instruction displacement is redirected to an isolated hook cell in the stub area. Dynamically scales horizontal decay by `0.95 ** (30 * dt)` using the game's measured frame delta (`[manager + 0x264]`) with high-precision wall-clock fallback (`QueryPerformanceCounter`), clamped between 1/480 s and 1/20 s. The original constant vector at `0x490b5b0` and vertical jump impulses are preserved. Controlled via `BB_JUMP_DT=1` (auto-enabled when uncapped unless disabled via `running_jump_fix=0` in `bbport.ini` or `BB_RUNNING_JUMP_FIX=0`). Configurable source via `BB_JUMP_DT_SOURCE=clock|game`.
- **GPU vendor-partitioned shader catalog & isolated cache storage:** Partitioned `shader_catalog/` into `nvidia/` (PCI ID `0x10DE`, 1,953 records) and `amd/` (PCI ID `0x1002`, ready for AMD records), with Intel (`0x8086`) and common fallback support. User pipeline caches are now stored in vendor-isolated directories (`user/cache/CUSA03173/<vendor>/`) with automatic legacy cache migration. `BB_GPU_VENDOR` strictly overrides hardware detection before copying, preventing cross-vendor flattening. Cross-vendor profile mismatches automatically clear stale architecture records.
- **Pipeline variant stutter mitigation & qualification:** Pre-building seeds known permutations ahead of time, eliminating startup and traversal hitches for cataloged shaders. Uncataloged variants (including 229 session-local motion pipelines) still compile on first use and can exhibit transient frame drops (e.g. 27 ms).
- **Pacing & RT telemetry:** Retained `BB_VIDEOOUT_BACKPRESSURE=0` and `BB_RT_CAPTURE_BUDGET=16`. Interval telemetry for dynamic jump momentum now outputs every 10 seconds by default (silenced with `BB_FPS_LOG=0`).
- Testing package: `bbport-windows-3.2.10` (SHA-256: `fadeca188d7d33039a0aa489d6237f579a9f6f41a5d118c4fa06c473a806d5e4`). [Features](features.md) · [Changelog](docs/changelog/changelog-2026-10-27.md).

---

## [3.2.9+build102726.105142] — 2026-10-27
### 3.2.9 — renderer maintenance, co-op settings and running-jump correction

- Reduce Atlas drawing work with a worker-built spatial index and reuse mapped ImGui upload buffers with growth headroom, retaining draw order and upload synchronization.
- Add bounded device-wide VRAM-pressure response for RT, compatible driver-cache checkpoints, invalid-key pruning and separate session-local motion deferral reporting. Preserve recent/dynamic geometry protections. Admission blocking stays off.
- Fix duplicate co-op name/password/server editors. The user confirmed the refreshed co-op UI is correct; search focus and settings reload regressions pass.
- Correct existing horizontal-momentum damping for fixed 60/90/120/144 FPS against 30 FPS decay, with executable/data guards. Disable via `running_jump_fix=0` or `BB_RUNNING_JUMP_FIX=0`. Vertical impulse is unchanged. Uncapped needs a measured-frame-time hook and remains unchanged; physical jump-distance equivalence still needs gameplay comparison.
- Resolve Pyrefly optional-value diagnostics in patch generation and tests with explicit narrowing and required XML attributes.
- Local renderer CPU/GPU, co-op/navigation and patch regressions pass. Supplied 3.2.9 gameplay showed zero capture exclusions and no PresentImage call reaching 50 ms; identical-route gains, genuine VRAM-pressure recovery and jump distances remain unverified.
- Final package: `bbport-windows-3.2.9`. Earlier testing archives remain separate. [Features](features.md) · [Changelog](docs/changelog/changelog-2026-10-27.md).

---

## [3.2.9+build102726.102043] — 2026-10-27
### Map drawing, VRAM maintenance and repeat-run pipeline caching (testing)

- Cull Atlas floor triangles using a worker-built spatial index, preserving source draw order, fog checks and geometry coverage. Reuse mapped ImGui vertex/index upload buffers and grow them with headroom.
- Extend existing RT cleanup to current device-wide VRAM pressure, with 90%/85% hysteresis, bounded cold-entry retirement and existing GPU-deferred destruction. Recent entries and dynamic-character allocation rules remain protected; static RT coverage under pressure needs testing.
- Persist compatible Vulkan driver-cache data through background checkpoints. Validate vendor/device/UUID and blob bounds, drain accepted writes on controlled shutdown, and prune structurally invalid/version-incompatible pipeline keys. Session-local motion variants remain deliberately deferred and are reported separately.
- Add overlay vertex/index counts and slow shader/pipeline compilation timings for route comparisons. Keep VideoOut admission blocking off and preserve texture-upload synchronization.
- Validation: native renderer, CPU spatial/pressure/cache/queue regressions and the RTX 4090 offscreen upload/cache test passed. This is not a measured FPS gain; identical-route gameplay and real VRAM-pressure acceptance remain pending.
- Fix duplicate co-op name/password/server controls: the guided form owns their editors while navigation/search metadata remains available. Add a rendered-QML regression that detects the three duplicates in the old path and verifies one set plus search focus/settings reloads after the fix.
- The supplied original 3.2.9 run has 12 min 16 s telemetry, all 50,124 generated outputs accepted, zero capture exclusions, and no slow-present call reaching 50 ms. Six 20–26 ms overlay events all coincide with texture updates; pressure was never active. Startup/producer stalls remain, and repeated-route/pressure acceptance is still open.
- Refreshed testing package: `bbport-windows-3.2.9-coop-settings-testing`. Original 3.2.9 package: `bbport-windows-3.2.9-render-maintenance-testing`. [Features](features.md) · [October 27 changelog](docs/changelog/changelog-2026-10-27.md).

---

## [3.2.8+build102726.085821] — 2026-10-27
### Atlas background preparation, BBSC 0.0.2 co-op, and first-time setup artwork

- Move Atlas JSON parsing and initial cut/interior geometry construction into a single background CPU job. Present frames continue with loading feedback until prepared map data is ready.
- Restore Hunter's Workshop background artwork and smooth gradient blending in First-Time Setup (`Main.qml`).
- Optimize setup wizard content width to maintain clean typography and keep artwork visible (`SetupWizard.qml`).
- Add BBSC 0.0.2 seamless co-op client/server packages, host data migration, and BBSC public server support (`play.seamlesshunt.com`).
- Standardize The Hunter's Dream client version string to `bbport`.
- Add overlay timings for ImGui locks, map/menu ticks, UI construction and backend draw/uploads under `BB_FPS_LOG=1`. Preserve existing GPU upload synchronization and default-off admission blocking.
- Retain the RT-only capacity control and character reserve; correct the percent sign in capture diagnostics.
- Testing package: `bbport-windows-3.2.8-atlas-hitch-testing`. The gameplay-tested artifact was `3.2.8+build102726.002419`; later co-op/setup-artwork source updates use `3.2.8+build102726.085821` and were not covered by that artifact's game log.
- Gameplay evidence for the earlier 3.2.8 artifact: 22 min 1 s telemetry, zero capture exclusions at 16 Mi vertices, all 85,333 generated outputs accepted, no measured PresentImage call reaching 50 ms and no GPU-loss/SRT fault markers. Smaller 20–43 ms overlay calls, seven rendering-stall messages and startup intervals of 134/182 ms remained. The 3.2.9 work targets those remaining drawing/cache costs; its gameplay results are pending.

---

## [3.2.7+build102626.204401] — 2026-10-26
### RT-only capture budget and hitch diagnostics (testing)

- Add `BB_RT_CAPTURE_BUDGET` (1–64 Mi vertices), overriding only RT capture capacity with base history capacity as its floor. Default remains 12 Mi vertices.
- Preserve the 15% character reserve while RT is active or retaining resources, including equal base/RT budgets and failed growth. Report capacity and position-buffer memory cost.
- With `BB_FPS_LOG=1`, report same-image CPU stage timings for presents taking at least 50 ms, including overlay and scratch recreation. The 174–383 ms hitch cause remains unconfirmed.
- Move Atlas parsing and initial geometry-cache preparation off the presentation thread into one isolated CPU worker with loading feedback. Add overlay substage timings for remaining hitches; GPU upload synchronization is unchanged. Native build and async-job regression pass; gameplay verification is pending.
- Keep VideoOut admission blocking off by default. Native renderer and motion-history/admission regression tests pass; gameplay coverage and GPU validation remain pending.
- Supplied 27 min 42 s telemetry run at 16 Mi vertices reports zero capture exclusions; same-image diagnostics localize four 50-326 ms hitches to overlay rendering. Internal overlay cause remains open. Escape the literal percent in the reserve diagnostic discovered in that run.
- Separate testing package: `bbport-windows-3.2.7-rt-capture-testing`. The verified 3.2.6 recovery archive remains unchanged.

---

All releases of this custom build of the Bloodborne PC port, newest first.

## [3.2.6+build102626.192649] — 2026-10-26
### Disable experimental VideoOut blocking after a GPU-loss report

- Default `BB_VIDEOOUT_BACKPRESSURE` to off. Keep observation-only queue/admission telemetry, the prior publish-before-Reflex-sleep ordering, HDR10 and FG. The experimental dequeue gate requires an explicit process environment override of `1`.
- Label each `VideoOut admission:` report with `mode=observe only` or `mode=experimental dequeue gate`, plus gated/bypassed counts and the effective environment flag, so a recovery run verifies the intended path.
- The first supplied 3.2.5 run failed with Vulkan device loss on submit, `WriteInvalid` near GPU address zero and exit code 23, shortly after the first successful/accepted DLSS-G pair. At least 32 unmapped SRT warning messages preceded the fault (the warning logger caps at 32). No admission timeout or invalid handoff sample was reported beforehand. The later Reflex error coincides with device loss; root cause is not established.
- Source inspection confirms both graphics and compute pipeline selection already reject SRT-walk faults. Do not mask the warning, remove that protection, assume HDR/NGX alone caused the crash, or treat the reduced startup queue age as stable gameplay evidence.
- **Recovery validation:** The complete saved run includes startup and 225 five-second telemetry periods totaling 18 min 46 s on RTX 4090 / driver 621.01. HDR10 and DLSS 2× remain active, with median accepted rates of 60 game images / 120 total images per second. All admission reports bypass blocking; no GPU-loss/SRT errors or presentation failures occur. The run quits normally. This supports the rollback baseline without identifying the earlier faulting GPU command.
- **Counters and limits:** Final generated / accepted-generated snapshots are 65,951 / 65,936, with 13 explicitly unpresented outputs. Three RT windows exclude 42,278 captures at the character reserve; slot/total-capacity exclusions are zero. One startup stall and a maximum reported frame of 383 ms remain. The full-run VideoOut queue window-average median is 29.45 ms; the median of 37 Reflex marker averages is 54.2 ms. Neither is a physical input-latency measurement.
- **Complete logs:** The launcher already saves full stdout/stderr to `<saves folder>/last_run.log` and rotates older runs. Its QML screen/Copy Log buffer retains 350,000 characters. The missing startup in the pasted excerpt was clipboard truncation; the complete file was recovered. The disk writer currently omits the launcher-generated exit-code footer.
- **Package and checks:** `bbport-windows-3.2.6-recovery.zip`, 321,675,968 bytes, SHA-256 `92df4665c5a3d81b212092c14c884d3f121e537dc8a20c91a7fc3ea863d2b904`; built from `b6b9810`. Native build, six CPU regression tests, full ZIP CRC, frozen launcher version, current renderer, DLSS ABI 2 SR/FG and Atlas assets passed verification. Documentation updates do not replace this archive.
- **Next work:** Preserve the recovery policy; add RT-only capacity control without removing the character reserve, investigate the hitch windows and keep HDR calibration/hardware transitions open. [Feature catalog](features.md) · [Dated changelog](docs/changelog/changelog-2026-10-26.md).

---

## [3.2.5+build102626.191628] — 2026-10-26
### Bound the prepared-frame queue with Reflex

- After publishing/notifying a frame, wait for VideoOut to dequeue it before beginning the next Reflex work span. Keep guest vblank/flip scheduling and generated-image pacing unchanged. The default policy applies with active Reflex; unsupported/off paths bypass it. `BB_VIDEOOUT_BACKPRESSURE=0` is a process-environment comparison override.
- A 100 ms admission timeout and shutdown notification prevent an indefinitely blocked admission wait. A timeout can allow the target queue depth of one to be exceeded; report it instead of claiming a hard queue bound. Acknowledge before presentation work, never while waiting for generated images.
- Add five-second `VideoOut admission:` reports under `BB_FPS_LOG=1`: queued/peak depth, published/dequeued totals, gated/bypassed/blocked counts, next-work wait averages/maxima and timeouts. Keep the existing handoff and Reflex wait diagnostics.
- Validation: six CPU regression tests pass, including real producer/consumer admission waits, acknowledgement ordering, bypass, timeout, report/reset and shutdown release. Native renderer/build verification accompanies the testing dist; 15+ minute gameplay acceptance remains pending.
- Interpretation: 3.2.4 maintained HDR10 and DLSS 2× at steady 60 game presents / 120 accepted images per second, but its VideoOut queue wait median was 32.69 ms and Reflex marker median 57.8 ms. Moving the next marker boundary after admission changes that interval's coverage; a smaller marker value alone will not prove improved input latency. Compare admission waits, FPS, stutter and visible response too.

---

## [3.2.4+build102626.171737] — 2026-10-26
### Reflex frame publication and CPU timing diagnostics

- Publish and notify the current VideoOut frame before Reflex sleeps for the next frame. Keep render-submit-end before publication; copy the frame ID before transferring ownership, and wait outside the Reflex mutex.
- Invalidate pending pacing IDs during swapchain recreation. Consume each submitted ID once; retain bounded semaphore waits and measurement-only behavior.
- With `BB_FPS_LOG=1`, report five-second CPU handoff averages/maxima for preparation, VideoOut and swap-thread queues, plus separate Reflex API/semaphore wait timings, timeouts and errors. These are CPU/marker timings, not input-to-photon latency or physical scanout measurements.
- Validation: CPU handoff partition/reset tests and the production Reflex state machine with mocked Vulkan calls pass, including publication order, present progress during the wait, duplicate IDs, sleep failure, timeout, recreation and measurement-only mode. Motion-history, presentation-telemetry and DLSS settings regression tests also pass. Gameplay latency/pacing comparison remains pending the new run.

---

## [3.2.3+build102626.160630] — 2026-10-26
### Capture-limit diagnostics and periodic frame-generation telemetry

- **RT capture diagnostics:** Report parameter-slot, total vertex-capacity and character-reserve exclusions separately, with per-report high-water marks, current limits and largest vertex-rejected draw. Keep allocation policy/capacity unchanged. `BB_MOTION_BUDGET` changes vertex storage only; it cannot solve parameter-slot exhaustion.
- **FG presentation telemetry:** Emit a report every five seconds with cumulative successful DLSS/FSR pairs and generated/accepted-generated totals; interval counts include unpresented outputs and failed presents. Game-present and accepted-image rates count accepted application presentations, not physical scanout or guest-render completion. Include requested/latest provider, selected HDR mode and inactive/fallback reasons.
- **Logging cost:** Format telemetry in a fixed buffer and write once to unbuffered stdout. Keep report state per presenter and handle idle intervals, counter resets and clock regression.
- **Validation:** Native renderer build plus `motion-history-test`, `presentation-telemetry-test` and `dlss-settings-test` passed. Live capture-exhaustion reproduction, overlay/log comparison, runtime fallback, window transitions and stall diagnosis remain pending.
- **Scope:** Diagnostic instrumentation; gameplay acceptance remains pending. Distribution integrity and gameplay behavior require their own verification. The verified 3.2.2 archive remains unchanged. This adds diagnostics; it does not claim to fix the prior 467 missing captures or six stalls. HDR calibration remains planned.

---

---

## [3.2.2+build102626.142758] — 2026-10-26
### HDR + frame generation, runtime accounting and documentation

Patch release for HDR/FG integration and runtime accounting fixes after 3.2.1. A fresh 3.2.2 distribution is built and verified; the supplied run confirms concurrent HDR10 output selection and successful DLSS-G evaluation. Known RT capture exhaustion and rendering-stall messages remain under investigation.

- **Shared HDR output after FG:** Keep rendered/generated/HUD-less color buffers SDR, compose the actual PC overlay in a matching SDR attachment, then convert every output image once to **BT.2020 / ST 2084 PQ, 10-bit RGB** (`VK_FORMAT_A2B10G10R10_UNORM_PACK32`). HDR no longer suppresses frame generation. Plain SDR and SDR-on-HDR desktop compensation remain supported.
- **Presentation and status fixes:** Return actual swapchain presentation success, count accepted generated presentations separately from evaluations/output, clear stale activity on skip/failure, and retain automatic DLSS→FSR fallback causes until provider change or DLSS recovery.
- **Validation:** Native renderer build and four focused tests passed during integration, including actual shader SPIR-V readback on RTX 4090. The later 848-line 3.2.2 log records HDR10 mode and successful DLSS-G 2× evaluation, then clean exit. Validation layers were absent during integration testing; generated-presentation totals, physical calibration and the toggle/resize/fallback matrix remain open.
- **3.2.2 package:** `bloodborne_pc/dist/bbport-windows-3.2.2.zip`, 321,578,750 bytes / 306.68 MiB, SHA-256 `e00e9dbbd0c4b7dabd49ff0644ea331db0b737b92229fb5cdde6bc6f8ea4d7ff`. Clean standalone distribution with `features.md` at root and development files omitted. CRC, selected file hashes, frozen launcher 3.2.2, current native renderer and packaged ABI 2 verified. Includes 20 Atlas map files, 7 art assets, frozen generator and 16 guides. The runtime's 16 registered areas are a different count. The custom co-op server was omitted; BBSC fallback remains available.
- **Known issues:** One RT reporting window records 467 draws missing from the RT scene due to object-motion capture exhaustion; these are not dropped display frames. Six rendering-stall messages and 217 stale pipelines warrant investigation; causation is not established. Reflex marker averages range 19.1–28.9 ms, not input latency. Capture-limit diagnosis, periodic FG presentation counters and repeatable stall/pacing measurements are the immediate follow-ups.
- **Brightness qualification:** The current SDR-expansion curve has a 600-nit knee and asymptotic 1000-nit ceiling; neutral white GPU readback is 742.757 nits. This is not a physical OLED measurement, native HDR scene recovery or a 1600-nit calibration mode. Peak/paper-white controls remain planned.
- **Documentation:** Concise root feature table, launcher guide, dedicated [build guide](build.md) and [dated changelog](docs/changelog/changelog-2026-10-26.md).

Historical entries below retain release context. Their earlier claims of sustained 4K120, fixed 1 ms shadow savings, eliminated ghosting, working production reflections, 10-bit ImGui compatibility and complete automated coverage are superseded by the qualified [feature catalog](features.md). Reflex samples are marker intervals, not input-to-photon latency; PGO counts are not a measured speedup.

---

---

## [3.2.1+build102626.022444] — 2026-10-26
### Priority 3 Quality Controls: Live Mip Bias Slider, Custom Shadow Reach & Auto Models Policy

- **Live DLSS Texture Mip Bias Slider (`dlss_mip_offset`)**:
  - Reused `TemporalUpscaler::SceneMipBias()` evaluated live per draw in `vk_rasterizer.cpp` so slider changes take effect immediately on subsequent frames without restarting the engine.
  - Added "DLSS texture mip offset" slider `[-2.0f, 0.0f]` to the in-game ImGui overlay (default `0.0f`).
  - Respected `BB_DLSS_MIP_OFFSET` environment precedence; guaranteed `0.0f` bias for native rendering and TAA.
- **Custom Ray-Traced Shadow Reach Override (`rt_shadow_reach_custom`)**:
  - Introduced `rt_shadow_reach_custom` bounded to `[0.0f, 150.0f]` in `bbport_settings.h` and `bbport_settings.cpp`.
  - Strictly preserved quality tier defaults across standard presets (`RtLow`, `RtMedium`, `RtHigh`, `RtUltra`).
  - Custom reach applies only when `ray_tracing == RtCustom` and `rt_shadow_reach_custom > 0.0f` (clamped to `[1.0f, 150.0f]`). Setting `0.0f` cleanly delegates back to the shadow tier default.
  - Added "Custom shadow distance" slider in in-game overlay with dynamic `Default (X m)` indicator when $\le 0.0\text{ m}$.
  - Maintained 100% backward compatibility for legacy `rt_shadow_reach` migrations.
- **Auto Models Policy Formalization**:
  - Formalized GPU generation policy: Model K (preset 11) for RTX 20/30 (Turing/Ampere) to avoid non-FP8 performance penalty; Model M (preset 13) for RTX 40/50 with Model L (preset 12) for Ultra Performance; driver default 0 on unknown GPUs.
  - Preserved manual choices (J, K, M, L) and rejected deprecated presets E and F.
  - Verified via unit test suite `nvidia-gpu-test`.
- **Unit Test Coverage**:
  - Added test cases in `test_dlss_model_settings.cpp` and `test_rt_settings.cpp` covering parsing, clamping, persistence, tier preservation, custom overrides, and environment precedence. All tests passed.
- **Distribution Package Audit & Packaging**:
  - Rebuilt pristine release archive `dist/bbport-windows.zip` and versioned archive `dist/bbport-windows-v3.2.1.zip` (321,507,050 bytes / 306.61 MiB, SHA-256 `f6a0191e48734882f9f467ed1c997e7d875763b285b6e2f0ffee761049f49c2d`).
  - Automatically unzipped into `dist/bbport-windows/` preserving user save data and custom settings.
  - Recorded verification hashes in `bloodborne_pc/out/package-audit-verification.json`.

---

## [3.2.0] — 2026-10-26
### DLSS-G ABI 2, Reflex Low-Latency Coupling, Runtime Telemetry & Bundled Atlas

- **DLSS Frame Generation ABI 2 Bridge**:
  - Rebuilt native `bbport_dlss.dll` bridge implementing ABI 2 with full Frame Generation lifecycle management, parameter propagation, and swapchain recreation callbacks.
  - Verified on NVIDIA GeForce RTX 4090: native DLSS-G 2x delivering 4K 120 FPS output, DLSS 4.5 Model M active (2560x1440 render), zero FSR fallback, zero old-bridge warnings.
- **Unified Reflex Low-Latency Coupling**:
  - Enforced engine-level coupling policy via `EffectiveReflexMode`: activating DLSS Frame Generation automatically promotes effective Reflex to `On` (preserving `Boost` if requested) to mitigate frame queuing delay.
  - Live latency diagnostics: queries `vkGetLatencyTimingsNV` and streams live average frame-start to present latency (measured at 9.5–12.7 ms on RTX 4090 at 120 FPS).
- **Bounded Lock-Free Runtime Status Channel (`BbSettings::RuntimeStatus`)**:
  - Thread-safe atomic channel tracking active upscaler, quality preset, DLSS model, upscaler problems, FG provider, multiplier, fallback reason, effective Reflex, forced Reflex, measured latency in ms, render/present FPS, and HDR swapchain.
  - Stale detection defined at 2000 ms; fully integrated into the in-game ImGui overlay (`bbport_overlay.cpp`).
  - Unit test suite added in `test_dlss_model_settings.cpp` verifying policy, auto-promotion, and staleness.
- **Ray Tracing Containment & Filtering Refinements**:
  - Safely isolated reflection prototype from shadow mask pass to prevent corrupting directional moon shadows; disabled unsafe UI controls with clear hints.
  - Extended scalar history clamping to checkerboard-unsampled pixels using same-depth neighbors in `rt_filter.comp`.
  - Added bounded highlight shoulder to HDR tonemapper in `post_process.frag`.
- **Bundled Hunter's Atlas & Native Lamp Travel**:
  - Packaged 16 pre-compiled area maps and vector art directly into `dist/bbport-windows/atlas/`, eliminating separate map preparation steps.
  - Verified live in-game native lamp travel executing on the main game thread (`queued to 2402950`) warping to area `m24` without stalling or crashing.
- **Distribution Package Audit & Packaging**:
  - Rebuilt pristine release archive `dist/bbport-windows.zip` (321,505,186 bytes / 306.61 MiB, SHA-256 `fefdaed8a92a894c90548a4df98a2f9b77122d4e420ec7da6272404a240d32e4`).
  - Recorded verification hashes in `package-audit-verification.json`.
  - Verified clean exit code 0 via in-game PC Menu (`Quit Game`).

---

## [3.1.0] — 2026-10-25
### True HDR, Screen-Space Ray-Traced Water Reflections, PGO & Anti-Ghosting

- **Profile-Guided Optimization (PGO) & ThinLTO**:
  - Integrated Clang IR instrumentation and profile ingestion via `llvm-profdata merge` in `build.sh` and `CMakeLists.txt`.
  - Captured 108B execution count profile across 18,203 functions in gameplay tours, generating `pgo/bbgpu.profdata` (5.0 MB) to optimize branch layouts in core GPU paths (`PostDraw`, `RecorderThread`, `ApplyGraphicsRegisterPacket`, `ImageResource::Fetch`).
  - ThinLTO enabled by default (`BB_LTO=ON`) with persistent compiler cache.
- **Screen-Space Ray-Traced Water Reflections (`rt_reflections`)**:
  - Added hybrid planar/ray-traced reflection pass with Schlick Fresnel ($F_0 \approx 0.04$) against TLAS in `rt_trace.comp` and `rt_apply.comp`.
  - Dedicated `Kind::Reflection` screen effect pipeline in `vk_rt_screen_effect.cpp` and `vk_rt_effects.cpp` with a-trous spatial/temporal filtering.
  - Fully integrated into `bbport_settings`, launcher UI/backend, and in-game ImGui overlay.
- **True HDR (High Dynamic Range) & Rec. 2020**:
  - Native `VK_COLOR_SPACE_HDR10_ST2084_EXT` support with SMPTE ST 2084 PQ EOTF transfer function.
  - Custom luminance tonemapper tuned for Bloodborne's deep blacks and incandescent firelight in `post_process.frag`.
  - Initial presenter-thread HDR swapchain support (`VK_FORMAT_A2B10G10R10_UNORM_PACK32`); actual PC overlay compatibility was completed by the final SDR-composition/HDR-output integration documented above.
- **Anti-Ghosting Temporal History Clamping (RTG-5)**:
  - Implemented 3×3 color neighborhood bounding box history clamp in `rt_filter.comp` to eliminate 16–24 frame ghost trails from moving casters and dynamic cloaks.
- **Dynamic Secondary Light Sources (`rt_secondary_lights`)**:
  - Added settings plumbing across engine shim, launcher backend, and in-game menu.
- **Launcher System → Logs View**:
  - Added horizontal and vertical scroll bars via `ScrollView` in `SettingsWorkspace.qml` for comfortable in-launcher log inspection.

---

## [3.0.0+build261025.213313] — 2026-10-25
### RTX & Performance Enhancements

- **DLSS Model Auto-Selection**: Added `Auto: recommended for your GPU` to the launcher and engine. Automatically chooses DLSS 4 Model K on RTX 20/30 (avoiding FP8 penalties) and DLSS 4.5 Model M/L on RTX 40/50.
- **Half-Resolution Moon Shadows (`rt_shadow_half`)**: Added a new toggle under Custom Ray Tracing in launcher and in-game ImGui overlay. Uses edge-aware upsampling to save ~1.0 ms GPU frame time at 4K while preserving sharp contact shadows.
- **Automatic Reflex & Frame Gen Coupling**: Selecting DLSS Frame Generation automatically promotes NVIDIA Reflex to On to ensure minimal frame latency.
- **Dynamic Capsule Badges**: Home page frosted display capsule dynamically displays active features (`DLSS · FG · RT · Fullscreen`).
- **Dedicated `.githooks/` Architecture**: Configured Git `core.hooksPath = .githooks` with automated `pre-commit` version synchronization and `pre-push` validation.
- **Package Dependencies**: Added `keystone-engine>=0.9.2` to `pyproject.toml`.
- **Launcher Fixes**: Resolved typing, NoneType checks, and CUSTOM_BUILD attribute in `bbport_launcher_win.py`.

---

## [3.0.0] — 2026-10-25
### Milestone Release: SunBros Custom RT & DLSS Edition

- **SunBros Custom UI Launcher (v3.0)**:
  - Instant startup with no countdown delay.
  - Authentic gothic typography using official `fleshandblood` font with textured ivory drop shadow.
  - Hunter Dossier & Trophy Archive with decrypted save data status and 40 PlayStation trophy lore modals.
  - Modern obsidian dark palette eliminating legacy contrast issues.
  - Compact Hunt Mode selector (Offline, Online, Co-op).
- **Vulkan Real-Time Ray Tracing**:
  - Hardware-accelerated compute pipeline via 7 specialized compute shaders (`rt_trace`, `rt_filter`, `rt_instances`, `rt_gather`, `rt_apply`, `rt_check`, `rt_common`).
  - Ray-Traced Ambient Occlusion (RTAO) with physical contact shadows.
  - Ray-Traced directional Moon Shadows.
  - Real-time in-game hot-swapping via ImGui overlay.
- **NVIDIA DLSS 4.5 & Reflex**:
  - Full DLSS Frame Generation support targeting 4K 120 FPS via DLSS SDK 310.9.1 (`nvngx_dlssg.dll`) and `bbport_dlss.dll`.
  - DLSS model selection (Auto, K, M, L, J, Default).
  - NVIDIA Reflex Low Latency integration.
- **Multiplayer & Co-op (BBSC 0.0.2)**:
  - Seamless co-op integration with relay fallback (UDP port 3478).
  - Rejoin stability fixes ported from BBSC 0.0.2.
  - 60 FPS multi-hunter lock to eliminate game-speed drift while leaving solo uncapped.
  - Automated session backups to `user/coop-backups/`.
- **Packaging Pipeline**:
  - Standard `.zip` archives with clean forward-slash entries, locking process termination, and automated pristine unzipping verification.

---

## [2.6.0] — 2026-10-25
### UI/UX Redesign, Minimal Home Layout & Character Profile Modal

  - Decodes active save data (`user/savedata/`) across all supported title IDs (`CUSA00207`, `CUSA03173`, `CUSA01988`).
  - Displays Hunter name, character level badge, vital attributes (HP, Stamina, Discovery), and Blood Echoes in an authentic gothic card layout.
  - Interactive modal with clean fallback UI when save data is absent or unformatted.
  - Save file auto-detection automatically selects the most recent save slot.
  - Version tagging with timestamp metadata (`2.6.MMDDYYHHSS`).
  - Interactive popup modal showcasing all 40 official PlayStation trophies.
  - Bundled high-resolution trophy icons (`TROP000.PNG`–`TROP039.PNG`), lore descriptions, and unlock state tracking via `trophies.json`.
  - Integrated official Bloodborne font (`fleshandblood`) and title logo with textured ivory drop shadow.
  - SunBros Edition branding: integrated SunBros circular avatar crest into HomePage top-left status badge, Hunter Profile card, CharacterInfoModal dossier header, and version footer (`SunBros Edition · Game v01.09 · Launcher v2.6 · BBSC 0.0.2`).
  - Reorganized header: green "Ready" status badge at top-left, centered version footer at bottom.
  - Home background updated to custom Hunter artwork with gradient scrims.
  - Custom avatar system: support for custom hunter avatar auto-detection from `user/avatar.png` or path configuration in `settings.json`.
  - Redesigned home page: clean, minimalist layout with Bloodborne throne artwork background.
  - Replaced bulky stacked buttons with a sleek Hunt Mode selector:
    - **⚔ Offline**: Solo campaign without network connections.
    - **👁 Online**: The Hunter's Dream network (specters, bloodstains, messages via Discord auth).
    - **👥 Co-op**: Seamless cooperative multiplayer powered by BBSC 0.0.2.
  - Smaller Play button repositioned directly adjacent to the Settings icon.
  - Fixed window dimensions to 1200×800 (no resize/maximize) to eliminate UI distortion.
  - Removed placeholder Character Profile icon from navigation rail pending QML fix.
  - Expanded settings content area utilizing full 1200×800 window canvas.
  - Fixed Co-op FPS and server dropdown readability (resolved black text on dark background contrast bug).
  - Resolved Qt Quick loading errors and QML property binding issues; proper null/undefined handling in modals.
  - 4K DLSS Performance mode with FSR 4 frame generation fallback (2× interpolation).
  - 120 FPS co-op target with RTX 4090 optimization.
  - Created `SETUP.md` (environment setup, building launcher, PyInstaller troubleshooting) and `README-LAUNCHER-V26.md`.
  - Distribution ready: 273 MB TAR.GZ, 276 MB ZIP (660 MB uncompressed, 4495 files).

---

## [2.5.0] — 2026-10-25
### Initial Qt Quick Launcher & Toolchain Modernization

- **Modern Qt Quick Launcher Migration**:
  - Migrated frontend from legacy Tkinter interface to GPU-accelerated Qt Quick / PySide6 GUI (`Main.qml`).
  - Two-column task-based Settings hub categorizing options into Visuals, Controls, Game & Saves, Online, Co-op, Mods & Patches, and System.
  - Discrete bottom-center version watermark (`Game v01.09 · Launcher v2.5 · BBSC 0.0.2`).
  - Basic graphics configuration controls for presets, resolution, and window mode.
  - Configured `pyproject.toml` with strict `ruff`, `flake8`, and `mypy` formatting and static analysis rules.
  - Created `scripts/build_dist.py` for automated multi-threaded distribution packaging, normalized forward-slash `.zip` archive creation, process lock termination, and checksum generation.
  - Added `scripts/build_dist.ps1` PowerShell build helper.
  - Added `scripts/build-all.sh` for complete end-to-end MSYS2 CLANG64 compilation, DLSS bridge building, and packaging.
- **Jgamrot 2.1 + BBSC 0.0.2 Base Integration**:
  - Pinned Jgamrot 2.1 engine base (`af2baf3`) with BBSC 0.0.2 co-op support.
  - Working DLSS + DLSS Frame Generation (`nvngx_dlssg.dll`, `bbport_dlss.dll`).
  - Co-op relay fallback on UDP 3478 when direct P2P is blocked, and rejoin stability fixes.
  - Isolated launcher configuration directory (`%APPDATA%\bbport-launcher-bbsc002`).

---

## [2.1.0] — 2026-10-01
### Jgamrot 2.1 Base Engine Release

- **DLSS Frame Generation**: Motion vectors and jitter scaled to DLSS requirements; shutdown freeze resolved.
- **Mouse Flick Lock-on**: Quick sideways mouse flick switches lock-on targets (`mouse_flick_threshold` in `bbport.ini`).
- **Display & Resolution**: Added 1920×1200 (16:10) resolution in launcher and in-game menu; HUD composition starts at the proper draw.
- **FPS Falling Fix**: Resolved occlusion query order during long sessions and eliminated memory lookup slowdowns across loading screens.
- **Crash Fixes**: Prevented crash at offset `0x2169edc` when queries exhaust; unknown GPU commands now drop buffer with warning instead of terminating.
- **Internationalization**: Unlock Game Region applied to Spanish, Japanese, and other supported languages while preserving online connectivity.
- **Memory Management**: Low-VRAM profile for 4 GB GPUs with dynamic staging pool cleanup.

---

## [2.0.0] — 2026-09-20
### Community PRs & High Refresh Rate Release

- **120 / 144 FPS Support**: Native frame rate caps and display synchronization.
- **Discord Rich Presence**: Real-time area, boss fight, hunter level, Blood Echoes, and Insight broadcasting.
- **Clean Distribution**: Removed all proprietary game code from distribution archives.
- **TAA & Upscaling Improvements**: Depth-adaptive anti-aliasing and subpixel camera jittering.

---

## [1.6.4] — 2026-09-15
### Initial Windows Launcher & FSR 3.1 Release

- **Qt Quick Desktop Launcher**: Settings management for `bbport.ini`, mods, and save files.
- **AMD FSR 3.1 Integration**: FidelityFX Super Resolution upscaling and frame generation for all modern GPUs.
- **Controller & Input**: Full SDL3 gamepad mapping with keyboard/mouse emulation fallbacks.
- **Automated Setup Wizard**: Initial game folder detection and prerequisite verification.
