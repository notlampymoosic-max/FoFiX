# -*- coding: utf-8 -*-
"""
test_tier4_real_world_scenarios.py - FoFiX Modernization E2E Test Suite (Tier 4)

Covers 5 realistic end-to-end application scenarios:
  1. Clone Hero Standard Library Song (TEST-T4-SCEN-01)
  2. Dual-Format Library Scanning (TEST-T4-SCEN-02)
  3. High-Density Chart with Dynamic Tempo Changes & Star Power (TEST-T4-SCEN-03)
  4. Complete Headless Game Engine Boot, Scene Transition & Teardown (TEST-T4-SCEN-04)
  5. Custom Song with Complete Stems & Extended song.ini Metadata (TEST-T4-SCEN-05)
"""

import os
import sys
import tempfile
import unittest
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tests.fixtures import SongFixtureFactory
from tests.test_tier1_feature_coverage import MockEngine


class TestRealWorldScenarios(unittest.TestCase):
    """Tier 4: Real-World E2E Application Scenarios."""

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

    def test_scenario1_clone_hero_standard_library_song(self):
        """TEST-T4-SCEN-01: Scenario 1 - Clone Hero Standard Library Song."""
        import pygame
        import Song
        import ChartReader

        with tempfile.TemporaryDirectory() as td:
            song_dir = os.path.join(td, "ThroughTheFire")
            SongFixtureFactory.create_full_song_folder(
                song_dir,
                format="chart",
                has_stems=True,
                stems=["song.ogg", "guitar.ogg"],
                has_art=True,
                art_format="jpg",
                ini_section="Song",
                meta={
                    "name": "Through The Fire",
                    "artist": "DragonForce",
                    "album": "Inhuman Rampage",
                    "year": "2006",
                    "charter": "CloneHeroCharter",
                    "diff_guitar": "6",
                    "diff_band": "6",
                },
            )

            # 1. Verify filesystem layout
            chart_path = os.path.join(song_dir, "notes.chart")
            ini_path = os.path.join(song_dir, "song.ini")
            art_path = os.path.join(song_dir, "album.jpg")
            self.assertTrue(os.path.isfile(chart_path))
            self.assertTrue(os.path.isfile(ini_path))
            self.assertTrue(os.path.isfile(art_path))

            # 2. Verify album art with Pillow
            with Image.open(art_path) as img:
                self.assertEqual(img.format, "JPEG")
                self.assertEqual(img.size, (64, 64))
                self.assertEqual(img.mode, "RGB")

            # 3. Verify audio stems via pygame mixer
            pygame.mixer.init()
            s_backing = pygame.mixer.Sound(os.path.join(song_dir, "song.ogg"))
            s_guitar = pygame.mixer.Sound(os.path.join(song_dir, "guitar.ogg"))
            self.assertGreater(s_backing.get_length(), 0.0)
            self.assertGreater(s_guitar.get_length(), 0.0)

            # 4. Genuine SongInfo parsing without error evasion
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "Through The Fire")
            self.assertEqual(info.artist, "DragonForce")
            self.assertEqual(info.album, "Inhuman Rampage")
            self.assertEqual(info.year, "2006")
            self.assertEqual(info.frets, "CloneHeroCharter")
            self.assertEqual(info.diffGuitar, 6)
            self.assertEqual(info.diffSong, 6)
            self.assertEqual(info.noteFileName, chart_path)

            # 5. Genuine ChartReader parsing
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
            self.assertTrue(harness.hasStarpowerPaths)
            self.assertGreater(len(harness.tracks[0][0].allEvents), 0)

    def test_scenario2_dual_format_library_scanning(self):
        """TEST-T4-SCEN-02: Scenario 2 - Dual-Format Library Scanning via Song Subsystems."""
        import Song

        with tempfile.TemporaryDirectory() as lib_dir:
            # Song 1: Legacy MIDI
            SongFixtureFactory.create_full_song_folder(
                os.path.join(lib_dir, "LegacyMidSong"),
                format="mid",
                ini_section="song",
                meta={"name": "Legacy Mid Song"},
            )
            # Song 2: Modern Clone Hero .chart
            SongFixtureFactory.create_full_song_folder(
                os.path.join(lib_dir, "ModernChartSong"),
                format="chart",
                ini_section="Song",
                meta={"name": "Modern Chart Song"},
            )
            # Song 3: Dual format
            dual_dir = os.path.join(lib_dir, "DualSong")
            SongFixtureFactory.create_full_song_folder(
                dual_dir,
                format="chart",
                ini_section="Song",
                meta={"name": "Dual Song"},
            )
            SongFixtureFactory.create_synthetic_midi(os.path.join(dual_dir, "notes.mid"))

            # 1. Genuine LibraryInfo song counting
            lib_ini = os.path.join(lib_dir, "library.ini")
            with open(lib_ini, "w") as f:
                f.write("[library]\nname = TestDualLib\n")

            lib_info = Song.LibraryInfo("TestDualLib", lib_ini)
            self.assertEqual(lib_info.name, "TestDualLib")
            self.assertEqual(lib_info.songCount, 3, "LibraryInfo must count MIDI, Chart, and Dual songs")

            # 2. Genuine Song.getAvailableSongs() execution
            class LibraryScanEngine:
                class MockConfig:
                    def get(self, sec, key):
                        cfg = {
                            ("game", "sort_order"): 0,
                            ("game", "tut"): 0,
                            ("game", "sort_direction"): 0,
                            ("game", "game_mode"): 1,
                            ("game", "songlist_instrument"): 0,
                            ("game", "log_class_inits"): 0,
                            ("game", "log_sections"): 0,
                            ("debug", "use_unedited_midis"): 0,
                            ("log", "log_unedited_midis"): 0,
                            ("performance", "cache_song_metadata"): False,
                        }
                        return cfg.get((sec, key), 0)

                class MockResource:
                    def __init__(self, root):
                        self.root = root
                    def fileName(self, *parts, **kwargs):
                        return os.path.join(self.root, *parts)

                def __init__(self, root):
                    self.config = self.MockConfig()
                    self.resource = self.MockResource(root)

            scan_engine = LibraryScanEngine(lib_dir)
            songs = Song.getAvailableSongs(scan_engine, lib_dir)
            self.assertEqual(len(songs), 3, "getAvailableSongs must discover all 3 songs in library")

            song_names = {s.name for s in songs}
            self.assertEqual(song_names, {"Legacy Mid Song", "Modern Chart Song", "Dual Song"})

            song_by_name = {s.name: s for s in songs}
            self.assertTrue(song_by_name["Legacy Mid Song"].noteFileName.endswith("notes.mid"))
            self.assertTrue(song_by_name["Modern Chart Song"].noteFileName.endswith("notes.chart"))
            self.assertTrue(song_by_name["Dual Song"].noteFileName.endswith("notes.mid"),
                            "Dual-format song must prioritize notes.mid per FoFiX precedence rules")

    def test_scenario3_high_density_chart_parsing(self):
        """TEST-T4-SCEN-03: Scenario 3 - High-Density Chart with Dynamic Tempo Changes & Star Power."""
        import Song
        import ChartReader

        with tempfile.TemporaryDirectory() as td:
            chart_path = os.path.join(td, "high_density.chart")

            # 10 dynamic tempo changes
            sync_track = [(0, "TS", 4)]
            bpms = [120, 130, 140, 150, 160, 150, 140, 130, 120, 110]
            for i, bpm in enumerate(bpms):
                sync_track.append((i * 192, "B", bpm * 1000))

            # 6 practice sections
            sections = [
                (0, "Intro"),
                (192 * 2, "Verse 1"),
                (192 * 4, "Pre-Chorus"),
                (192 * 6, "Chorus 1"),
                (192 * 8, "Guitar Solo"),
                (192 * 10, "Outro"),
            ]

            # 300+ note events including chords
            notes = []
            for tick in range(0, 3000, 10):
                fret = (tick // 10) % 5
                notes.append((tick, "N", fret, 0))
                if tick % 50 == 0:
                    notes.append((tick, "N", (fret + 1) % 5, 0))

            # 4 Star Power phrases
            sp_events = [
                (192 * 1, "S", 2, 192),
                (192 * 3, "S", 2, 192),
                (192 * 5, "S", 2, 192),
                (192 * 7, "S", 2, 192),
            ]
            all_track_events = sorted(notes + sp_events, key=lambda ev: ev[0])

            SongFixtureFactory.create_synthetic_chart(
                chart_path,
                sync_track=sync_track,
                sections=sections,
                tracks={"ExpertSingle": all_track_events},
            )

            # Genuine ChartReader execution
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

            # 1. Verify Note Counts
            expert_notes = harness.tracks[0][0].allEvents
            self.assertGreater(len(expert_notes), 300, "High-density chart must produce >300 note events")

            # 2. Verify Chord Synchronization (identical timestamp, distinct note numbers)
            timestamp_map = {}
            for t_ms, note_ev in expert_notes:
                timestamp_map.setdefault(round(t_ms, 2), []).append(note_ev.number)
            chords = [frets for t, frets in timestamp_map.items() if len(frets) > 1]
            self.assertGreater(len(chords), 10, "High-density chart must have synchronized chord notes")
            for frets in chords:
                self.assertEqual(len(frets), len(set(frets)), "Chord notes at same timestamp must have distinct frets")

            # 3. Verify Star Power Marker Events (pitch 103, 4 phrases = 8 events)
            sp_events_parsed = [ev for t, ev in harness.midiEventTracks[0][0].allEvents
                                if getattr(ev, 'number', None) == ChartReader.STAR_POWER_NOTE]
            self.assertEqual(len(sp_events_parsed), 8, "Expected 4 start and 4 end Star Power markers")
            self.assertTrue(harness.hasStarpowerPaths)

            # 4. Verify Tempo Events
            self.assertEqual(len(harness.tempoEventTrack.allEvents), 10, "Expected 10 tempo changes")

            # 5. Verify Section Markers
            section_events = harness.eventTracks[Song.TK_SECTIONS].allEvents
            self.assertEqual(len(section_events), 6, "Expected 6 practice sections")
            self.assertEqual(section_events[0][0], 0.0)
            self.assertEqual(section_events[0][1].text, "Intro")
            for i in range(len(section_events) - 1):
                self.assertLess(section_events[i][0], section_events[i+1][0],
                                "Section timestamps must be strictly monotonic")

    def test_scenario4_headless_engine_boot_scene_transition_teardown(self):
        """TEST-T4-SCEN-04: Scenario 4 - Complete Headless Game Engine Boot, Scene Transition & Teardown."""
        import pygame
        import Config
        import GameEngine
        from View import Layer

        # 1. Boot GameEngine in Headless Mode
        config = Config.load(setAsDefault=True)
        engine = GameEngine.GameEngine(config)

        # 2. Verify Subsystem Initialization
        self.assertIsNotNone(engine.video, "Video subsystem must be initialized")
        self.assertIsNotNone(engine.view, "View task must be initialized")
        self.assertIsNotNone(engine.audio, "Audio subsystem must be initialized")
        self.assertIsNotNone(engine.svg, "SvgContext must be initialized")
        self.assertIsNotNone(engine.input, "Input subsystem must be initialized")

        # 3. Test Scene Transitions via View Layer Stack
        class InstrumentedScene(Layer):
            def __init__(self, name):
                super().__init__()
                self.name = name
                self.shown_called = False
                self.hidden_called = False
                self.render_calls = 0
            def shown(self):
                self.shown_called = True
            def hidden(self):
                self.hidden_called = True
            def render(self, visibility, topMost):
                self.render_calls += 1

        scene_a = InstrumentedScene("SceneA")
        scene_b = InstrumentedScene("SceneB")

        # Push Scene A
        engine.view.pushLayer(scene_a)
        self.assertTrue(scene_a.shown_called, "Scene shown() must be called on push")
        self.assertEqual(engine.view.topLayer(), scene_a)
        self.assertEqual(len(engine.view.layers), 1)

        # Step 3 engine ticks
        for _ in range(3):
            engine.run()
        self.assertGreater(scene_a.render_calls, 0, "Active scene must receive render calls")

        # Push Scene B (Scene transition)
        engine.view.pushLayer(scene_b)
        self.assertTrue(scene_b.shown_called)
        self.assertEqual(engine.view.topLayer(), scene_b)
        self.assertEqual(len(engine.view.layers), 2)

        for _ in range(3):
            engine.run()
        self.assertGreater(scene_b.render_calls, 0)

        # Pop Scene B (Transition back to Scene A)
        engine.view.popLayer(scene_b)
        self.assertIn(scene_b, engine.view.outgoing)
        self.assertEqual(engine.view.topLayer(), scene_a)

        # Step transition completion
        engine.view.run(1000)
        self.assertNotIn(scene_b, engine.view.layers)
        self.assertTrue(scene_b.hidden_called, "Popped scene hidden() must be called")

        # 4. Clean Teardown
        engine.quit()
        self.assertFalse(pygame.display.get_init(), "Display must be shut down cleanly")

    def test_scenario5_custom_song_complete_stems_extended_ini(self):
        """TEST-T4-SCEN-05: Scenario 5 - Custom Song with Complete Stems & Extended song.ini Metadata."""
        import pygame
        import Song

        with tempfile.TemporaryDirectory() as td:
            song_dir = os.path.join(td, "Masterpiece")
            SongFixtureFactory.create_full_song_folder(
                song_dir,
                format="chart",
                has_stems=True,
                stems=[
                    "song.ogg",
                    "guitar.ogg",
                    "bass.ogg",
                    "drums.ogg",
                    "vocals.ogg",
                ],
                has_art=True,
                art_format="jpg",
                ini_section="Song",
                meta={
                    "name": "Masterpiece",
                    "artist": "Virtuoso Band",
                    "album": "The Magnum Opus",
                    "year": "2026",
                    "genre": "Progressive Metal",
                    "charter": "ExpertCharter",
                    "diff_band": "5",
                    "diff_guitar": "5",
                    "diff_bass": "4",
                    "diff_drums": "5",
                    "diff_vocals": "3",
                    "song_length": "240000",
                    "preview_start_time": "60000",
                    "preview_end_time": "90000",
                },
            )

            # 1. Verify Audio Stems Decoding Integrity
            pygame.mixer.init()
            stem_names = ["song.ogg", "guitar.ogg", "bass.ogg", "drums.ogg", "vocals.ogg"]
            for stem in stem_names:
                p = os.path.join(song_dir, stem)
                self.assertTrue(os.path.isfile(p))
                snd = pygame.mixer.Sound(p)
                self.assertGreater(snd.get_length(), 0.0, f"Stem {stem} must decode to valid audio")

            # 2. Verify Album Art Image
            art_path = os.path.join(song_dir, "album.jpg")
            with Image.open(art_path) as img:
                self.assertEqual(img.format, "JPEG")
                self.assertEqual(img.mode, "RGB")

            # 3. Genuine SongInfo Extended Metadata Verification
            ini_path = os.path.join(song_dir, "song.ini")
            info = Song.SongInfo(ini_path)
            self.assertEqual(info.name, "Masterpiece")
            self.assertEqual(info.artist, "Virtuoso Band")
            self.assertEqual(info.album, "The Magnum Opus")
            self.assertEqual(info.year, "2026")
            self.assertEqual(info.genre, "Progressive Metal")
            self.assertEqual(info.frets, "ExpertCharter")
            self.assertEqual(info.diffSong, 5)
            self.assertEqual(info.diffGuitar, 5)
            self.assertEqual(info.diffBass, 4)
            self.assertEqual(info.diffDrums, 5)
            self.assertEqual(info.diffVocals, 3)

            # 4. Verify Stem-to-Channel Mapping (bass.ogg -> rhythm stem resolution)
            rhythm_stem = None
            for _bass_stem in ("bass", "rhythm"):
                cand = os.path.join(song_dir, _bass_stem + ".ogg")
                if os.path.isfile(cand):
                    rhythm_stem = cand
                    break
            self.assertEqual(rhythm_stem, os.path.join(song_dir, "bass.ogg"),
                             "Clone Hero bass.ogg must be resolved as the rhythm channel stem")

            # 5. Genuine Song.loadSong verifying all stems bound to tracks
            song = Song.loadSong(MockEngine(), "Masterpiece", library=td)
            self.assertIsNotNone(song.music, "Backing music stem must be loaded")
            self.assertIsNotNone(song.guitarTrack, "Guitar stem must be loaded")
            self.assertEqual(song.guitarTrack.channel.id, 1, "guitarTrack must bind to channel 1")
            self.assertIsNotNone(song.rhythmTrack, "Bass stem must route to rhythm channel 2")
            self.assertEqual(song.rhythmTrack.channel.id, 2, "rhythmTrack must bind to channel 2")
            self.assertIsNotNone(song.drumTrack, "Drums stem must be loaded to channel 3")
            self.assertEqual(song.drumTrack.channel.id, 3, "drumTrack must bind to channel 3")


if __name__ == "__main__":
    unittest.main()
