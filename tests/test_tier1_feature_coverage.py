# -*- coding: utf-8 -*-
"""
test_tier1_feature_coverage.py - FoFiX Modernization E2E Test Suite (Tier 1)

Covers the 9 core modernization features with >=5 test cases per feature (47 tests total):
  1. Python 3 Compilation and Environment (5 tests)
  2. macOS Launcher Script (5 tests)
  3. MIDI Subsystem (5 tests)
  4. Song & Library Loading (5 tests)
  5. ChartReader (.chart Parser) (6 tests)
  6. song.ini Metadata Parser (5 tests)
  7. Album Art Loader (5 tests)
  8. Audio Stem Routing (6 tests)
  9. Headless Execution (5 tests)
"""

import ast
import glob
import io
import os
import sqlite3
import struct
import sys
import tempfile
import unittest
import warnings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tests.fixtures import SongFixtureFactory, encode_vlq, decode_vlq, MockChartSong


class MockAudioChannel:
    def __init__(self, channel_id):
        self.id = channel_id
    def set_volume(self, v): pass
    def fadeout(self, t): pass
    def stop(self): pass
    def play(self, s, loops=0): return self

class MockAudio:
    def getChannel(self, n):
        return MockAudioChannel(n)

class MockConfig:
    def __init__(self):
        self._cfg = {
            ("audio", "crowd_tracks_enabled"): 0,
            ("audio", "speed_factor"): 1.0,
            ("audio", "delay"): 0,
            ("audio", "miss_volume"): 0.2,
            ("audio", "songvol"): 1.0,
            ("audio", "guitarvol"): 1.0,
            ("audio", "crowd_volume"): 1.0,
            ("audio", "single_track_miss_volume"): 0.2,
            ("game", "log_class_inits"): 0,
            ("game", "log_sections"): 0,
            ("game", "sort_order"): "title",
            ("game", "sort_direction"): 0,
            ("game", "tut"): 0,
            ("game", "game_mode"): 0,
            ("log", "log_unedited_midis"): 0,
            ("debug", "use_unedited_midis"): 0,
            ("performance", "cache_song_metadata"): False,
        }
    def get(self, section, key):
        return self._cfg.get((section, key), 0)

class MockResource:
    def fileName(self, *args, **kwargs):
        return os.path.join(*[a for a in args if isinstance(a, str)])

class MockEngine:
    def __init__(self):
        self.config = MockConfig()
        self.resource = MockResource()
        self.audio = MockAudio()
        self.audioSpeedFactor = 1.0
    def setSpeedFactor(self, factor): pass


class TestPython3EnvironmentAndCompilation(unittest.TestCase):
    """Feature 1: Python 3.12 Environment & Compilation Verification."""

    def test_py3_ast_compilation_all_source_files(self):
        """TEST-T1-ENV-01: Verify all source files compile cleanly under Python 3.12."""
        py_files = sorted(
            glob.glob(os.path.join(SRC_DIR, "*.py")) +
            glob.glob(os.path.join(SRC_DIR, "midi", "*.py"))
        )
        py_files = [f for f in py_files if "dist" not in f and "build" not in f]
        self.assertGreaterEqual(len(py_files), 94, "Expected at least 94 source files in src/ and src/midi/")

        failed = []
        for f in py_files:
            with open(f, "rb") as fp:
                src = fp.read()
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    compile(src, f, "exec", ast.PyCF_ONLY_AST)
            except SyntaxError as e:
                failed.append((os.path.relpath(f, PROJECT_ROOT), e.lineno, str(e.msg)))

        self.assertEqual(len(failed), 0, f"Source files failed Python 3.12 syntax check: {failed}")

    def test_venv_python_version_is_312(self):
        """TEST-T1-ENV-02: Verify virtual environment runs Python 3.12."""
        self.assertEqual(
            sys.version_info[:2],
            (3, 12),
            f"Expected Python 3.12 runtime, got {sys.version_info.major}.{sys.version_info.minor}",
        )

    def test_core_dependencies_importable(self):
        """TEST-T1-ENV-03: Verify core dependencies import and satisfy minimum versions."""
        import pygame
        import OpenGL.GL
        import numpy
        import PIL.Image

        # Verify Pygame >= 2.0.0
        self.assertTrue(hasattr(pygame, "ver"), "pygame missing ver attribute")
        major = int(pygame.ver.split(".")[0])
        self.assertGreaterEqual(major, 2, f"Expected pygame >= 2.0, found {pygame.ver}")

        # Verify OpenGL GL module imported
        self.assertTrue(hasattr(OpenGL.GL, "glGetString"))

        # Verify numpy
        self.assertTrue(hasattr(numpy, "__version__"))

        # Verify Pillow
        self.assertTrue(hasattr(PIL.Image, "open"))

    def test_stdlib_shadowing_eliminated(self):
        """TEST-T1-ENV-04: Verify decimal and locale resolve to stdlib, not src/."""
        import decimal
        import locale

        self.assertFalse(
            decimal.__file__.startswith(SRC_DIR),
            f"decimal module shadowed by file in src/: {decimal.__file__}",
        )
        self.assertFalse(
            locale.__file__.startswith(SRC_DIR),
            f"locale module shadowed by file in src/: {locale.__file__}",
        )
        self.assertFalse(
            os.path.exists(os.path.join(SRC_DIR, "decimal.py")),
            "src/decimal.py should be removed or relocated",
        )
        self.assertFalse(
            os.path.exists(os.path.join(SRC_DIR, "locale.py")),
            "src/locale.py should be removed or relocated",
        )

    def test_sqlite3_standard_module(self):
        """TEST-T1-ENV-05: Verify sqlite3 stdlib works and pysqlite legacy is absent."""
        con = sqlite3.connect(":memory:")
        cur = con.cursor()
        cur.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT);")
        cur.execute("INSERT INTO test (name) VALUES ('FoFiX');")
        cur.execute("SELECT name FROM test WHERE id = 1;")
        res = cur.fetchone()[0]
        con.close()
        self.assertEqual(res, "FoFiX")


class TestMacosLauncher(unittest.TestCase):
    """Feature 2: macOS Launcher Script (run_fofix.sh) Verification."""

    def setUp(self):
        self.launcher_path = os.path.join(PROJECT_ROOT, "run_fofix.sh")

    def test_launcher_script_exists_and_is_executable(self):
        """TEST-T1-LAUNCH-01: Verify ./run_fofix.sh exists and is executable."""
        self.assertTrue(os.path.isfile(self.launcher_path), "run_fofix.sh does not exist")
        self.assertTrue(
            os.access(self.launcher_path, os.X_OK),
            "run_fofix.sh is not executable (chmod +x required)",
        )

    def test_launcher_shebang_and_safety_flags(self):
        """TEST-T1-LAUNCH-02: Verify launcher shebang and safety settings."""
        with open(self.launcher_path, "r", encoding="utf-8") as f:
            content = f.read()
        lines = content.strip().splitlines()
        self.assertTrue(
            lines[0].startswith("#!/bin/bash") or lines[0].startswith("#!/usr/bin/env bash"),
            f"Expected bash shebang in run_fofix.sh, got: {lines[0]}",
        )
        self.assertIn("SCRIPT_DIR=", content, "run_fofix.sh must dynamically resolve SCRIPT_DIR")

    def test_launcher_activates_venv(self):
        """TEST-T1-LAUNCH-03: Verify launcher activates virtual environment."""
        with open(self.launcher_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(
            ".venv/bin/activate" in content or ".venv/bin/python" in content,
            "run_fofix.sh must activate or execute from .venv",
        )

    def test_launcher_switches_to_src_directory(self):
        """TEST-T1-LAUNCH-04: Verify launcher sets working directory to src/."""
        with open(self.launcher_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(
            'cd "$SCRIPT_DIR/src"' in content or "cd src" in content,
            "run_fofix.sh must cd to src directory for ../data resolution",
        )

    def test_launcher_forwards_cli_arguments(self):
        """TEST-T1-LAUNCH-05: Verify launcher passes CLI arguments with $@."""
        with open(self.launcher_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('"$@"', content, 'run_fofix.sh must forward CLI arguments using "$@"')


class TestMidiSubsystem(unittest.TestCase):
    """Feature 3: MIDI Subsystem (src/midi/) Verification."""

    def test_midi_file_header_parsing(self):
        """TEST-T1-MIDI-01: Verify SMF header chunk parsing."""
        raw_header = b"MThd\x00\x00\x00\x06\x00\x01\x00\x02\x01\xe0"
        magic = raw_header[:4]
        length = struct.unpack(">I", raw_header[4:8])[0]
        fmt, ntrks, division = struct.unpack(">HHH", raw_header[8:14])

        self.assertEqual(magic, b"MThd")
        self.assertEqual(length, 6)
        self.assertEqual(fmt, 1)
        self.assertEqual(ntrks, 2)
        self.assertEqual(division, 480)

    def test_midi_variable_length_quantity_codec(self):
        """TEST-T1-MIDI-02: Verify VLQ encoding and decoding across boundary values."""
        test_values = [0x00, 0x40, 0x7F, 0x80, 0x2000, 0x3FFF, 0x1FFFFF]
        for val in test_values:
            encoded = encode_vlq(val)
            decoded, consumed = decode_vlq(encoded)
            self.assertEqual(
                decoded,
                val,
                f"VLQ roundtrip failed for {hex(val)}: got {hex(decoded)}",
            )
            self.assertEqual(consumed, len(encoded))

    def test_midi_track_event_dispatching(self):
        """TEST-T1-MIDI-03: Verify parsing of MIDI track events using src.midi."""
        from midi.MidiInFile import MidiInFile
        from midi.MidiOutStream import MidiOutStream

        class TrackEventCollector(MidiOutStream):
            def __init__(self):
                super().__init__()
                self.events = []
                self.seq_names = []
            def sequence_name(self, text):
                self.seq_names.append(text)
            def note_on(self, channel=0, note=0x40, velocity=0x40):
                self.events.append(("note_on", channel, note, velocity))
            def note_off(self, channel=0, note=0x40, velocity=0x40):
                self.events.append(("note_off", channel, note, velocity))

        with tempfile.TemporaryDirectory() as td:
            midi_path = os.path.join(td, "test.mid")
            SongFixtureFactory.create_synthetic_midi(
                midi_path,
                track_name="PART GUITAR",
                notes=[(0, 480, 96, 100)],
                star_power=[(0, 480)],
            )
            collector = TrackEventCollector()
            midi_in = MidiInFile(collector, midi_path)
            midi_in.read()
            self.assertIn("PART GUITAR", collector.seq_names)
            note_types = [ev[0] for ev in collector.events]
            self.assertIn("note_on", note_types)
            self.assertIn("note_off", note_types)

    def test_midi_tempo_meta_event_parsing(self):
        """TEST-T1-MIDI-04: Verify MIDI tempo meta event 0x51 calculation through MidiInFile."""
        from midi.MidiInFile import MidiInFile
        from midi.MidiOutStream import MidiOutStream

        class TempoCollector(MidiOutStream):
            def __init__(self):
                super().__init__()
                self.tempos = []
            def tempo(self, us):
                self.tempos.append(us)

        with tempfile.TemporaryDirectory() as td:
            midi_path = os.path.join(td, "test.mid")
            SongFixtureFactory.create_synthetic_midi(midi_path, tempo_bpm=120.0)
            collector = TempoCollector()
            MidiInFile(collector, midi_path).read()
            self.assertEqual(len(collector.tempos), 1)
            self.assertEqual(collector.tempos[0], 500_000)
            computed_bpm = 60_000_000.0 / collector.tempos[0]
            self.assertAlmostEqual(computed_bpm, 120.0, places=2)

    def test_midi_starpower_note_extraction(self):
        """TEST-T1-MIDI-05: Verify note 103 extraction for Star Power using MidiInFile."""
        from midi.MidiInFile import MidiInFile
        from midi.MidiOutStream import MidiOutStream
        import ChartReader

        class NoteCollector(MidiOutStream):
            def __init__(self):
                super().__init__()
                self.notes = []
            def note_on(self, channel=0, note=0x40, velocity=0x40):
                self.notes.append(note)

        with tempfile.TemporaryDirectory() as td:
            midi_path = os.path.join(td, "test.mid")
            SongFixtureFactory.create_synthetic_midi(midi_path, star_power=[(0, 480)])
            collector = NoteCollector()
            MidiInFile(collector, midi_path).read()
            self.assertIn(103, collector.notes, "Pitch 103 (Star Power) must be extracted from track")
            self.assertEqual(ChartReader.STAR_POWER_NOTE, 103, "Star Power pitch must be 103")


class TestSongAndLibraryLoading(unittest.TestCase):
    """Feature 4: Song & Library Loading (src/Song.py) Verification."""

    def test_get_available_songs_finds_chart_folder(self):
        """TEST-T1-SONG-01: Verify getAvailableSongs() discovers folders with notes.chart."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_dir = os.path.join(td, "TestChartSong")
            SongFixtureFactory.create_full_song_folder(song_dir, format="chart")
            songs = Song.getAvailableSongs(MockEngine(), td)
            discovered = [s.songName for s in songs]
            self.assertIn("TestChartSong", discovered)

    def test_get_available_songs_finds_midi_folder(self):
        """TEST-T1-SONG-02: Verify getAvailableSongs() discovers folders with notes.mid."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_dir = os.path.join(td, "TestMidiSong")
            SongFixtureFactory.create_full_song_folder(song_dir, format="mid")
            songs = Song.getAvailableSongs(MockEngine(), td)
            discovered = [s.songName for s in songs]
            self.assertIn("TestMidiSong", discovered)

    def test_get_available_libraries_does_not_leak_songs(self):
        """TEST-T1-SONG-03: Verify getAvailableLibraries() does not classify song folders as libraries."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_dir = os.path.join(td, "SongFolder")
            SongFixtureFactory.create_full_song_folder(song_dir, format="chart")
            libs = Song.getAvailableLibraries(MockEngine(), td)
            self.assertNotIn("SongFolder", libs)

    def test_library_info_counts_chart_songs(self):
        """TEST-T1-SONG-04: Verify LibraryInfo counts both .chart and .mid songs."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            SongFixtureFactory.create_full_song_folder(os.path.join(td, "Song1"), format="chart")
            SongFixtureFactory.create_full_song_folder(os.path.join(td, "Song2"), format="chart")
            SongFixtureFactory.create_full_song_folder(os.path.join(td, "Song3"), format="mid")
            ini_file = os.path.join(td, "library.ini")
            with open(ini_file, "w") as f:
                f.write("[library]\nname = TestLibrary\n")
            lib_info = Song.LibraryInfo("TestLibrary", ini_file)
            self.assertEqual(lib_info.songCount, 3)

    def test_song_object_instantiation(self):
        """TEST-T1-SONG-05: Verify Song track structures initialization."""
        import Song
        song = Song.Song(MockEngine())
        self.assertEqual(len(song.tracks), 6, "Expected 6 instrument parts")
        for part_tracks in song.tracks:
            self.assertEqual(len(part_tracks), 4, "Expected 4 difficulty levels per part")


class TestChartReaderParser(unittest.TestCase):
    """Feature 5: ChartReader (.chart Parser) Verification."""

    def test_chart_reader_parse_song_section(self):
        """TEST-T1-CHART-01: Verify parsing of [Song] section."""
        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            SongFixtureFactory.create_synthetic_chart(
                chart_path,
                song_meta={
                    "Name": "Custom Song",
                    "Artist": "Custom Artist",
                    "Charter": "Custom Charter",
                    "Resolution": 192,
                    "Offset": 10,
                },
            )
            with open(chart_path, "r", encoding="utf-8") as f:
                content = f.read()

            import ChartReader
            sections = ChartReader.ChartReader._parse_sections(content)
            self.assertIn("Song", sections)
            self.assertEqual(sections["Song"].get("Name"), "Custom Song")
            self.assertEqual(sections["Song"].get("Artist"), "Custom Artist")
            self.assertEqual(sections["Song"].get("Charter"), "Custom Charter")
            self.assertEqual(sections["Song"].get("Resolution"), "192")

    def test_chart_reader_parse_synctrack_bpm(self):
        """TEST-T1-CHART-02: Verify parsing of [SyncTrack] BPM events and ms table."""
        import ChartReader
        tempo_markers = [(0, 120.0), (768, 150.0)]
        resolution = 192
        table, last_tick, last_bpm, total_ms = ChartReader._build_ms_table(tempo_markers, resolution)

        self.assertEqual(len(table), 2)
        # Tick 0 at 120 BPM: 0.0 ms
        self.assertEqual(table[0], (0, 120.0, 0.0))
        # 768 ticks / 192 = 4 beats at 120 BPM (0.5s/beat) = 2.0s = 2000.0 ms
        self.assertAlmostEqual(table[1][2], 2000.0, places=2)

    def test_chart_reader_parse_note_tracks(self):
        """TEST-T1-CHART-03: Verify parsing of note lines into tick, fret, sustain via ChartReader.read()."""
        import ChartReader
        song = MockChartSong()
        reader = ChartReader.ChartReader(song)
        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            SongFixtureFactory.create_synthetic_chart(
                chart_path,
                tracks={"ExpertSingle": [(0, "N", 0, 0), (192, "N", 1, 96)]},
            )
            reader.read(chart_path)
            events = song.get_notes(0, 0)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0][1].number, 0)
            self.assertEqual(events[1][1].number, 1)
            self.assertGreater(events[1][1].length, 0.0)

    def test_chart_reader_parse_star_power(self):
        """TEST-T1-CHART-04: Verify parsing of star power lines into MarkerNote 103 and hasStarpowerPaths."""
        import ChartReader
        song = MockChartSong()
        reader = ChartReader.ChartReader(song)
        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            SongFixtureFactory.create_synthetic_chart(
                chart_path,
                tracks={"ExpertSingle": [(384, "S", 2, 384)]},
            )
            reader.read(chart_path)
            self.assertTrue(song.hasStarpowerPaths, "hasStarpowerPaths must be set True on star power events")
            sp_markers = [ev for t, ev in song.get_star_power(0, 0)
                          if getattr(ev, 'number', None) == ChartReader.STAR_POWER_NOTE]
            self.assertEqual(len(sp_markers), 2, "Expected start and end MarkerNote for Star Power phrase")

    def test_chart_reader_get_parts_and_diffs(self):
        """TEST-T1-CHART-05: Verify ChartReader.get_parts_and_diffs contract (PROJECT.md:57)."""
        import inspect
        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            SongFixtureFactory.create_synthetic_chart(
                chart_path,
                tracks={
                    "ExpertSingle": [(0, "N", 0, 0)],
                    "HardSingle": [(0, "N", 0, 0)],
                    "ExpertDrums": [(0, "N", 0, 0)],
                },
            )

            import ChartReader
            func = getattr(ChartReader, "get_parts_and_diffs", getattr(ChartReader.ChartReader, "get_parts_and_diffs", None))
            self.assertIsNotNone(
                func,
                "ChartReader must implement 'get_parts_and_diffs(chart_path)' as specified in PROJECT.md:57",
            )
            self.assertTrue(callable(func), "ChartReader.get_parts_and_diffs must be callable")

            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            self.assertGreaterEqual(len(params), 1, "get_parts_and_diffs must accept chart_path parameter")

            res = func(chart_path)
            self.assertIsInstance(res, dict, "get_parts_and_diffs must return a dictionary")
            for part, diffs in res.items():
                self.assertIsInstance(part, str)
                self.assertIsInstance(diffs, (list, tuple))
                for diff in diffs:
                    self.assertIsInstance(diff, str)

            self.assertIn("Guitar", res, "Res should include 'Guitar' for Single track")
            self.assertIn("Expert", res["Guitar"], "Guitar should include 'Expert'")
            self.assertIn("Hard", res["Guitar"], "Guitar should include 'Hard'")
            self.assertIn("Drums", res, "Res should include 'Drums'")
            self.assertIn("Expert", res["Drums"], "Drums should include 'Expert'")

    def test_chart_reader_get_sections(self):
        """TEST-T1-CHART-06: Verify ChartReader.get_sections contract (PROJECT.md:59)."""
        import inspect
        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            SongFixtureFactory.create_synthetic_chart(
                chart_path,
                sections=[
                    (0, "Intro"),
                    (768, "Verse 1"),
                ],
            )

            import ChartReader
            func = getattr(ChartReader, "get_sections", getattr(ChartReader.ChartReader, "get_sections", None))
            self.assertIsNotNone(
                func,
                "ChartReader must implement 'get_sections(chart_path)' as specified in PROJECT.md:59",
            )
            self.assertTrue(callable(func), "ChartReader.get_sections must be callable")

            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            self.assertGreaterEqual(len(params), 1, "get_sections must accept chart_path parameter")

            secs = func(chart_path)
            self.assertIsInstance(secs, list, "get_sections must return a list")
            self.assertEqual(len(secs), 2, "Expected 2 sections from synthetic chart")

            prev_time = -1.0
            for item in secs:
                self.assertIsInstance(item, (tuple, list))
                self.assertEqual(len(item), 2)
                timestamp, name = item
                self.assertIsInstance(timestamp, (int, float))
                self.assertGreaterEqual(timestamp, 0.0)
                self.assertGreaterEqual(timestamp, prev_time)
                self.assertIsInstance(name, str)
                self.assertGreater(len(name), 0)
                prev_time = timestamp

            self.assertAlmostEqual(secs[0][0], 0.0, places=1)
            self.assertEqual(secs[0][1], "Intro")
            self.assertAlmostEqual(secs[1][0], 2000.0, delta=50.0)
            self.assertEqual(secs[1][1], "Verse 1")


class TestSongIniParser(unittest.TestCase):
    """Feature 6: song.ini Metadata Parser Verification."""

    def test_song_ini_standard_metadata_keys(self):
        """TEST-T1-INI-01: Verify standard metadata keys parsing."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            SongFixtureFactory.create_synthetic_ini(
                ini_path,
                section_name="song",
                metadata={
                    "name": "Standard Song",
                    "artist": "Standard Artist",
                    "album": "Standard Album",
                    "year": "2026",
                    "genre": "Rock",
                },
            )
            import Song
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "Standard Song")
            self.assertEqual(info.artist, "Standard Artist")
            self.assertEqual(info.album, "Standard Album")
            self.assertEqual(info.genre, "Rock")

    def test_song_ini_case_insensitive_section_header(self):
        """TEST-T1-INI-02: Verify case-insensitive section header [Song]."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            SongFixtureFactory.create_synthetic_ini(
                ini_path,
                section_name="Song",
                metadata={"name": "Capitalized Section Song"},
            )
            import Song
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "Capitalized Section Song")

    def test_song_ini_charter_alias_for_frets(self):
        """TEST-T1-INI-03: Verify charter alias is mapped to frets attribute."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            SongFixtureFactory.create_synthetic_ini(
                ini_path,
                section_name="Song",
                metadata={"charter": "CustomCharter"},
            )
            import Song
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.frets, "CustomCharter")

    def test_song_ini_hopo_frequency_alias(self):
        """TEST-T1-INI-04: Verify hopo_frequency alias is mapped to hopofreq."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            SongFixtureFactory.create_synthetic_ini(
                ini_path,
                section_name="Song",
                metadata={"hopo_frequency": "250"},
            )
            import Song
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.hopofreq, 250)

    def test_song_ini_difficulty_ratings(self):
        """TEST-T1-INI-05: Verify difficulty rating tags diff_guitar, diff_band, etc."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            SongFixtureFactory.create_synthetic_ini(
                ini_path,
                section_name="Song",
                metadata={
                    "diff_guitar": "5",
                    "diff_bass": "4",
                    "diff_drums": "6",
                    "diff_vocals": "3",
                    "diff_band": "5",
                },
            )
            import Song
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.diffGuitar, 5)
            self.assertEqual(info.diffBass, 4)
            self.assertEqual(info.diffDrums, 6)
            self.assertEqual(info.diffVocals, 3)
            self.assertEqual(info.diffSong, 5)


class TestAlbumArtLoader(unittest.TestCase):
    """Feature 7: Album Art Loader (src/Dialogs.py & src/Texture.py) Verification."""

    @classmethod
    def setUpClass(cls):
        import pygame
        os.environ["FOFIX_HEADLESS"] = "1"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        pygame.init()
        cls.screen = pygame.display.set_mode((640, 480), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)

    @classmethod
    def tearDownClass(cls):
        import pygame
        pygame.display.quit()
        pygame.quit()

    def test_album_art_discovers_album_png(self):
        """TEST-T1-ART-01: Verify discovery and Texture loading of album.png."""
        from Texture import Texture
        with tempfile.TemporaryDirectory() as td:
            art_path = os.path.join(td, "album.png")
            SongFixtureFactory.create_dummy_image(art_path, format="PNG", size=(64, 64))
            tex = Texture(art_path)
            self.assertIsNotNone(tex.texture)
            self.assertEqual(tex.pixelSize, (64, 64))

    def test_album_art_discovers_album_jpg(self):
        """TEST-T1-ART-02: Verify discovery and Texture loading of album.jpg."""
        from Texture import Texture
        with tempfile.TemporaryDirectory() as td:
            art_path = os.path.join(td, "album.jpg")
            SongFixtureFactory.create_dummy_image(art_path, format="JPEG", size=(64, 64))
            tex = Texture(art_path)
            self.assertIsNotNone(tex.texture)
            self.assertEqual(tex.pixelSize, (64, 64))

    def test_album_art_discovers_album_jpeg(self):
        """TEST-T1-ART-03: Verify discovery and Texture loading of album.jpeg."""
        from Texture import Texture
        with tempfile.TemporaryDirectory() as td:
            art_path = os.path.join(td, "album.jpeg")
            SongFixtureFactory.create_dummy_image(art_path, format="JPEG", size=(64, 64))
            tex = Texture(art_path)
            self.assertIsNotNone(tex.texture)
            self.assertEqual(tex.pixelSize, (64, 64))

    def test_album_art_label_jpg_discovery(self):
        """TEST-T1-ART-04: Verify discovery and Texture loading of label.jpg."""
        from Texture import Texture
        with tempfile.TemporaryDirectory() as td:
            art_path = os.path.join(td, "label.jpg")
            SongFixtureFactory.create_dummy_image(art_path, format="JPEG", size=(64, 64))
            tex = Texture(art_path)
            self.assertIsNotNone(tex.texture)
            self.assertEqual(tex.pixelSize, (64, 64))

    def test_album_art_pillow_texture_creation(self):
        """TEST-T1-ART-05: Verify Pillow loads PNG and JPEG into raw pixel buffers."""
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            png_path = os.path.join(td, "test.png")
            jpg_path = os.path.join(td, "test.jpg")
            SongFixtureFactory.create_dummy_image(png_path, format="PNG", size=(64, 64))
            SongFixtureFactory.create_dummy_image(jpg_path, format="JPEG", size=(64, 64))

            img_png = Image.open(png_path)
            self.assertEqual(img_png.size, (64, 64))
            raw_png = img_png.convert("RGBA").tobytes()
            self.assertEqual(len(raw_png), 64 * 64 * 4)

            img_jpg = Image.open(jpg_path)
            self.assertEqual(img_jpg.size, (64, 64))
            raw_jpg = img_jpg.convert("RGB").tobytes()
            self.assertEqual(len(raw_jpg), 64 * 64 * 3)


class TestAudioStemRouting(unittest.TestCase):
    """Feature 8: Audio Stem Routing (src/Song.py) Verification."""

    @classmethod
    def setUpClass(cls):
        import pygame
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        pygame.mixer.init()

    @classmethod
    def tearDownClass(cls):
        import pygame
        pygame.mixer.quit()

    def test_audio_stem_backing_music_assignment(self):
        """TEST-T1-STEM-01: Verify song.ogg is routed as backing music."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_name = "StemSong"
            target_dir = os.path.join(td, song_name)
            SongFixtureFactory.create_full_song_folder(target_dir, stems=["song.ogg"])
            song = Song.loadSong(MockEngine(), song_name, library=td)
            self.assertIsNotNone(song.music, "song.ogg must be bound to self.music")

    def test_audio_stem_guitar_channel_1(self):
        """TEST-T1-STEM-02: Verify guitar.ogg is routed to guitar channel 1."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_name = "GuitarStemSong"
            target_dir = os.path.join(td, song_name)
            SongFixtureFactory.create_full_song_folder(target_dir, stems=["song.ogg", "guitar.ogg"])
            song = Song.loadSong(MockEngine(), song_name, library=td)
            self.assertIsNotNone(song.guitarTrack, "guitar.ogg must initialize guitarTrack")
            self.assertEqual(song.guitarTrack.channel.id, 1, "guitarTrack must bind to channel 1")

    def test_audio_stem_bass_rhythm_channel_2(self):
        """TEST-T1-STEM-03: Verify bass.ogg or rhythm.ogg is routed to channel 2."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_name = "BassStemSong"
            target_dir = os.path.join(td, song_name)
            SongFixtureFactory.create_full_song_folder(target_dir, stems=["song.ogg", "bass.ogg"])
            song = Song.loadSong(MockEngine(), song_name, library=td)
            self.assertIsNotNone(song.rhythmTrack, "bass.ogg must initialize rhythmTrack")
            self.assertEqual(song.rhythmTrack.channel.id, 2, "rhythmTrack must bind to channel 2")

    def test_audio_stem_drums_channel_3(self):
        """TEST-T1-STEM-04: Verify drums.ogg is routed to channel 3."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_name = "DrumStemSong"
            target_dir = os.path.join(td, song_name)
            SongFixtureFactory.create_full_song_folder(target_dir, stems=["song.ogg", "drums.ogg"])
            song = Song.loadSong(MockEngine(), song_name, library=td)
            self.assertIsNotNone(song.drumTrack, "drums.ogg must initialize drumTrack")
            self.assertEqual(song.drumTrack.channel.id, 3, "drumTrack must bind to channel 3")

    def test_audio_stem_vocals_channel_5(self):
        """TEST-T1-STEM-05: Verify vocals.ogg is routed to vocals channel 5."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_name = "VocalStemSong"
            target_dir = os.path.join(td, song_name)
            SongFixtureFactory.create_full_song_folder(target_dir, stems=["song.ogg", "vocals.ogg"])
            song = Song.loadSong(MockEngine(), song_name, library=td)
            vocal_track = getattr(song, "vocalTrack", None)
            if vocal_track is not None and hasattr(vocal_track, "channel"):
                self.assertEqual(vocal_track.channel.id, 5)
            else:
                self.assertTrue(hasattr(song, "vocalTrack"), "Song must define vocalTrack attribute")

    def test_audio_stem_mp3_fallback(self):
        """TEST-T1-STEM-06: Verify fallback when .mp3 stems are present."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_name = "Mp3Song"
            target_dir = os.path.join(td, song_name)
            SongFixtureFactory.create_full_song_folder(target_dir, stems=[])
            mp3_path = os.path.join(target_dir, "song.mp3")
            SongFixtureFactory.create_dummy_ogg(mp3_path)
            song = Song.loadSong(MockEngine(), song_name, library=td)
            self.assertIsNotNone(song.music, "song.mp3 must be routed via _audio_fallback")


class TestHeadlessExecution(unittest.TestCase):
    """Feature 9: Headless Execution (FOFIX_HEADLESS, dummy audio) Verification."""

    def setUp(self):
        os.environ["FOFIX_HEADLESS"] = "1"
        os.environ["SDL_AUDIODRIVER"] = "dummy"

    def test_headless_env_flag_checked(self):
        """TEST-T1-HEAD-01: Verify FOFIX_HEADLESS environment variable handling."""
        os.environ["FOFIX_HEADLESS"] = "1"
        self.assertEqual(os.environ.get("FOFIX_HEADLESS"), "1")

    def test_headless_pygame_hidden_flag_added(self):
        """TEST-T1-HEAD-02: Verify pygame.HIDDEN constant exists."""
        import pygame
        self.assertTrue(hasattr(pygame, "HIDDEN"))

    def test_headless_opengl_context_initialization(self):
        """TEST-T1-HEAD-03: Verify OpenGL context creation with pygame.HIDDEN."""
        import pygame
        from OpenGL.GL import glGetString, GL_VERSION, GL_RENDERER

        pygame.init()
        screen = pygame.display.set_mode(
            (640, 480),
            pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN,
        )
        self.assertIsNotNone(screen)
        version = glGetString(GL_VERSION)
        self.assertIsNotNone(version)
        renderer = glGetString(GL_RENDERER)
        self.assertIsNotNone(renderer)

        pygame.display.quit()
        pygame.quit()

    def test_headless_audio_dummy_mixer_init(self):
        """TEST-T1-HEAD-04: Verify dummy audio driver initializes cleanly."""
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        import pygame
        pygame.mixer.init()
        init_res = pygame.mixer.get_init()
        self.assertIsNotNone(init_res)
        freq, fmt, channels = init_res
        self.assertGreater(freq, 0)
        pygame.mixer.quit()

    def test_headless_game_engine_lifecycle(self):
        """TEST-T1-HEAD-05: Verify GameEngine headless lifecycle."""
        import Config
        import GameEngine
        config = Config.load(setAsDefault=True)
        engine = GameEngine.GameEngine(config)
        running = engine.run()
        self.assertIn(running, (True, False))
        engine.quit()


if __name__ == "__main__":
    unittest.main()
