# -*- coding: utf-8 -*-
"""
test_tier2_boundary_corner_cases.py - FoFiX Modernization E2E Test Suite (Tier 2)

Covers 8 boundary and corner case domains with >=5 test cases per domain (40 tests total):
  1. Empty and Corrupted/Truncated Files (5 tests)
  2. Malformed song.ini Files (5 tests)
  3. Unicode & Special Characters in Song Metadata and Paths (5 tests)
  4. Non-Standard & Extreme Resolutions in .chart (5 tests)
  5. Extreme BPM Values in .chart (5 tests)
  6. Unsupported & Unknown Chart Elements (5 tests)
  7. Missing Optional Stems & Audio Edge Cases (5 tests)
  8. Non-Standard Resolutions & Display Settings in Headless Video (5 tests)
"""

import io
import os
import shutil
import struct
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tests.fixtures import SongFixtureFactory


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


class MockChartTrack:
    """Lightweight track mock for ChartReader event accumulation."""
    def __init__(self):
        self.allEvents = []

    def addEvent(self, time, event):
        self.allEvents.append((time, event))


class MockChartSong:
    """Lightweight Song mock satisfying ChartReader.read() contracts."""
    def __init__(self):
        # Support isolated execution if peer modules (Audio.py) are in transit
        import types
        if "Audio" not in sys.modules:
            try:
                import Audio
            except Exception:
                sys.modules["Audio"] = types.ModuleType("Audio")
        if "cPickle" not in sys.modules:
            import pickle
            sys.modules["cPickle"] = pickle

        import Song
        self.bpm = 120.0
        self.midiStyle = None
        self.hasStarpowerPaths = False
        self.parts = list(Song.parts.values())
        self.tempoEventTrack = MockChartTrack()
        self.eventTracks = [MockChartTrack() for _ in range(5)]
        self.midiEventTracks = [[MockChartTrack() for _ in range(4)] for _ in range(len(self.parts))]
        self.tracks = [[MockChartTrack() for _ in range(4)] for _ in range(len(self.parts))]

    def setBpm(self, bpm):
        self.bpm = bpm

    def get_notes(self, part_idx=0, diff_idx=0):
        """Returns list of (time_ms, note_event) for a given part and difficulty."""
        return self.tracks[part_idx][diff_idx].allEvents

    def get_star_power(self, part_idx=0, diff_idx=0):
        """Returns list of (time_ms, marker_event) for star power phrases."""
        return self.midiEventTracks[part_idx][diff_idx].allEvents


class TestEmptyAndCorruptFiles(unittest.TestCase):
    """Domain 1: Empty and Corrupted/Truncated Files."""

    def test_bnd_empty_chart_file(self):
        """TEST-T2-FILE-01: Verify 0-byte notes.chart does not crash ChartReader."""
        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            with open(chart_path, "wb") as f:
                pass  # 0 bytes

            import ChartReader
            sections = ChartReader.ChartReader._parse_sections("")
            self.assertEqual(sections, {})

    def test_bnd_truncated_chart_file(self):
        """TEST-T2-FILE-02: Verify truncated .chart file handles EOF gracefully."""
        truncated_content = "[Song]\n{\n  Name = \"Truncated\"\n"  # missing closing brace
        import ChartReader
        sections = ChartReader.ChartReader._parse_sections(truncated_content)
        self.assertIn("Song", sections)
        self.assertEqual(sections["Song"].get("Name"), "Truncated")

    def test_bnd_empty_midi_file(self):
        """TEST-T2-FILE-03: Verify 0-byte notes.mid is rejected gracefully."""
        from midi.MidiInFile import MidiInFile
        from midi.MidiToText import MidiToText

        with tempfile.TemporaryDirectory() as td:
            midi_path = os.path.join(td, "notes.mid")
            with open(midi_path, "wb") as f:
                pass
            with self.assertRaises((EOFError, TypeError, ValueError, IndexError)):
                MidiInFile(MidiToText(), midi_path).read()

    def test_bnd_corrupt_midi_header_magic(self):
        """TEST-T2-FILE-04: Verify notes.mid with corrupt magic bytes is rejected safely."""
        from midi.MidiInFile import MidiInFile
        from midi.MidiToText import MidiToText

        corrupt_bytes = b"CORR\x00\x00\x00\x06\x00\x01\x00\x02\x01\xe0"
        with tempfile.TemporaryDirectory() as td:
            midi_path = os.path.join(td, "corrupt.mid")
            with open(midi_path, "wb") as f:
                f.write(corrupt_bytes)
            with self.assertRaises((TypeError, ValueError)):
                MidiInFile(MidiToText(), midi_path).read()

    def test_bnd_zero_length_audio_stem(self):
        """TEST-T2-FILE-05: Verify 0-byte audio file is rejected cleanly by audio driver."""
        import pygame
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        pygame.mixer.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                stem_path = os.path.join(td, "song.ogg")
                with open(stem_path, "wb") as f:
                    pass
                with self.assertRaises(pygame.error):
                    pygame.mixer.Sound(stem_path)
        finally:
            pygame.mixer.quit()


class TestMalformedSongIni(unittest.TestCase):
    """Domain 2: Malformed song.ini Files."""

    def test_bnd_empty_song_ini(self):
        """TEST-T2-INI-01: Verify 0-byte song.ini defaults safely."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            with open(ini_path, "wb") as f:
                pass
            import Song
            info = Song.SongInfo(ini_path)
            self.assertIsNotNone(info.name)

    def test_bnd_song_ini_without_section_header(self):
        """TEST-T2-INI-02: Verify song.ini without section header handles safely."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            with open(ini_path, "w", encoding="utf-8") as f:
                f.write("name = HeaderlessSong\nartist = MysteryBand\n")
            import Song
            info = Song.SongInfo(ini_path)
            self.assertIsNotNone(info.name)

    def test_bnd_song_ini_invalid_data_types(self):
        """TEST-T2-INI-03: Verify non-numeric strings in numeric fields default safely."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            SongFixtureFactory.create_synthetic_ini(
                ini_path,
                section_name="song",
                metadata={
                    "name": "InvalidTypes",
                    "diff_guitar": "not_an_int",
                    "year": "twothousand",
                    "hopo_frequency": "invalid_freq",
                },
            )
            import Song
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.diffGuitar, -1)

    def test_bnd_song_ini_duplicate_keys(self):
        """TEST-T2-INI-04: Verify song.ini with duplicate keys is parsed without crash."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            with open(ini_path, "w", encoding="utf-8") as f:
                f.write("[song]\nname = First\nname = Second\nartist = Band\n")
            import Song
            info = Song.SongInfo(ini_path)
            self.assertIn(info.name, ("First", "Second"))

    def test_bnd_song_ini_stray_comments_and_binary(self):
        """TEST-T2-INI-05: Verify semicolons, comments, and whitespace are handled."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            with open(ini_path, "w", encoding="utf-8") as f:
                f.write("; Initial comment\n[song]\n# Hash comment\nname = Clean Song\nartist = Clean Artist\n")
            import Song
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "Clean Song")


class TestUnicodeAndSpecialCharacters(unittest.TestCase):
    """Domain 3: Unicode & Special Characters in Song Metadata and Paths."""

    def test_bnd_unicode_latin_accents_in_metadata(self):
        """TEST-T2-UNI-01: Verify Latin accented characters in metadata."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            SongFixtureFactory.create_synthetic_ini(
                ini_path,
                metadata={
                    "name": "Café con Leão",
                    "artist": "Sigur Rós",
                    "album": "Ágætis byrjun",
                },
            )
            import Song
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "Café con Leão")
            self.assertEqual(info.artist, "Sigur Rós")
            self.assertEqual(info.album, "Ágætis byrjun")

    def test_bnd_cjk_kanji_metadata(self):
        """TEST-T2-UNI-02: Verify CJK Japanese Kanji characters in metadata."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            SongFixtureFactory.create_synthetic_ini(
                ini_path,
                metadata={
                    "name": "残酷な天使のテーゼ",
                    "artist": "高橋洋子",
                },
            )
            import Song
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "残酷な天使のテーゼ")
            self.assertEqual(info.artist, "高橋洋子")

    def test_bnd_emoji_in_song_metadata(self):
        """TEST-T2-UNI-03: Verify emoji characters in song metadata."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            SongFixtureFactory.create_synthetic_ini(
                ini_path,
                metadata={
                    "name": "Rock & Roll 🎸🔥",
                    "artist": "Heavy Metal 🤘",
                },
            )
            import Song
            info = Song.SongInfo(ini_path)
            self.assertIn("🎸", info.name)

    def test_bnd_special_characters_in_folder_path(self):
        """TEST-T2-UNI-04: Verify song discovery in path containing brackets, spaces, hashes."""
        with tempfile.TemporaryDirectory() as td:
            complex_dir = os.path.join(td, "Pack [2026] #1", "Track (Special - 42)")
            os.makedirs(complex_dir, exist_ok=True)
            SongFixtureFactory.create_full_song_folder(
                complex_dir,
                format="chart",
                meta={"name": "Special Track"},
            )
            import Song
            ini_path = os.path.join(complex_dir, "song.ini")
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "Special Track")
            self.assertEqual(info.songName, "Track (Special - 42)")
            self.assertEqual(info.noteFileName, os.path.join(complex_dir, "notes.chart"))

    def test_bnd_utf8_bom_song_ini(self):
        """TEST-T2-UNI-05: Verify song.ini encoded with UTF-8 BOM is parsed cleanly."""
        with tempfile.TemporaryDirectory() as td:
            ini_path = os.path.join(td, "song.ini")
            bom_content = "\ufeff[song]\nname = BOM Song\nartist = BOM Artist\n"
            with open(ini_path, "w", encoding="utf-8-sig") as f:
                f.write(bom_content)

            import Song
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "BOM Song")


class TestNonStandardChartResolutions(unittest.TestCase):
    """Domain 4: Non-Standard & Extreme Resolutions in .chart."""

    def test_bnd_resolution_zero_fallback(self):
        """TEST-T2-RES-01: Verify Resolution = 0 falls back safely to default 192."""
        import ChartReader
        # Genuinely pass resolution = 0 to verify safe fallback without ZeroDivisionError
        table, last_tick, last_bpm, total_ms = ChartReader._build_ms_table([(0, 120.0)], 0)
        ms = ChartReader._ticks_to_ms(192, 0, table, last_tick, last_bpm, total_ms)
        self.assertAlmostEqual(ms, 500.0, places=2, msg="Resolution 0 must default to 192 PPQ (500ms at 120 BPM)")

    def test_bnd_resolution_negative_fallback(self):
        """TEST-T2-RES-02: Verify negative resolution falls back safely to default 192."""
        import ChartReader
        content = "[Song]\n{\n  Resolution = -480\n}\n"
        sections = ChartReader.ChartReader._parse_sections(content)
        raw_res = int(sections["Song"].get("Resolution", 192))
        # Pass negative resolution directly into ChartReader timing methods without local test-level sanitization
        table, last_tick, last_bpm, total_ms = ChartReader._build_ms_table([(0, 120.0)], raw_res)
        ms = ChartReader._ticks_to_ms(192, raw_res, table, last_tick, last_bpm, total_ms)
        self.assertAlmostEqual(ms, 500.0, places=2, msg="Negative resolution must default to 192 PPQ (500ms at 120 BPM)")

    def test_bnd_resolution_standard_480(self):
        """TEST-T2-RES-03: Verify Resolution = 480 calculates ms timing accurately via ChartReader."""
        import ChartReader
        table, last_tick, last_bpm, total_ms = ChartReader._build_ms_table([(0, 120.0)], 480)
        ms = ChartReader._ticks_to_ms(480, 480, table, last_tick, last_bpm, total_ms)
        self.assertAlmostEqual(ms, 500.0, places=2)

    def test_bnd_resolution_high_precision_960(self):
        """TEST-T2-RES-04: Verify Resolution = 960 converts high-precision ticks via ChartReader."""
        import ChartReader
        table, last_tick, last_bpm, total_ms = ChartReader._build_ms_table([(0, 120.0)], 960)
        ms = ChartReader._ticks_to_ms(960, 960, table, last_tick, last_bpm, total_ms)
        self.assertAlmostEqual(ms, 500.0, places=2)

    def test_bnd_resolution_non_standard_odd_value(self):
        """TEST-T2-RES-05: Verify non-standard odd resolution 193 computes safely via ChartReader."""
        import ChartReader
        table, last_tick, last_bpm, total_ms = ChartReader._build_ms_table([(0, 120.0)], 193)
        ms = ChartReader._ticks_to_ms(193, 193, table, last_tick, last_bpm, total_ms)
        self.assertAlmostEqual(ms, 500.0, places=2)


class TestExtremeBpmValues(unittest.TestCase):
    """Domain 5: Extreme BPM Values in .chart."""

    def test_bnd_bpm_zero_or_negative_fallback(self):
        """TEST-T2-BPM-01: Verify BPM <= 0 defaults safely to 120.0 BPM without ZeroDivisionError."""
        import ChartReader
        # Genuinely pass BPM = 0.0 to exercise division-by-zero protection
        table_zero, last_tick_zero, last_bpm_zero, total_ms_zero = ChartReader._build_ms_table([(0, 0.0)], 192)
        self.assertEqual(table_zero[0][1], 120.0, "BPM 0.0 must default safely to 120.0 BPM")
        ms_zero = ChartReader._ticks_to_ms(192, 192, table_zero, last_tick_zero, last_bpm_zero, total_ms_zero)
        self.assertAlmostEqual(ms_zero, 500.0, places=2, msg="BPM 0.0 must yield standard 120.0 BPM duration")

        # Genuinely pass negative BPM (-60.0) to exercise non-positive guard
        table_neg, last_tick_neg, last_bpm_neg, total_ms_neg = ChartReader._build_ms_table([(0, -60.0)], 192)
        self.assertEqual(table_neg[0][1], 120.0, "Negative BPM must default safely to 120.0 BPM")
        ms_neg = ChartReader._ticks_to_ms(192, 192, table_neg, last_tick_neg, last_bpm_neg, total_ms_neg)
        self.assertAlmostEqual(ms_neg, 500.0, places=2, msg="Negative BPM must yield standard 120.0 BPM duration")

    def test_bnd_bpm_extremely_slow(self):
        """TEST-T2-BPM-02: Verify extremely slow tempo (1.0 BPM) computes timestamps via ChartReader."""
        import ChartReader
        table, last_tick, last_bpm, total_ms = ChartReader._build_ms_table([(0, 1.0)], 192)
        ms = ChartReader._ticks_to_ms(192, 192, table, last_tick, last_bpm, total_ms)
        self.assertAlmostEqual(ms, 60000.0, places=2)

    def test_bnd_bpm_extremely_fast(self):
        """TEST-T2-BPM-03: Verify extremely fast tempo (5000.0 BPM) computes without overflow."""
        import ChartReader
        table, last_tick, last_bpm, total_ms = ChartReader._build_ms_table([(0, 5000.0)], 192)
        ms = ChartReader._ticks_to_ms(192, 192, table, last_tick, last_bpm, total_ms)
        self.assertAlmostEqual(ms, 12.0, places=2)

    def test_bnd_bpm_rapid_successive_tempo_changes(self):
        """TEST-T2-BPM-04: Verify rapid tempo changes in ChartReader._build_ms_table produce monotonic time."""
        import ChartReader
        tempo_markers = [(tick, 100.0 + (tick % 50)) for tick in range(0, 1000, 10)]
        table, _, _, _ = ChartReader._build_ms_table(tempo_markers, resolution=192)
        self.assertEqual(len(table), 100)
        for i in range(1, len(table)):
            self.assertGreater(table[i][2], table[i - 1][2], "Calculated ms must be strictly monotonic")

    def test_bnd_bpm_missing_initial_tick_zero_event(self):
        """TEST-T2-BPM-05: Verify first BPM event at tick > 0 defaults tick 0 to 120.0 in ChartReader."""
        import ChartReader
        content = "[SyncTrack]\n{\n  768 = B 140000\n}\n"
        sections = ChartReader.ChartReader._parse_sections(content)
        tempo_markers = []
        for line in sections.get("SyncTrack", []):
            tick, tokens = ChartReader.ChartReader._split_event(line)
            if tokens and tokens[0] == "B":
                tempo_markers.append((tick, int(tokens[1]) / 1000.0))

        # Do NOT manually insert (0, 120.0) here.
        # ChartReader._build_ms_table must autonomously prepend tick 0 at 120.0 BPM.
        table, last_tick, last_bpm, total_ms = ChartReader._build_ms_table(tempo_markers, 192)
        self.assertEqual(table[0], (0, 120.0, 0.0), "Table must autonomously start at tick 0 with 120.0 BPM")
        ms_at_0 = ChartReader._ticks_to_ms(0, 192, table, last_tick, last_bpm, total_ms)
        self.assertAlmostEqual(ms_at_0, 0.0, places=2, msg="Tick 0 timestamp must be 0.0 ms")
        ms_at_768 = ChartReader._ticks_to_ms(768, 192, table, last_tick, last_bpm, total_ms)
        self.assertAlmostEqual(ms_at_768, 2000.0, places=2, msg="Tick 768 must reflect elapsed time from tick 0 at 120 BPM")


class TestUnsupportedAndUnknownChartElements(unittest.TestCase):
    """Domain 6: Unsupported & Unknown Chart Elements."""

    def test_bnd_chart_unsupported_track_section_name(self):
        """TEST-T2-CHART-01: Verify unknown section header is skipped without crashing."""
        import ChartReader
        song = MockChartSong()
        reader = ChartReader.ChartReader(song)
        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            with open(chart_path, "w", encoding="utf-8") as f:
                f.write(
                    "[Song]\n{\n  Name = \"UnknownSectionTest\"\n  Resolution = 192\n}\n"
                    "[SyncTrack]\n{\n  0 = B 120000\n}\n"
                    "[ExpertUnrealInstrument]\n{\n  0 = N 0 0\n}\n"
                    "[ExpertSingle]\n{\n  0 = N 1 0\n}\n"
                )
            reader.read(chart_path)
            notes = song.get_notes(0, 0)
            self.assertEqual(len(notes), 1, "Only valid ExpertSingle note should be loaded")
            self.assertEqual(notes[0][1].number, 1, "Parsed note fret must match ExpertSingle event")
            self.assertNotIn("ExpertUnrealInstrument", ChartReader.CHART_TRACK_MAP)

    def test_bnd_chart_open_notes_fret_7(self):
        """TEST-T2-CHART-02: Verify fret 7 (open note) is handled gracefully and skipped."""
        import ChartReader
        song = MockChartSong()
        reader = ChartReader.ChartReader(song)
        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "open_notes.chart")
            with open(chart_path, "w", encoding="utf-8") as f:
                f.write(
                    "[Song]\n{\n  Resolution = 192\n}\n"
                    "[SyncTrack]\n{\n  0 = B 120000\n}\n"
                    "[ExpertSingle]\n{\n"
                    "  0 = N 7 0\n"       # Open note (unsupported, must be ignored)
                    "  192 = N 0 0\n"     # Normal green note (tick 192 = 500 ms)
                    "  384 = N 7 96\n"    # Open note with sustain (must be ignored)
                    "  576 = N 2 96\n"    # Normal yellow note (tick 576 = 1500 ms)
                    "}\n"
                )
            reader.read(chart_path)
            notes = song.get_notes(0, 0)
            self.assertEqual(len(notes), 2, "Open notes (fret 7) must be skipped; exactly 2 valid notes retained")
            # Verify valid notes are accurately parsed
            self.assertAlmostEqual(notes[0][0], 500.0, places=2)
            self.assertEqual(notes[0][1].number, 0)
            self.assertAlmostEqual(notes[1][0], 1500.0, places=2)
            self.assertEqual(notes[1][1].number, 2)
            # Verify no open note (7) leaked into track
            self.assertTrue(all(0 <= n.number <= 4 for _, n in notes), "All notes must be in standard range 0..4")
            self.assertFalse(any(n.number == 7 for _, n in notes), "No fret 7 open notes must exist in parsed track")

    def test_bnd_chart_stray_event_types(self):
        """TEST-T2-CHART-03: Verify unrecognized event types in SyncTrack, Events, and Tracks are skipped."""
        import Song
        import ChartReader
        song = MockChartSong()
        reader = ChartReader.ChartReader(song)
        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "stray_events.chart")
            with open(chart_path, "w", encoding="utf-8") as f:
                f.write(
                    "[Song]\n{\n  Resolution = 192\n}\n"
                    "[SyncTrack]\n{\n"
                    "  0 = B 120000\n"
                    "  100 = UNKNOWN_SYNC 1 2 3\n"
                    "  200 = TS 4\n"
                    "  300 = A 1000\n"
                    "}\n"
                    "[Events]\n{\n"
                    "  0 = UNKNOWN_EVENT \"foo\"\n"
                    "  192 = E \"section Verse 1\"\n"
                    "  384 = E \"phrase_start\"\n"
                    "}\n"
                    "[ExpertSingle]\n{\n"
                    "  0 = UNKNOWN_TRACK_EVENT 1 2 3\n"
                    "  50 = X 99 99\n"
                    "  192 = N 1 0\n"       # Valid note (500 ms)
                    "  384 = S 99 100\n"    # Unknown Star Power type (not type 2)
                    "  384 = S 2 192\n"     # Valid Star Power (type 2)
                    "  576 = TR 0 0\n"      # Unknown tremolo event
                    "  768 = N 3 0\n"       # Valid note (2000 ms)
                    "}\n"
                )
            reader.read(chart_path)
            notes = song.get_notes(0, 0)
            self.assertEqual(len(notes), 2, "Only 2 valid notes must be parsed despite stray events")
            self.assertEqual(notes[0][1].number, 1)
            self.assertEqual(notes[1][1].number, 3)

            sp_events = song.get_star_power(0, 0)
            self.assertEqual(len(sp_events), 2, "Only valid S 2 phrase should generate SP markers (start & end)")
            self.assertTrue(song.hasStarpowerPaths)

            sections = song.eventTracks[Song.TK_SECTIONS].allEvents
            self.assertEqual(len(sections), 1, "Only valid 'section' event should populate section markers")
            self.assertEqual(sections[0][1].text, "Verse 1")

    def test_bnd_chart_negative_ticks(self):
        """TEST-T2-CHART-04: Verify negative tick note and section events compute negative timestamps without crashing."""
        import Song
        import ChartReader
        song = MockChartSong()
        reader = ChartReader.ChartReader(song)
        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "negative_ticks.chart")
            with open(chart_path, "w", encoding="utf-8") as f:
                f.write(
                    "[Song]\n{\n  Resolution = 192\n}\n"
                    "[SyncTrack]\n{\n  0 = B 120000\n}\n"
                    "[Events]\n{\n"
                    "  -192 = E \"section CountIn\"\n"
                    "  0 = E \"section Intro\"\n"
                    "}\n"
                    "[ExpertSingle]\n{\n"
                    "  -192 = N 0 0\n"    # Pickup note before beat 0 (-500 ms)
                    "  0 = N 1 0\n"       # Beat 0 note (0 ms)
                    "  192 = N 2 96\n"    # Beat 1 note (500 ms)
                    "}\n"
                )
            reader.read(chart_path)
            notes = song.get_notes(0, 0)
            self.assertEqual(len(notes), 3, "All 3 notes including negative tick must be parsed")
            self.assertAlmostEqual(notes[0][0], -500.0, places=2, msg="Negative tick -192 must yield -500.0 ms")
            self.assertEqual(notes[0][1].number, 0)
            self.assertAlmostEqual(notes[1][0], 0.0, places=2)
            self.assertEqual(notes[1][1].number, 1)
            self.assertAlmostEqual(notes[2][0], 500.0, places=2)
            self.assertEqual(notes[2][1].number, 2)

            sections = song.eventTracks[Song.TK_SECTIONS].allEvents
            self.assertEqual(len(sections), 2, "Both negative and zero tick section markers must be parsed")
            self.assertAlmostEqual(sections[0][0], -500.0, places=2)
            self.assertEqual(sections[0][1].text, "CountIn")
            self.assertAlmostEqual(sections[1][0], 0.0, places=2)
            self.assertEqual(sections[1][1].text, "Intro")

    def test_bnd_chart_comments_inline_and_standalone(self):
        """TEST-T2-CHART-05: Verify // comments across sections and notes do not corrupt parsed data."""
        import ChartReader
        song = MockChartSong()
        reader = ChartReader.ChartReader(song)
        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "comments.chart")
            with open(chart_path, "w", encoding="utf-8") as f:
                f.write(
                    "// Header comment\n"
                    "[Song]\n{\n"
                    "  // Inside song comment\n"
                    "  Name = \"CleanName\"\n"
                    "  Resolution = 192\n"
                    "}\n"
                    "// Middle comment\n"
                    "[SyncTrack]\n{\n"
                    "  // Sync comment\n"
                    "  0 = B 120000\n"
                    "}\n"
                    "[ExpertSingle]\n{\n"
                    "  // Note comment\n"
                    "  0 = N 0 0\n"
                    "  // Another note comment\n"
                    "  192 = N 1 0\n"
                    "}\n"
                )
            reader.read(chart_path)
            notes = song.get_notes(0, 0)
            self.assertEqual(len(notes), 2, "Comments must not interfere with note count")
            self.assertEqual(notes[0][1].number, 0)
            self.assertEqual(notes[1][1].number, 1)

            # Also verify _parse_sections directly
            with open(chart_path, "r", encoding="utf-8") as f:
                sections = ChartReader.ChartReader._parse_sections(f.read())
            self.assertEqual(sections["Song"].get("Name"), "CleanName")


class TestMissingOptionalStems(unittest.TestCase):
    """Domain 7: Missing Optional Stems & Audio Edge Cases."""

    def test_bnd_stems_only_song_ogg_present(self):
        """TEST-T2-STEM-01: Verify single-track fallback when only song.ogg exists."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_name = "SingleSong"
            target_dir = os.path.join(td, song_name)
            SongFixtureFactory.create_full_song_folder(target_dir, stems=["song.ogg"])
            song = Song.loadSong(MockEngine(), song_name, library=td)
            self.assertIsNotNone(song.music)
            self.assertIsNone(song.guitarTrack)
            self.assertTrue(song.singleTrackSong)

    def test_bnd_stems_only_guitar_ogg_present(self):
        """TEST-T2-STEM-02: Verify guitar.ogg is promoted to songFile when song.ogg absent."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_name = "GuitarOnlySong"
            target_dir = os.path.join(td, song_name)
            SongFixtureFactory.create_full_song_folder(target_dir, stems=["guitar.ogg"])
            song = Song.loadSong(MockEngine(), song_name, library=td)
            self.assertIsNotNone(song.music, "guitar.ogg promoted to music when song.ogg missing")
            self.assertIsNone(song.guitarTrack)
            self.assertTrue(song.singleTrackSong)

    def test_bnd_stems_identical_file_size_deduplication(self):
        """TEST-T2-STEM-03: Verify identical file size between song.ogg and guitar.ogg deduplicates."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_name = "DupSong"
            target_dir = os.path.join(td, song_name)
            SongFixtureFactory.create_full_song_folder(target_dir, stems=["song.ogg", "guitar.ogg"])
            s1 = os.path.join(target_dir, "song.ogg")
            s2 = os.path.join(target_dir, "guitar.ogg")
            shutil.copyfile(s1, s2)
            song = Song.loadSong(MockEngine(), song_name, library=td)
            self.assertIsNotNone(song.music)
            self.assertIsNone(song.guitarTrack, "guitarTrack must be None when file size matches song.ogg")

    def test_bnd_stems_missing_rhythm_and_drums(self):
        """TEST-T2-STEM-04: Verify 2-stem song sets rhythm and drums to None."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_name = "TwoStemSong"
            target_dir = os.path.join(td, song_name)
            SongFixtureFactory.create_full_song_folder(target_dir, stems=["song.ogg", "guitar.ogg"])
            song = Song.loadSong(MockEngine(), song_name, library=td)
            self.assertIsNotNone(song.music)
            self.assertIsNotNone(song.guitarTrack)
            self.assertIsNone(song.rhythmTrack)
            self.assertIsNone(song.drumTrack)

    def test_bnd_stems_mixed_extensions(self):
        """TEST-T2-STEM-05: Verify mixed stem extensions (.ogg, .mp3) coexist."""
        import Song
        with tempfile.TemporaryDirectory() as td:
            song_name = "MixedStemSong"
            target_dir = os.path.join(td, song_name)
            SongFixtureFactory.create_full_song_folder(target_dir, stems=["song.ogg"])
            mp3_guitar = os.path.join(target_dir, "guitar.mp3")
            SongFixtureFactory.create_dummy_ogg(mp3_guitar)
            song = Song.loadSong(MockEngine(), song_name, library=td)
            self.assertIsNotNone(song.music)
            self.assertIsNotNone(song.guitarTrack)


class TestNonStandardVideoResolutions(unittest.TestCase):
    """Domain 8: Non-Standard Resolutions & Display Settings in Headless Video."""

    def setUp(self):
        os.environ["FOFIX_HEADLESS"] = "1"
        os.environ["SDL_AUDIODRIVER"] = "dummy"

    def tearDown(self):
        try:
            import pygame
            pygame.display.quit()
            pygame.quit()
        except Exception:
            pass

    def test_bnd_video_minimum_resolution_320x240(self):
        """TEST-T2-VID-01: Verify smallest standard resolution (320, 240) in hidden mode."""
        import pygame
        pygame.init()
        screen = pygame.display.set_mode((320, 240), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
        self.assertIsNotNone(screen)
        self.assertEqual(screen.get_size(), (320, 240))

    def test_bnd_video_standard_800x600(self):
        """TEST-T2-VID-02: Verify standard 800x600 resolution in hidden mode."""
        import pygame
        pygame.init()
        screen = pygame.display.set_mode((800, 600), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
        self.assertIsNotNone(screen)
        self.assertEqual(screen.get_size(), (800, 600))

    def test_bnd_video_widescreen_1920x1080(self):
        """TEST-T2-VID-03: Verify full HD 1080p (1920, 1080) resolution in hidden mode."""
        import pygame
        pygame.init()
        screen = pygame.display.set_mode((1920, 1080), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
        self.assertIsNotNone(screen)
        self.assertEqual(screen.get_size(), (1920, 1080))

    def test_bnd_video_widescreen_aspect_16_10(self):
        """TEST-T2-VID-04: Verify 16:10 aspect ratio (1680, 1050) in hidden mode."""
        import pygame
        pygame.init()
        screen = pygame.display.set_mode((1680, 1050), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
        self.assertIsNotNone(screen)
        self.assertEqual(screen.get_size(), (1680, 1050))

    def test_bnd_video_multiple_successive_flips(self):
        """TEST-T2-VID-05: Verify calling pygame.display.flip() 10 times in hidden mode maintains valid OpenGL context."""
        import pygame
        from OpenGL.GL import glGetError, GL_NO_ERROR

        pygame.init()
        screen = pygame.display.set_mode((640, 480), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
        self.assertIsNotNone(screen, "Display screen surface must not be None")
        for _ in range(10):
            pygame.display.flip()
        self.assertTrue(pygame.display.get_init(), "Display context must remain initialized")
        err = glGetError()
        self.assertEqual(err, GL_NO_ERROR, f"OpenGL reported error {err} after successive flips")
        self.assertEqual(pygame.display.get_surface().get_size(), (640, 480))


class TestTourLobbyNetworking(unittest.TestCase):
    """TEST-T2-TOUR: Verification of FakeNetworking, Phrasebook, and World Lobby messaging in Python 3."""

    def test_tour_lobby_phrasebook_serialization(self):
        """TEST-T2-TOUR-01: Verify CreatePlayer serialization across Phrasebook without dict_keys error."""
        import Session, World
        pb = Session.Phrasebook()
        msg = World.CreatePlayer(name="TourPlayer")
        packets = pb.encode(msg)
        self.assertGreaterEqual(len(packets), 1)

        pb2 = Session.Phrasebook()
        decoded_last = None
        for p in packets:
            dec = pb2.decode(p)
            if dec is not None:
                decoded_last = dec

        self.assertIsNotNone(decoded_last)
        self.assertEqual(decoded_last.name, "TourPlayer")

    def test_tour_lobby_fake_networking_bytes_transfer(self):
        """TEST-T2-TOUR-02: Verify FakeNetworking socket send/recv operates purely on bytes."""
        import FakeNetworking
        s1 = FakeNetworking.socket.socket(None, None, None)
        s1.bind(('127.0.0.1', 19876))
        s1.listen(1)

        s2 = FakeNetworking.socket.socket(None, None, None)
        s2.connect(('127.0.0.1', 19876))

        server_sock, _ = s1.accept()
        server_sock.send(b"PACKET_DATA")
        received = s2.recv(1024)
        self.assertEqual(received, b"PACKET_DATA")

        s1.close()
        s2.close()
        server_sock.close()

    def test_song_chooser_empty_library_resolution(self):
        """TEST-T2-SONGCHOOSER: Verify SongChooser safely defaults library to DEFAULT_LIBRARY without NoneType join error."""
        import Dialogs, Song
        from GameEngine import GameEngine
        engine = GameEngine()
        sc = Dialogs.SongChooser(engine, selectedLibrary=None, selectedSong=None)
        self.assertIn("songs", sc.library)
        self.assertGreaterEqual(len(sc.items), 1)
        engine.quit()


if __name__ == "__main__":
    unittest.main()
