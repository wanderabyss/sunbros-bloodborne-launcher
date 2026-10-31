#!/usr/bin/env bash
# scripts/build-all.sh
# --------------------
# All-in-one build and packaging script for MSYS2 CLANG64 shell.
# Builds binaries, tools, packages dist, and creates the distribution zip archive.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
BB_DIR="$REPO_ROOT/bloodborne_pc"
if [[ ! -d "$BB_DIR" ]]; then
    BB_DIR="$REPO_ROOT/src/bloodborne_pc"
fi
export BB_PACKAGE_NAME="${BB_PACKAGE_NAME:-bbport-windows}"

echo "======================================================================"
echo " Bloodborne PC - Build & Package All"
echo " Package Name: $BB_PACKAGE_NAME"
echo "======================================================================"

cd "$BB_DIR"
source ./msys2-env.sh

# 1. Fetch FSR 4 assets if script exists
if [[ -f tools/fetch_fsr4_assets.sh ]]; then
    echo ">>> [1/6] Fetching FSR 4 assets..."
    bash tools/fetch_fsr4_assets.sh || true
fi

# 2. Main C/C++ compilation
echo ">>> [2/6] Running build.sh..."
bash build.sh

# 3. DLSS Bridge (optional if vendor/nvidia-dlss exists)
DLSS_ROOT="${DLSS_SDK_ROOT:-$REPO_ROOT/vendor/nvidia-dlss}"
if [[ -d "$DLSS_ROOT" && -f packaging/windows/build_dlss.sh ]]; then
    echo ">>> [3/6] Building DLSS bridge..."
    DLSS_SDK_ROOT="$DLSS_ROOT" bash packaging/windows/build_dlss.sh || true
else
    echo ">>> [3/6] Skipping DLSS bridge (DLSS SDK not found at $DLSS_ROOT)."
fi

# 4. Co-op Server (optional)
if [[ -f packaging/windows/build_coop_server.sh ]]; then
    echo ">>> [4/6] Building co-op server..."
    bash packaging/windows/build_coop_server.sh || true
fi

# 5. Atlas generator (optional)
if [[ -f packaging/windows/build_atlas_generator.sh ]]; then
    echo ">>> [5/6] Building Hunter's Atlas generator..."
    bash packaging/windows/build_atlas_generator.sh || true
fi

# 6. Windows packaging & zip creation
echo ">>> [6/6] Packaging distribution & creating zip archive..."
bash packaging/windows/package.sh

echo "======================================================================"
echo " Build & packaging complete!"
echo " Output files located in: $BB_DIR/dist/"
echo "======================================================================"
