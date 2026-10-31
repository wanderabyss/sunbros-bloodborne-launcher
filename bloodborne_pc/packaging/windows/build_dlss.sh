#!/usr/bin/env bash
# Builds bbport_dlss.dll (gpu/dlss_bridge, the only code that uses the NVIDIA DLSS SDK) with
# MSVC and puts it with NVIDIA's nvngx_dlss.dll (Super Resolution) and nvngx_dlssg.dll (Frame
# Generation) next to out/bb-probe.exe; package.sh ships them.
# Needs Visual Studio 2026 (Build Tools), CMake with VS 2026 support, and the NVIDIA DLSS SDK:
#   DLSS_SDK_ROOT=F:/sdk/DLSS bash packaging/windows/build_dlss.sh
# For VS 2022: DLSS_CMAKE_GENERATOR='Visual Studio 17 2022' DLSS_BUILD_DIR=out/dlss-bridge-vs17
set -euo pipefail
cd -- "$(dirname -- "$0")/../.."
sdk=${DLSS_SDK_ROOT:?Set DLSS_SDK_ROOT to a checkout of github.com/NVIDIA/DLSS}
cmake=${CMAKE_EXE:-cmake}
generator=${DLSS_CMAKE_GENERATOR:-Visual Studio 18 2026}
# A separate directory avoids reusing the old VS 2022 cache with a different generator.
build_dir=${DLSS_BUILD_DIR:-out/dlss-bridge-vs18}
# Only the Vulkan headers: MSYS2's C headers must not reach MSVC.
mkdir -p out/vkinclude
cp -r /c/msys64/clang64/include/vulkan /c/msys64/clang64/include/vk_video out/vkinclude/
"$cmake" -S gpu/dlss_bridge -B "$build_dir" -G "$generator" -A x64 \
    -DDLSS_SDK_ROOT="$(cygpath -m "$sdk")" -DVULKAN_INCLUDE="$(cygpath -m "$PWD/out/vkinclude")"
"$cmake" --build "$build_dir" --config Release
"$build_dir/Release/bbport-dlss-check.exe" "$build_dir/Release/bbport_dlss.dll"
cp "$build_dir/Release/bbport_dlss.dll" "$sdk/lib/Windows_x86_64/rel/nvngx_dlss.dll" \
    "$sdk/lib/Windows_x86_64/rel/nvngx_dlssg.dll" out/
cp "$sdk/LICENSE.txt" out/NVIDIA-DLSS-LICENSE.txt
echo "DLSS bridge ready: out/bbport_dlss.dll, out/nvngx_dlss.dll, out/nvngx_dlssg.dll"
# Optional: the bridge on NVIDIA Streamline (gpu/dlss_bridge_sl, BB_DLSS_BACKEND=streamline) in
# out/streamline with Streamline's signed runtime, from a Streamline SDK release:
#   STREAMLINE_SDK_ROOT=C:/path/to/streamline bash packaging/windows/build_dlss.sh
if [[ -n ${STREAMLINE_SDK_ROOT:-} ]]; then
    sl_build_dir=${DLSS_SL_BUILD_DIR:-out/dlss-sl-vs17}
    "$cmake" -S gpu/dlss_bridge_sl -B "$sl_build_dir" -G "$generator" -A x64 \
        -DSTREAMLINE_SDK_ROOT="$(cygpath -m "$STREAMLINE_SDK_ROOT")" \
        -DVULKAN_INCLUDE="$(cygpath -m "$PWD/out/vkinclude")"
    "$cmake" --build "$sl_build_dir" --config Release
    "$build_dir/Release/bbport-dlss-check.exe" "$sl_build_dir/Release/bbport_dlss_sl.dll"
    sl_bin=$STREAMLINE_SDK_ROOT/bin/x64
    rm -rf out/streamline && mkdir -p out/streamline
    cp "$sl_build_dir/Release/bbport_dlss_sl.dll" "$sl_bin/sl.interposer.dll" "$sl_bin/sl.common.dll" \
        "$sl_bin/sl.dlss.dll" "$sl_bin/nvngx_dlss.dll" "$sl_bin/nvngx_dlss.license.txt" out/streamline/
    cp "$STREAMLINE_SDK_ROOT/license.txt" out/streamline/Streamline-LICENSE.txt
    echo "Streamline DLSS bridge ready: out/streamline"
fi
