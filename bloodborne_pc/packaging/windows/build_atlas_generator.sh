#!/usr/bin/env bash
# Hunter's Atlas generator (tools/atlas/generator), frozen for the release as
# out/atlas-generator/generate_atlas.exe; package.sh copies it to tools/atlas-generator/.
# Needs a Windows Python (WINPYTHON or py) with network access for the pinned packages.
set -euo pipefail
cd "$(dirname "$0")/../.."
python=${WINPYTHON:-$(command -v py || true)}
[[ -n $python ]] || { echo 'Need a Windows Python (WINPYTHON=path\to\python.exe)' >&2; exit 1; }
export USERPROFILE=${USERPROFILE:-$(cygpath -w "/c/Users/$(id -un)")}
venv=out/atlas-venv
if [[ ! -x $venv/Scripts/python.exe ]]; then
    "$python" -m venv "$venv"
fi
"$venv/Scripts/python.exe" -m pip install -q --disable-pip-version-check \
    -r tools/atlas/generator/requirements-runtime.txt pyinstaller
src=$(cygpath -w "$PWD/tools/atlas/generator")
"$venv/Scripts/python.exe" -m PyInstaller --noconfirm --clean --log-level WARN --console \
    --name generate_atlas --distpath out/atlas-dist --workpath out/atlas-work --specpath out/atlas-work \
    --paths "$src" --collect-data soulstruct --copy-metadata soulstruct --copy-metadata constrata \
    --collect-all zstandard --hidden-import scipy.linalg --hidden-import scipy.sparse \
    $(for m in pipeline_context soulstruct_local_config generate_navigation_maps probe_markers \
               update_verified_markers generate_floorplans_v12 probe_gates extract_verified_gates \
               probe_location_names extract_subarea_names generate_map_v13 extract_native_map_font \
               extract_atlas_features; do echo --hidden-import "$m"; done) \
    --exclude-module matplotlib --exclude-module pandas --exclude-module tkinter \
    "$src\\generate_atlas.py"
rm -rf out/atlas-generator
mv out/atlas-dist/generate_atlas out/atlas-generator
echo "Built $PWD/out/atlas-generator/generate_atlas.exe"
