# Hunter's Atlas

The full-screen map is [Hunter's Atlas](https://github.com/MikeTat1988/HuntersAtlas) by
MikeTat1988 (GPL-2.0, `LICENSE-GPL-2.0.txt`), version 1.2 (commit b1d6272, 2026-10-17), built
into the port instead of installed over the launcher.

- `generator/`: Atlas's map generator, unchanged (`source/generator/src`). It reads the player's
  own game files and writes the maps, the place names, the lamp and pickup markers and the map
  font. No game file or generated map is in this repository or in the release.
- `art/`: Atlas's own art and its fallback font (DejaVu, `LICENSE-DejaVu.txt`); `scripts/atlas.py`
  converts the pictures to the engine's BBRA format when the maps are prepared.
- The engine half is in `gpu/shim/bbport_map*.cpp`, `gpu/shim/bbport_atlas_*`,
  `src/runtime_map.c`, `src/runtime_atlas_state.c` and `src/runtime_menu_sound.c`, from Atlas's
  `source/native`, wired into this port's overlay, pad and audio code.

The launcher prepares the maps (*Settings → Mods & Patches → Hunter's Atlas → Prepare maps*), which
runs `scripts/atlas.py prepare`. A source checkout needs Python with the packages in
`generator/requirements-runtime.txt` (`BB_ATLAS_PYTHON` names that Python); the release ships the
generator frozen as `tools/atlas-generator/`.
