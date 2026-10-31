# Launcher assets

The SunBro's Edition art (`hunter-icon.*`, `ui/sunbros-*.png`, `ui/bg/home.jpg` and `../art/`) is part of this project.

These files come from Bloodborne (Sony Interactive Entertainment, FromSoftware) and are **not** in the public source repository:

- `trophies/TROP*.PNG`: the game's trophy icons (the Dossier shows them)
- `ui/bloodborne-logo*.png` and `ui/bloodborne-font.*`: the game's logo and title font
- `ui/home-bg.jpg` and `ui/bg/*.jpg` except `home.jpg`: key art and blurred screenshots behind the launcher pages

The launcher runs without them: those images stay empty and the default font is used. To build with them, copy `launcher/assets` from a release zip (`bbport-windows-<version>/launcher/assets`) into this folder.
