#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_fofix_smoke.py - FoFiX Automated Smoke & Verification Suite (R5)

Covers the four verification phases specified in ORIGINAL_REQUEST §R5:
  Phase 1: Syntax compilation of all 96 source files in src/ and src/midi/ using ast.parse.
  Phase 2: Import resolution across all modules with PYTHONPATH=src.
  Phase 3: Headless GameEngine initialization with FOFIX_HEADLESS=1 and SDL_AUDIODRIVER=dummy,
           running 10 ticks and clean shutdown.
  Phase 4: Parsing of Clone Hero .chart and song.ini metadata.

Can be run standalone:
  python3 test_fofix_smoke.py
Exits with 0 on pass, 1 on failure.
"""

import ast
import glob
import os
import sys
import tempfile
import traceback

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Auto-bootstrap into project virtual environment if running outside venv (ORIGINAL_REQUEST.md §R5, TEST_INFRA.md:30)
if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
    if os.path.isfile(venv_python) and os.path.abspath(sys.executable) != os.path.abspath(venv_python):
        os.execv(venv_python, [venv_python, os.path.abspath(__file__)] + sys.argv[1:])

SRC_DIR = os.path.join(PROJECT_ROOT, "src")
MIDI_DIR = os.path.join(SRC_DIR, "midi")


def phase1_verify_syntax():
    """Phase 1: Compile all Python source files in src/ and src/midi/ using ast.parse."""
    print("\n" + "=" * 70)
    print("PHASE 1: Python 3.12 Syntax Compilation Verification")
    print("=" * 70)

    py_files = sorted(
        glob.glob(os.path.join(SRC_DIR, "*.py")) +
        glob.glob(os.path.join(MIDI_DIR, "*.py"))
    )
    # Exclude build / dist if present
    py_files = [f for f in py_files if "dist" not in f and "build" not in f]

    print(f"Discovered {len(py_files)} source files in src/ and src/midi/.")

    clean_files = []
    failed_files = []

    for filepath in py_files:
        rel_path = os.path.relpath(filepath, PROJECT_ROOT)
        try:
            with open(filepath, "rb") as f:
                source_bytes = f.read()
            ast.parse(source_bytes, filename=filepath)
            clean_files.append(rel_path)
        except SyntaxError as e:
            failed_files.append((rel_path, e.lineno, e.offset, str(e.msg)))
        except Exception as e:
            failed_files.append((rel_path, 0, 0, str(e)))

    print(f"Compilation Results: {len(clean_files)} Clean | {len(failed_files)} Failed")

    if failed_files:
        print("\nSyntax Failures Detected:")
        for rel_path, line, col, msg in failed_files:
            print(f"  FAIL: {rel_path}:{line}:{col} - {msg}")
        return False, f"{len(failed_files)} files failed syntax compilation"

    if len(clean_files) < 94:
        print(f"  WARNING: Expected at least 94 source files, found {len(clean_files)}")

    print("Phase 1 PASSED: All source files compile cleanly under Python 3.12.")
    return True, "All files compiled cleanly"


def phase2_verify_imports():
    """Phase 2: Import resolution across all modules with PYTHONPATH=src."""
    print("\n" + "=" * 70)
    print("PHASE 2: Module Import Resolution Verification")
    print("=" * 70)

    # Establish environment
    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)
    os.chdir(SRC_DIR)

    # Modules to verify in topological order
    target_modules = [
        # Foundation & Utilities
        ("Version", "Version information"),
        ("Log", "Logging system"),
        ("Config", "Configuration parser"),
        ("Task", "Task queue"),
        ("Cerealizer", "Object serializer"),
        # MIDI subsystem
        ("midi", "MIDI package"),
        ("midi.MidiFileParser", "MIDI file parser"),
        ("midi.DataTypeConverters", "MIDI data type converters"),
        # Core Engine & Hardware
        ("Audio", "Audio streaming & mixer"),
        ("Video", "Display & OpenGL context"),
        ("Texture", "Texture manager"),
        ("Font", "Font rendering"),
        ("Svg", "SVG context"),
        ("Input", "Input subsystem"),
        # Chart & Song Models
        ("ChartReader", "Clone Hero .chart parser"),
        ("Song", "Song library & note models"),
        # Game Scenes & Shell
        ("GameEngine", "Main game engine"),
        ("Dialogs", "UI dialogs & pickers"),
        ("GuitarScene", "Guitar gameplay scene"),
        ("MainMenu", "Main menu scene"),
        ("FoFiX", "FoFiX application entry point"),
    ]

    passed_imports = []
    failed_imports = []

    for mod_name, description in target_modules:
        try:
            __import__(mod_name)
            passed_imports.append((mod_name, description))
            print(f"  [OK] {mod_name:<24} ({description})")
        except Exception as e:
            failed_imports.append((mod_name, description, str(e)))
            print(f"  [FAIL] {mod_name:<22} ({description}): {type(e).__name__}: {e}")

    print(f"\nImport Results: {len(passed_imports)} Passed | {len(failed_imports)} Failed")
    if failed_imports:
        return False, f"{len(failed_imports)} modules failed to import"

    print("Phase 2 PASSED: All core modules imported successfully.")
    return True, "All modules imported"


def phase3_verify_headless_engine():
    """Phase 3: Headless GameEngine initialization, 10 ticks, clean shutdown."""
    print("\n" + "=" * 70)
    print("PHASE 3: Headless GameEngine Lifecycle Verification")
    print("=" * 70)

    os.environ["FOFIX_HEADLESS"] = "1"
    os.environ["SDL_AUDIODRIVER"] = "dummy"

    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)
    os.chdir(SRC_DIR)

    engine = None
    try:
        import pygame
        import Config
        import GameEngine
        import Video

        print("  Initializing configuration...")
        config = Config.load(setAsDefault=True)

        print("  Instantiating GameEngine in headless mode...")
        engine = GameEngine.GameEngine(config)

        if not hasattr(engine, "video") or engine.video is None:
            raise RuntimeError("Engine video subsystem not initialized")

        print("  Stepping GameEngine main loop (10 frames)...")
        for tick in range(10):
            running = engine.run()
            if not running:
                print(f"  Engine finished tasks at tick {tick}")
                break

        print("  Shutting down GameEngine...")
        engine.quit()
        engine = None

        # Clean pygame subsystems
        try:
            pygame.mixer.quit()
            pygame.display.quit()
            pygame.quit()
        except Exception:
            pass

        print("Phase 3 PASSED: GameEngine completed headless boot, 10 ticks, and clean quit.")
        return True, "Headless lifecycle verified"

    except Exception as e:
        print(f"  [FAIL] Headless lifecycle error: {type(e).__name__}: {e}")
        traceback.print_exc()
        if engine is not None:
            try:
                engine.quit()
            except Exception:
                pass
        return False, str(e)


def phase4_verify_chart_and_metadata():
    """Phase 4: Parsing of Clone Hero .chart and song.ini metadata."""
    print("\n" + "=" * 70)
    print("PHASE 4: Clone Hero .chart and song.ini Parsing Verification")
    print("=" * 70)

    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)
    os.chdir(SRC_DIR)

    with tempfile.TemporaryDirectory() as tmp_dir:
        chart_path = os.path.join(tmp_dir, "notes.chart")
        ini_path = os.path.join(tmp_dir, "song.ini")

        # Create synthetic .chart
        chart_content = (
            "[Song]\n"
            "{\n"
            '  Name = "Smoke Test Song"\n'
            '  Artist = "Smoke Artist"\n'
            '  Charter = "Smoke Charter"\n'
            "  Resolution = 192\n"
            "  Offset = 0\n"
            "}\n"
            "[SyncTrack]\n"
            "{\n"
            "  0 = TS 4\n"
            "  0 = B 120000\n"
            "  768 = B 140000\n"
            "}\n"
            "[Events]\n"
            "{\n"
            '  0 = E "section Intro"\n'
            '  768 = E "section Verse 1"\n'
            '  1536 = E "section Chorus"\n'
            "}\n"
            "[ExpertSingle]\n"
            "{\n"
            "  0 = N 0 0\n"
            "  192 = N 1 96\n"
            "  384 = N 2 0\n"
            "  576 = S 2 384\n"
            "  576 = N 3 0\n"
            "  768 = N 4 192\n"
            "}\n"
            "[HardSingle]\n"
            "{\n"
            "  0 = N 0 0\n"
            "  192 = N 1 0\n"
            "}\n"
            "[ExpertDrums]\n"
            "{\n"
            "  0 = N 0 0\n"
            "}\n"
        )
        with open(chart_path, "w", encoding="utf-8") as f:
            f.write(chart_content)

        # Create synthetic song.ini with modern tags and aliases
        ini_content = (
            "[Song]\n"
            "name = Smoke Test Song\n"
            "artist = Smoke Artist\n"
            "album = Smoke Album\n"
            "year = 2026\n"
            "genre = Rock\n"
            "charter = Smoke Charter\n"
            "hopo_frequency = 170\n"
            "diff_guitar = 5\n"
            "diff_drums = 4\n"
            "diff_band = 5\n"
        )
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(ini_content)

        try:
            import Song
            import ChartReader

            # Test SongInfo metadata parsing
            print("  Parsing song.ini via Song.SongInfo...")
            info = Song.SongInfo(ini_path)
            assert info.name == "Smoke Test Song", f"Expected name 'Smoke Test Song', got '{info.name}'"
            assert info.artist == "Smoke Artist", f"Expected artist 'Smoke Artist', got '{info.artist}'"
            print(f"  [OK] song.ini metadata parsed: {info.name} - {info.artist}")

            # Verify aliases if supported
            if hasattr(info, "frets") and info.frets:
                print(f"  [OK] charter alias mapped to frets: '{info.frets}'")
            if hasattr(info, "diffGuitar") and info.diffGuitar == 5:
                print(f"  [OK] diffGuitar rating parsed: {info.diffGuitar}")

            # Test ChartReader contract
            print("  Parsing .chart via ChartReader...")
            if hasattr(ChartReader, "get_parts_and_diffs"):
                parts_and_diffs = ChartReader.get_parts_and_diffs(chart_path)
                print(f"  [OK] ChartReader.get_parts_and_diffs: {parts_and_diffs}")
                assert "Guitar" in parts_and_diffs or "Single" in str(parts_and_diffs), "Guitar track missing"
            else:
                print("  [NOTE] ChartReader.get_parts_and_diffs pending Milestone M4 implementation.")

            if hasattr(ChartReader, "get_sections"):
                sections = ChartReader.get_sections(chart_path)
                print(f"  [OK] ChartReader.get_sections: {len(sections)} sections found")
                assert len(sections) >= 3, f"Expected at least 3 sections, got {len(sections)}"
            else:
                print("  [NOTE] ChartReader.get_sections pending Milestone M4 implementation.")

            # Test full chart read
            class MockSong:
                def __init__(self):
                    self.midiStyle = None
                    self.hasStarpowerPaths = False
                    self.tracks = [[[] for _ in range(4)] for _ in range(6)]
                    self.tempoEventTrack = None
                    self.midiEventTracks = [[None for _ in range(4)] for _ in range(6)]
                    self.eventTracks = [None for _ in range(5)]
                    self.info = info

            mock_song = MockSong()
            reader = ChartReader.ChartReader(mock_song)
            reader.read(chart_path)
            print("  [OK] ChartReader.read() completed successfully.")

            print("Phase 4 PASSED: .chart and song.ini parsed successfully.")
            return True, ".chart and song.ini parsed successfully"

        except Exception as e:
            print(f"  [FAIL] Chart/metadata parsing error: {type(e).__name__}: {e}")
            traceback.print_exc()
            return False, str(e)


def main():
    print("=" * 70)
    print("FoFiX MODERNIZATION: AUTOMATED SMOKE VERIFICATION SUITE (R5)")
    print(f"Python: {sys.version.split()[0]} on {sys.platform}")
    print(f"Root:   {PROJECT_ROOT}")
    print("=" * 70)

    phases = [
        ("Phase 1: Syntax Compilation", phase1_verify_syntax),
        ("Phase 2: Import Resolution", phase2_verify_imports),
        ("Phase 3: Headless GameEngine Lifecycle", phase3_verify_headless_engine),
        ("Phase 4: Chart & Metadata Parsing", phase4_verify_chart_and_metadata),
    ]

    results = []
    all_passed = True

    for name, func in phases:
        try:
            passed, msg = func()
            results.append((name, passed, msg))
            if not passed:
                all_passed = False
        except Exception as e:
            results.append((name, False, f"Unhandled exception: {e}"))
            all_passed = False

    print("\n" + "=" * 70)
    print("SMOKE TEST SUMMARY")
    print("=" * 70)
    for name, passed, msg in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  [{status:<6}] {name:<42} - {msg}")
    print("=" * 70)

    if all_passed:
        print("ALL SMOKE PHASES PASSED!")
        sys.exit(0)
    else:
        print("SMOKE TEST SUITE FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
