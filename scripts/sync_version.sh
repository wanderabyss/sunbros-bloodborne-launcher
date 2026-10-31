#!/usr/bin/env bash
# sync_version.sh
#
# Reads the latest release entry from Release_Notes.md and
# syncs it to pyproject.toml (and uv.lock).
#
# Usage:
#   bash scripts/sync_version.sh            # run manually from repo root
#   bash scripts/sync_version.sh --check    # exit 1 if out of sync, no write
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    PYTHON_CMD="py"
fi

exec "$PYTHON_CMD" "$REPO_ROOT/scripts/sync_version.py" "$@"