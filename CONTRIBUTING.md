# Contributing

Bug reports, fixes and features are welcome.

1. **Report first.** Open an [issue](https://github.com/wanderabyss/sunbros-bloodborne-launcher/issues/new/choose) with your graphics card and driver, the version (shown on the launcher's Home page), what happened, and `user\last_run.log`. Questions and setup help go to [Discussions](https://github.com/wanderabyss/sunbros-bloodborne-launcher/discussions).
2. **Branch and build.** Fork, branch from `main`, and build as in the [build guide](build.md): MSYS2 CLANG64 for the game, Visual Studio C++ Build Tools for the DLSS bridge, and a Windows Python 3.11+ with `pip install -e ".[dev]"` for the launcher.
3. **Test.** Run the Python suite (`python -m pytest bloodborne_pc/tests`) and the native `*-test` targets. Changes to rendering, upscaling or frame generation should also say what was checked in game: GPU, output size, settings, and the FPS / failed-present counters from the overlay or `last_run.log`.
4. **Keep it clean.** No game files, keys, saves, runtime DLLs beyond what their licences allow, or third-party mod files. Mark changes to vendored shadPS4 code with a `bbport:` comment (see `bloodborne_pc/gpu/VENDOR.txt`). Add a line to [Release_Notes.md](Release_Notes.md) for anything a player will notice.
5. **Open a pull request** against `main` saying what changed, why, and how it was tested. Accepted changes ship in the next release.

Contributions are accepted under the [LICENSE](LICENSE) (GPL-3.0-or-later). Code taken from other projects must keep its author and licence and be listed under *Third-party packages* in the [player guide](bloodborne_pc/README.md#third-party-packages).
