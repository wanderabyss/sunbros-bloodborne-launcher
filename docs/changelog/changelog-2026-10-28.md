# Changelog — October 28, 2026

### Brought in

- Launcher Command Center & Workspaces: `HomePage` Command Center dashboard, `VisualsStudio` (with top-level preset bar including `Remastered` and `HD Texture Pack` shortcut), `DossierWorkspace` (`StatRadar` + trophy filters), `MultiplayerWorkspace` (`CoopSetupPanel`), `PreferencesPage`, `DepthCard` 3D tilt effects, and opt-in background update downloader (`downloadUpdate`, `updateReady`).
- HD Texture Pack: Nexus Mods download (a link per file), picture-only pack builder, its own folder and the launcher's installed indicator (`HomePage` setup facts chip and `VisualsStudio`).
- Ray tracing "you can see" steps 1, 2, 3A and 6: debug views and compare split, stronger AO, ray-traced-only moon shadows, depth alpha test.
- DLSS 5 readiness, paused.

### Conflicts and decisions

- **HDR:** both builds had HDR10 output. The 3.2.x presentation-time conversion (validated for 18 min 46 s with DLSS 2×) is the only one. Old `bbport.ini` brightness lines are dropped on the next save. The window still reads Windows' SDR content brightness and the display's peak for the `Display: HDR on in Windows` log line.
- **Ray tracing:** both sides' controls and saved settings kept. `rt_filter.comp` applies the fast-band clamp, then the neighbour clamp. The reflection variant of `rt_trace.comp` now passes the frame constants that `Trace()` takes.
- **Presenter:** the DLSS 5 guard and frame-generation telemetry are both kept.
- **Launcher:** harmonized `HomePage.qml` (Command Center dashboard + `hdPackBadge` chip deep-linking to `Visuals` -> `High-resolution textures`), `VisualsStudio.qml` (top-level preset bar with `Remastered` and `HD Texture Pack` shortcut + `Qt.callLater` scroll-to-editor), `Main.qml` (`launcher.startPage` routing), `bbport_launcher_backend.py` (`_route` dict merge + `coopPlay` guards), and `bbport_launcher_win.py` (`INI_DEFAULTS` aligned with `bbport.ini` and `GRAPHICS_PRESETS['balanced']`, isolated `DATA_DIR` settings lookup).
- **Online:** `bloodborne_pc/gpu/bbnet/vendor` restored (it had been hidden by `.gitignore`).

### Validation

- Native build of `bb-probe`, `bb-play` and `bb-gpu-capabilities` passes and packaged into `bbport-windows-3.3.0`.
- Native tests pass: hdr-presentation, overlay-upload, render-maintenance, motion-history, presentation-telemetry, frame-handoff, frame-admission, reflex-handoff, motion-shader, ui-composition, p2p-relay, output-settings, dlss-settings, nvidia-gpu, rt-key-map, rt-settings.
- Python & QML integration suite: 104 tests and 63 subtests pass across `test_depth_workspaces_qml`, `test_home_dashboard_qml`, `test_coop_settings_qml`, `test_update_download_qml`, `test_workspace_navigation_qml`, `test_graphics_presets`, `test_launcher_hd_indicator`, `test_settings_navigation`, `test_setup_wizard`, `test_startup_routing`, `test_launcher_ray_tracing`, `test_launcher_updates`, `test_fromsoft`, `test_picture_gate`, and `test_hd_texture_pack`.
