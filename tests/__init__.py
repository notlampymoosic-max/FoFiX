# -*- coding: utf-8 -*-
"""
FoFiX E2E Test Suite Package Initialization
Ensures:
  1. src/ is on sys.path.
  2. Working directory is set to src/ for ../data resolution.
  3. Headless environment variables are configured.
"""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

# Configure environment variables for headless execution
os.environ.setdefault("FOFIX_HEADLESS", "1")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Guarantee src/ is at the head of sys.path
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Switch working directory to src/ if not already there
# This is required so Version.dataPath() ('../data') resolves to PROJECT_ROOT/data
if os.path.basename(os.getcwd()) != "src" and os.path.isdir(SRC_DIR):
    try:
        os.chdir(SRC_DIR)
    except OSError:
        pass
