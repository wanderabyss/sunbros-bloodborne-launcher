# Bloodborne PC Launcher v3.0 - Setup & Development Guide

This guide covers setting up the development environment, compiling the C++ Vulkan translation runtime, building the PySide6 Qt Quick Launcher v3.0, and packaging clean release distributions.

---

## 1. Prerequisites

### Tools & Compilers
- **Python 3.10+** (Python 3.12 or 3.13 recommended) from [python.org](https://www.python.org/).
- **MSYS2**: For C++ compilation via the `CLANG64` toolchain (`winget install MSYS2.MSYS2`).
- **Visual Studio 2022 Build Tools**: With *Desktop development with C++* and Windows 10/11 SDK.
- **NVIDIA DLSS SDK 310.9.16**: Cloned or placed in `vendor/nvidia-dlss/`.

### MSYS2 CLANG64 Packages
Open an MSYS2 CLANG64 shell and install the required dependencies:
```bash
pacman -Syu
pacman -S --needed \
    mingw-w64-clang-x86_64-clang \
    mingw-w64-clang-x86_64-ninja \
    mingw-w64-clang-x86_64-cmake \
    mingw-w64-clang-x86_64-pkgconf \
    mingw-w64-clang-x86_64-vulkan-headers \
    mingw-w64-clang-x86_64-vulkan-loader \
    mingw-w64-clang-x86_64-ffmpeg \
    mingw-w64-clang-x86_64-sdl3 \
    mingw-w64-clang-x86_64-glslang \
    mingw-w64-clang-x86_64-qt6-base \
    mingw-w64-clang-x86_64-qt6-declarative \
    mingw-w64-clang-x86_64-qt6-httpserver \
    mingw-w64-clang-x86_64-qt6-websockets
```

---

## 2. Python Environment Setup

From the repository root:

```powershell
# 1. Create virtual environment
python -m venv .venv

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Upgrade pip and install launcher requirements
pip install --upgrade pip
pip install -e ".[dev]"
pip install pyinstaller pillow certifi PySide6_Essentials==6.12.0
```

---

## 3. Building Core Engine & Binaries

### Option A: Automated Build Script (Recommended)
From the repository root, run the distribution build tool:
```powershell
# PowerShell wrapper
.\scripts\build_dist.ps1

# Or directly with Python
python scripts\build_dist.py
```
This automatically compiles C++ binaries via MSYS2, fetches frame generation shaders, builds the DLSS bridge, executes `package.sh`, generates a clean `.zip` archive, and unpacks it to `bloodborne_pc/dist/bbport-windows`.

### Option B: Manual Step-by-Step Compilation
Inside an MSYS2 CLANG64 shell:
```bash
cd /c/bbport/bloodborne_pc

# 1. Fetch FSR 4 frame generation compute shaders
bash tools/fetch_fsr4_assets.sh

# 2. Compile game core translation layer (Ninja + Clang)
bash build.sh

# 3. Compile DLSS bridge (MSVC + DLSS SDK)
DLSS_SDK_ROOT=../vendor/nvidia-dlss bash packaging/windows/build_dlss.sh

# 4. Build optional components
bash packaging/windows/build_coop_server.sh
bash packaging/windows/build_atlas_generator.sh

# 5. Stage distribution
bash packaging/windows/package.sh
```

---

## 4. Building the PySide6 Launcher

The SunBro's Edition launcher can be frozen into a standalone Windows binary using PyInstaller:

```powershell
cd C:\bbport\bloodborne_pc

# Run PyInstaller
python -m PyInstaller --noconfirm --clean --log-level ERROR --windowed `
  --name Bloodborne `
  --icon launcher/assets/hunter-icon.ico `
  --distpath out/pyi-dist `
  --workpath out/pyi-work `
  --specpath out/pyi-work `
  launcher/bbport_launcher_win.py

# Copy executable and QML assets to distribution
Copy-Item out\pyi-dist\Bloodborne\Bloodborne.exe dist\bbport-windows\ -Force
Copy-Item -Recurse launcher\qml dist\bbport-windows\launcher\ -Force
Copy-Item -Recurse launcher\assets dist\bbport-windows\launcher\ -Force
```

---

## 5. Running Automated Tests

Before submitting changes, run the test suites using the project virtual environment:

```powershell
# Ray Tracing settings and hot-swapping serialization
python bloodborne_pc/tests/test_launcher_ray_tracing.py

# BBSC 0.0.2 multiplayer handshake, P2P & relay fallback
python bloodborne_pc/tests/test_coop.py

# Launcher settings persistence & update channels
python bloodborne_pc/tests/test_launcher_updates.py

# Game engine patch generation & safety verification
python bloodborne_pc/tests/test_patches.py

# QML Component Syntax & Loading Verification
python -c "
import os, sys
os.environ['QT_QUICK_CONTROLS_STYLE'] = 'Basic'
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

app = QGuiApplication(sys.argv)
qml_dir = 'bloodborne_pc/launcher/qml'
for f in ['Main.qml', 'HomePage.qml', 'SettingsWorkspace.qml', 'CharacterPage.qml', 'CharacterInfoModal.qml']:
    engine = QQmlApplicationEngine()
    engine.addImportPath(qml_dir)
    engine.load(os.path.join(qml_dir, f))
    assert engine.rootObjects(), f'Failed to load {f}'
print('All QML views validated successfully.')
"
```

---

## 6. Packaging & Release Management

Distribution packaging is handled by `scripts/build_dist.py`:
- **Archive format**: Always `.zip` (standard DEFLATE compression level 6, entry paths use forward slashes).
- **Prohibited asset guard**: Enforces that no decrypted proprietary Sony game files (`eboot.bin`, `*.dcx`, `*.bdt`, `*.bhd`) are included.
- **Lock Management**: Automatically terminates orphaned processes holding file locks on `bloodborne_pc/dist/bbport-windows` before replacing files.
- **Fast Zipping Mode**:
  ```powershell
  python scripts/build_dist.py --only-zip
  ```

---

## 7. Future Architecture Roadmap

- [ ] **PGO & ThinLTO**: Profile-guided optimization and link-time optimization pipeline for 15-20% higher 1% low frame rates in Yharnam crowds.
- [ ] **DLSS 5 Readiness**: Architecture prepared for next-generation multi-frame generation bridges.
- [ ] **HDR & Rec. 2020 Tone Mapping**: High dynamic range display output with custom tone curve preserving Bloodborne's gothic blacks.
- [ ] **Dynamic Candle & Lantern Ray Tracing**: Extending RTAO compute shaders to evaluate dynamic secondary point lights.
- [ ] **Linux / Steam Deck Proton Packaging**: Flatpak / AppImage containerization targeting Steam Deck OLED at 60 FPS.
