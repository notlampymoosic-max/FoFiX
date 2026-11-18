# -*- coding: utf-8 -*-
"""
test_tier3_cross_feature_combinations.py - FoFiX Modernization E2E Test Suite (Tier 3)

Covers 10 pairwise cross-feature combination interactions:
  1. .chart + Multi-Track Stems (TEST-T3-PAIR-01)
  2. .mid + Clone Hero song.ini (TEST-T3-PAIR-02)
  3. .chart + album.jpg + song.ini (TEST-T3-PAIR-03)
  4. Headless GL + .chart Loading (TEST-T3-PAIR-04)
  5. Practice Sections + Note Timing (TEST-T3-PAIR-05)
  6. Tap Notes + hopo_frequency (TEST-T3-PAIR-06)
  7. .chart vs .mid Precedence (TEST-T3-PAIR-07)
  8. Headless Engine + Audio Stem Routing (TEST-T3-PAIR-08)
  9. song.ini vs [Song] Metadata Precedence (TEST-T3-PAIR-09)
  10. Unicode + album.png + Headless (TEST-T3-PAIR-10)
"""

import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tests.fixtures import SongFixtureFactory


class TestCrossFeatureCombinations(unittest.TestCase):
    """Pairwise Cross-Feature Combinations."""

    def setUp(self):
        os.environ["FOFIX_HEADLESS"] = "1"
        os.environ["SDL_AUDIODRIVER"] = "dummy"

    def tearDown(self):
        try:
            import pygame
            pygame.display.quit()
            pygame.mixer.quit()
            pygame.quit()
        except Exception:
            pass

    def test_cross_chart_and_multitrack_stems(self):
        """TEST-T3-PAIR-01: Pair .chart note tracks with multi-track audio stems."""
        import pygame
        import ChartReader

        with tempfile.TemporaryDirectory() as td:
            SongFixtureFactory.create_full_song_folder(
                td,
                format="chart",
                has_stems=True,
                stems=["song.ogg", "guitar.ogg", "bass.ogg", "drums.ogg"],
            )
            chart_path = os.path.join(td, "notes.chart")

            # 1. Parse .chart instrument tracks
            parts = ChartReader.get_parts_and_diffs(chart_path)
            self.assertIn("Guitar", parts, "Guitar part must be defined in chart")

            # 2. Verify all 4 stems decode as playable audio
            pygame.mixer.init()
            for stem in ["song.ogg", "guitar.ogg", "bass.ogg", "drums.ogg"]:
                snd = pygame.mixer.Sound(os.path.join(td, stem))
                self.assertGreater(snd.get_length(), 0.0)

            # 3. Verify track-to-channel routing rules via Song.loadSong
            import Song
            from tests.test_tier1_feature_coverage import MockEngine
            song_name = os.path.basename(td)
            lib_parent = os.path.dirname(td)
            song = Song.loadSong(MockEngine(), song_name, library=lib_parent)
            self.assertIsNotNone(song.music, "song.ogg must bind to music")
            self.assertIsNotNone(song.guitarTrack, "guitar.ogg must initialize guitarTrack")
            self.assertEqual(song.guitarTrack.channel.id, 1, "guitar.ogg must route to channel 1")
            self.assertIsNotNone(song.rhythmTrack, "bass.ogg must initialize rhythmTrack")
            self.assertEqual(song.rhythmTrack.channel.id, 2, "bass.ogg must route to channel 2")
            self.assertIsNotNone(song.drumTrack, "drums.ogg must initialize drumTrack")
            self.assertEqual(song.drumTrack.channel.id, 3, "drums.ogg must route to channel 3")

    def test_cross_midi_and_clonehero_song_ini(self):
        """TEST-T3-PAIR-02: Pair legacy MIDI notes.mid with modern song.ini aliases."""
        import Song
        from midi.MidiInFile import MidiInFile
        from midi.MidiOutStream import MidiOutStream

        class TrackEventCollector(MidiOutStream):
            def __init__(self):
                super().__init__()
                self.seq_names = []
            def sequence_name(self, text):
                self.seq_names.append(text)

        with tempfile.TemporaryDirectory() as td:
            SongFixtureFactory.create_full_song_folder(
                td,
                format="mid",
                ini_section="Song",
                meta={
                    "name": "Hybrid Midi Modern Song",
                    "artist": "Retro Band",
                    "charter": "ModernCharter",
                    "hopo_frequency": "200",
                    "diff_guitar": "4",
                },
            )
            ini_path = os.path.join(td, "song.ini")
            midi_path = os.path.join(td, "notes.mid")

            # 1. Genuine SongInfo parsing with alias mapping
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "Hybrid Midi Modern Song")
            self.assertEqual(info.frets, "ModernCharter")
            self.assertEqual(info.hopofreq, 200)
            self.assertEqual(info.diffGuitar, 4)
            self.assertTrue(info.noteFileName.endswith("notes.mid"))

            # 2. Genuine binary MIDI parsing alongside modern ini
            collector = TrackEventCollector()
            MidiInFile(collector, midi_path).read()
            self.assertIn("PART GUITAR", collector.seq_names)

    def test_cross_chart_album_jpg_and_song_ini(self):
        """TEST-T3-PAIR-03: Pair .chart, album.jpg, and song.ini in single song bundle."""
        from PIL import Image
        import Song
        import ChartReader

        with tempfile.TemporaryDirectory() as td:
            SongFixtureFactory.create_full_song_folder(
                td,
                format="chart",
                has_art=True,
                art_format="jpg",
                meta={
                    "name": "Album Art Song",
                    "artist": "Visual Artist",
                },
            )
            ini_path = os.path.join(td, "song.ini")
            chart_path = os.path.join(td, "notes.chart")
            art_path = os.path.join(td, "album.jpg")

            # 1. SongInfo metadata
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "Album Art Song")
            self.assertEqual(info.artist, "Visual Artist")
            self.assertTrue(info.noteFileName.endswith("notes.chart"))

            # 2. Album Art JPEG loading
            with Image.open(art_path) as img:
                self.assertEqual(img.format, "JPEG")
                self.assertEqual(img.size, (64, 64))

            # 3. ChartReader verification
            parts = ChartReader.get_parts_and_diffs(chart_path)
            self.assertIn("Guitar", parts)

    def test_cross_headless_and_chart_loading(self):
        """TEST-T3-PAIR-04: Pair headless OpenGL context with .chart parsing."""
        import pygame
        from OpenGL.GL import glClear, GL_COLOR_BUFFER_BIT, glGetError, GL_NO_ERROR
        import Song
        import ChartReader

        pygame.init()
        screen = pygame.display.set_mode((640, 480), pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN)
        self.assertIsNotNone(screen)

        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            SongFixtureFactory.create_synthetic_chart(chart_path)

            class SongHarness:
                def __init__(self):
                    self.parts = [Song.parts[Song.GUITAR_PART]]
                    self.bpm = 120.0
                    self.hasStarpowerPaths = False
                    self.midiStyle = None
                    self.tempoEventTrack = Song.TempoTrack(None)
                    self.eventTracks = [Song.Track(None) for _ in range(5)]
                    self.midiEventTracks = [[Song.Track(None) for _ in range(len(Song.difficulties))]]
                    self.tracks = [[Song.NoteTrack(None) for _ in range(len(Song.difficulties))]]
                def setBpm(self, bpm):
                    self.bpm = bpm

            harness = SongHarness()
            reader = ChartReader.ChartReader(harness)
            reader.read(chart_path)
            self.assertGreater(len(harness.tracks[0][0].allEvents), 0)

            # Execute OpenGL frame while holding chart in memory
            glClear(GL_COLOR_BUFFER_BIT)
            pygame.display.flip()
            self.assertEqual(glGetError(), GL_NO_ERROR)

    def test_cross_practice_sections_and_note_timing(self):
        """TEST-T3-PAIR-05: Pair practice section markers with note event timestamps."""
        import Song
        import ChartReader

        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            SongFixtureFactory.create_synthetic_chart(
                chart_path,
                sync_track=[(0, "TS", 4), (0, "B", 120000)],
                sections=[
                    (0, "Intro"),
                    (768, "Verse 1"),
                ],
                tracks={
                    "ExpertSingle": [
                        (0, "N", 0, 0),
                        (768, "N", 1, 0),
                    ]
                },
            )

            # 1. Parse sections via ChartReader.get_sections()
            sections = ChartReader.get_sections(chart_path)
            self.assertEqual(len(sections), 2)
            self.assertAlmostEqual(sections[0][0], 0.0, places=1)
            self.assertEqual(sections[0][1], "Intro")
            self.assertAlmostEqual(sections[1][0], 2000.0, places=1)
            self.assertEqual(sections[1][1], "Verse 1")

            # 2. Parse full chart and verify note timestamps match sections
            class SongHarness:
                def __init__(self):
                    self.parts = [Song.parts[Song.GUITAR_PART]]
                    self.bpm = 120.0
                    self.hasStarpowerPaths = False
                    self.midiStyle = None
                    self.tempoEventTrack = Song.TempoTrack(None)
                    self.eventTracks = [Song.Track(None) for _ in range(5)]
                    self.midiEventTracks = [[Song.Track(None) for _ in range(len(Song.difficulties))]]
                    self.tracks = [[Song.NoteTrack(None) for _ in range(len(Song.difficulties))]]
                def setBpm(self, bpm):
                    self.bpm = bpm

            harness = SongHarness()
            reader = ChartReader.ChartReader(harness)
            reader.read(chart_path)

            notes = harness.tracks[0][0].allEvents
            self.assertEqual(len(notes), 2)
            self.assertAlmostEqual(notes[0][0], sections[0][0], places=1)
            self.assertAlmostEqual(notes[1][0], sections[1][0], places=1)

    def test_cross_tap_notes_and_hopo_frequency(self):
        """TEST-T3-PAIR-06: Pair tap notes (N 6) with hopo_frequency in song.ini."""
        import Song
        import ChartReader

        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            ini_path = os.path.join(td, "song.ini")

            SongFixtureFactory.create_synthetic_chart(
                chart_path,
                tracks={
                    "ExpertSingle": [
                        (0, "N", 0, 0),
                        (96, "N", 6, 0),  # Tap note modifier
                        (96, "N", 1, 0),
                    ]
                },
            )
            SongFixtureFactory.create_synthetic_ini(
                ini_path,
                section_name="Song",
                metadata={"hopo_frequency": "170"},
            )

            # 1. Verify song.ini hopo_frequency mapping
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.hopofreq, 170)

            # 2. Parse chart with tap note
            class SongHarness:
                def __init__(self):
                    self.parts = [Song.parts[Song.GUITAR_PART]]
                    self.bpm = 120.0
                    self.hasStarpowerPaths = False
                    self.midiStyle = None
                    self.tempoEventTrack = Song.TempoTrack(None)
                    self.eventTracks = [Song.Track(None) for _ in range(5)]
                    self.midiEventTracks = [[Song.Track(None) for _ in range(len(Song.difficulties))]]
                    self.tracks = [[Song.NoteTrack(None) for _ in range(len(Song.difficulties))]]
                def setBpm(self, bpm):
                    self.bpm = bpm

            harness = SongHarness()
            reader = ChartReader.ChartReader(harness)
            reader.read(chart_path)

            notes = harness.tracks[0][0].allEvents
            self.assertEqual(len(notes), 2)
            self.assertEqual(notes[0][1].number, 0)
            self.assertEqual(notes[1][1].number, 1)

    def test_cross_song_loader_dual_format_precedence(self):
        """TEST-T3-PAIR-07: Verify dual-format folder (both notes.mid and notes.chart) precedence."""
        import Song

        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            midi_path = os.path.join(td, "notes.mid")
            ini_path = os.path.join(td, "song.ini")

            SongFixtureFactory.create_synthetic_chart(chart_path)
            SongFixtureFactory.create_synthetic_midi(midi_path)
            SongFixtureFactory.create_synthetic_ini(ini_path)

            # Branch 1: Both exist -> notes.mid takes precedence
            info_dual = Song.SongInfo(ini_path)
            self.assertTrue(info_dual.noteFileName.endswith("notes.mid"),
                            "Legacy MIDI notes.mid must take precedence when both formats are present")

            # Branch 2: notes.mid removed -> notes.chart selected as fallback
            os.remove(midi_path)
            info_chart_only = Song.SongInfo(ini_path)
            self.assertTrue(info_chart_only.noteFileName.endswith("notes.chart"),
                            "notes.chart must be selected when notes.mid is absent")

    def test_cross_headless_engine_audio_stem_routing(self):
        """TEST-T3-PAIR-08: Pair headless engine boot with dummy audio stem playback."""
        import Audio
        import pygame

        os.environ["SDL_AUDIODRIVER"] = "dummy"

        with tempfile.TemporaryDirectory() as td:
            stem_path = os.path.join(td, "song.ogg")
            SongFixtureFactory.create_dummy_ogg(stem_path)

            audio = Audio.Audio()
            audio.open(frequency=44100, bits=16, stereo=True, bufferSize=1024)

            ch1 = audio.getChannel(1)
            self.assertIsNotNone(ch1)

            sound = pygame.mixer.Sound(stem_path)
            ch1.play(sound)
            self.assertTrue(ch1.get_busy())

            ch1.stop()
            self.assertFalse(ch1.get_busy())
            audio.close()

    def test_cross_song_ini_overrides_chart_metadata(self):
        """TEST-T3-PAIR-09: Verify song.ini metadata takes precedence over .chart [Song] block."""
        import Song
        import ChartReader

        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "notes.chart")
            ini_path = os.path.join(td, "song.ini")

            SongFixtureFactory.create_synthetic_chart(
                chart_path,
                song_meta={"Name": "ChartTitle", "Artist": "ChartArtist"},
            )
            SongFixtureFactory.create_synthetic_ini(
                ini_path,
                section_name="Song",
                metadata={"name": "IniTitle", "artist": "IniArtist"},
            )

            # 1. Verify .chart [Song] block contains conflicting values
            with open(chart_path, "r", encoding="utf-8") as f:
                sections = ChartReader.ChartReader._parse_sections(f.read())
            self.assertEqual(sections["Song"]["Name"], "ChartTitle")
            self.assertEqual(sections["Song"]["Artist"], "ChartArtist")

            # 2. Verify SongInfo enforces song.ini precedence
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "IniTitle", "song.ini title must take precedence over chart title")
            self.assertEqual(info.artist, "IniArtist", "song.ini artist must take precedence over chart artist")

    def test_cross_unicode_metadata_album_art_headless(self):
        """TEST-T3-PAIR-10: Pair Unicode/CJK song metadata with album.png in headless mode."""
        import pygame
        from PIL import Image
        import Song

        with tempfile.TemporaryDirectory() as td:
            SongFixtureFactory.create_full_song_folder(
                td,
                format="chart",
                has_art=True,
                art_format="png",
                meta={
                    "name": "残光のファンタジア",
                    "artist": "東京事変",
                    "album": "音楽",
                },
            )
            ini_path = os.path.join(td, "song.ini")
            art_path = os.path.join(td, "album.png")

            # 1. Verify Unicode metadata resolution in SongInfo
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "残光のファンタジア")
            self.assertEqual(info.artist, "東京事変")
            self.assertEqual(info.album, "音楽")

            # 2. Verify album art with PIL
            with Image.open(art_path) as img:
                self.assertEqual(img.size, (64, 64))
                self.assertEqual(img.format, "PNG")

            # 3. Verify album art loadable as pygame surface
            pygame.init()
            surf = pygame.image.load(art_path)
            self.assertEqual(surf.get_size(), (64, 64))


if __name__ == "__main__":
    unittest.main()
