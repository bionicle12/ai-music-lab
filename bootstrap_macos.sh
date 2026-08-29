#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PYTHON_BIN="${AI_MUSIC_BOOTSTRAP_PYTHON:-/opt/homebrew/bin/python3.11}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python 3.11 was not found at $PYTHON_BIN" >&2
  echo "Install Homebrew python@3.11 or set AI_MUSIC_BOOTSTRAP_PYTHON." >&2
  exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/scripts/bootstrap_macos.py"
