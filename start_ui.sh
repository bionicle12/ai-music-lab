#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PYTHON_BIN="$SCRIPT_DIR/.venv-ui/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "The UI environment is missing. Run ./bootstrap_macos.sh first." >&2
  exit 1
fi

export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
cd "$SCRIPT_DIR"

echo "AI Music Lab: http://127.0.0.1:7860  (Russian: /ru)"
echo "Stop: Ctrl+C"
exec "$PYTHON_BIN" -m music_lab_ui.app
