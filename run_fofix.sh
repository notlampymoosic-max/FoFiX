#!/usr/bin/env bash
set -e

# Resolve absolute path to the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Verify and activate Python 3.12 virtual environment
VENV_ACTIVATE="$SCRIPT_DIR/.venv/bin/activate"
if [ ! -f "$VENV_ACTIVATE" ]; then
  echo "Error: Python virtual environment not found at $VENV_ACTIVATE" >&2
  echo "Please set up the virtual environment first (e.g., /opt/homebrew/bin/python3.12 -m venv .venv)." >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$VENV_ACTIVATE"

# Export PYTHONPATH ensuring src/ is discoverable for flat imports
export PYTHONPATH="$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

# Change working directory to src/ (required for native ../data asset resolution)
cd "$SCRIPT_DIR/src"

# Execute FoFiX main entry point, replacing current shell process and forwarding all arguments
exec python3 FoFiX.py "$@"
