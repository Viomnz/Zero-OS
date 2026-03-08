#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SCRIPT_DIR/zero_os_ui.py"
fi

if command -v python >/dev/null 2>&1; then
  exec python "$SCRIPT_DIR/zero_os_ui.py"
fi

echo "Python is required to launch Zero OS UI." >&2
exit 1
