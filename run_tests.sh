#!/usr/bin/env bash
set -e

# Resolve absolute path to project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_ACTIVATE="$SCRIPT_DIR/.venv/bin/activate"

# 1. Environment verification: Check Python virtual environment exists
if [ ! -f "$VENV_ACTIVATE" ]; then
    echo "ERROR: Virtual environment not found at $VENV_ACTIVATE" >&2
    echo "Please set up the Python 3.12 virtual environment first (Milestone M1)." >&2
    exit 2
fi

# 2. Activate virtual environment
# shellcheck source=/dev/null
source "$VENV_ACTIVATE" || {
    echo "ERROR: Failed to activate virtual environment at $VENV_ACTIVATE" >&2
    exit 2
}

# Verify python interpreter
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 interpreter not found in active virtual environment" >&2
    exit 2
fi

# 3. Configure headless and audio driver environment variables
export FOFIX_HEADLESS=1
export SDL_AUDIODRIVER=dummy
export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

# 4. Change working directory to src/ (required for native ../data asset resolution)
if [ ! -d "$SCRIPT_DIR/src" ]; then
    echo "ERROR: Source directory not found at $SCRIPT_DIR/src" >&2
    exit 2
fi

cd "$SCRIPT_DIR/src"

echo "======================================================================"
echo "FoFiX Modernization E2E Test Suite Runner (Tiers 1-4 + R5)"
echo "Interpreter: $(which python3)"
echo "CWD:         $(pwd)"
echo "Headless:    FOFIX_HEADLESS=${FOFIX_HEADLESS}, SDL_AUDIODRIVER=${SDL_AUDIODRIVER}"
echo "======================================================================"

# 5. Run test suite
set +e
if [ $# -gt 0 ]; then
    python3 -m unittest "$@"
    TEST_EXIT=$?
else
    python3 -m unittest discover -t .. -s ../tests -p "test_*.py" -v
    TEST_EXIT=$?
fi

if [ $TEST_EXIT -ne 0 ]; then
    echo "======================================================================"
    echo "Test suite failed with exit code $TEST_EXIT"
    echo "======================================================================"
    exit 1
fi

echo "======================================================================"
echo "All tests completed successfully."
echo "======================================================================"
exit 0
