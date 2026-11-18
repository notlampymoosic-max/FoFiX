# -*- coding: utf-8 -*-
"""
fixtures.py - Reusable Synthetic Fixture Generators for FoFiX Modernization E2E Tests

Provides:
  - SongFixtureFactory:
      - create_synthetic_chart: generates valid .chart files with sections, notes, Star Power.
      - create_synthetic_ini: generates song.ini with case-insensitive sections, aliases, diffs.
      - create_dummy_ogg: generates minimal valid Ogg Vorbis audio stem files.
      - create_dummy_image: generates valid PNG/JPEG album art via Pillow.
      - create_synthetic_midi: generates valid Standard MIDI (SMF Type 1) binary files.
      - create_full_song_folder: creates complete ready-to-load song directories.
"""

import io
import os
import shutil
import struct
import warnings
from PIL import Image

def _install_safe_warning_interceptor():
    orig_showwarning = warnings.showwarning
    def safe_showwarning(message, category, filename, lineno, file=None, line=None):
        try:
            orig_showwarning(message, category, filename, lineno, file, line)
        except TypeError:
            try:
                formatted = warnings.formatwarning(message, category, filename, lineno, line)
                import sys
                sys.stderr.write(f"Safe Warning: {formatted}\n")
            except Exception:
                pass
    warnings.showwarning = safe_showwarning

_install_safe_warning_interceptor()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SAMPLE_OGG = os.path.join(DATA_DIR, "sounds", "drumscw1.ogg")
STEM_SAMPLE_MAP = {
    "song": os.path.join(DATA_DIR, "sounds", "100pct1.ogg"),
    "guitar": os.path.join(DATA_DIR, "sounds", "100pct2.ogg"),
    "bass": os.path.join(DATA_DIR, "sounds", "100pct3.ogg"),
    "rhythm": os.path.join(DATA_DIR, "sounds", "99pct2.ogg"),
    "drums": os.path.join(DATA_DIR, "sounds", "drumscw1.ogg"),
    "vocals": os.path.join(DATA_DIR, "sounds", "bassscw1.ogg"),
    "crowd": os.path.join(DATA_DIR, "sounds", "bassscw2.ogg"),
}


def encode_vlq(value: int) -> bytes:
    """Encode an integer into MIDI variable-length quantity (VLQ) bytes."""
    buf = bytearray()
    buf.append(value & 0x7F)
    value >>= 7
    while value > 0:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(buf))


def decode_vlq(data: bytes, offset: int = 0) -> tuple[int, int]:
    """
    Decode a MIDI variable-length quantity from bytes.
    Returns (value, bytes_consumed).
    """
    value = 0
    bytes_consumed = 0
    while True:
        if offset + bytes_consumed >= len(data):
            raise ValueError("Unexpected EOF while decoding VLQ")
        b = data[offset + bytes_consumed]
        bytes_consumed += 1
        value = (value << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return value, bytes_consumed


class SongFixtureFactory:
    """Factory generating synthetic test songs, chart files, metadata, and assets."""

    @staticmethod
    def create_synthetic_chart(
        filepath: str,
        song_meta: dict = None,
        sync_track: list = None,
        sections: list = None,
        lyrics: list = None,
        tracks: dict = None,
    ) -> str:
        """
        Creates a valid Clone Hero .chart plaintext file.
        :param filepath: Output path.
        :param song_meta: dict of [Song] properties (Name, Artist, Charter, Resolution, etc.)
        :param sync_track: list of (tick, type, *args), e.g. [(0, 'TS', 4), (0, 'B', 120000)]
        :param sections: list of (tick, section_name), e.g. [(0, 'Intro'), (768, 'Verse 1')]
        :param lyrics: list of (tick, text), e.g. [(0, 'la'), (192, 'la')]
        :param tracks: dict of track_name -> list of events, e.g.
                       'ExpertSingle': [(0, 'N', 0, 0), (192, 'N', 1, 96), (384, 'S', 2, 384)]
        """
        if song_meta is None:
            song_meta = {
                "Name": "Synthetic Test Song",
                "Artist": "Fixture Band",
                "Charter": "TestWriter",
                "Resolution": 192,
                "Offset": 0,
            }
        if sync_track is None:
            sync_track = [
                (0, "TS", 4),
                (0, "B", 120000),
            ]
        if tracks is None:
            tracks = {
                "ExpertSingle": [
                    (0, "N", 0, 0),
                    (192, "N", 1, 96),
                    (384, "N", 2, 0),
                    (576, "S", 2, 384),
                    (576, "N", 3, 0),
                    (768, "N", 4, 192),
                    (960, "S", 2, 384),
                    (960, "N", 0, 0),
                ]
            }

        lines = ["[Song]", "{"]
        for k, v in song_meta.items():
            if isinstance(v, (int, float)):
                lines.append(f"  {k} = {v}")
            else:
                lines.append(f'  {k} = "{v}"')
        lines.append("}")

        lines.extend(["[SyncTrack]", "{"])
        for ev in sync_track:
            tick, ev_type = ev[0], ev[1]
            args = " ".join(str(a) for a in ev[2:])
            lines.append(f"  {tick} = {ev_type} {args}")
        lines.append("}")

        if sections or lyrics:
            lines.extend(["[Events]", "{"])
            if sections:
                for tick, sec_name in sections:
                    lines.append(f'  {tick} = E "section {sec_name}"')
            if lyrics:
                for tick, lyric_text in lyrics:
                    lines.append(f'  {tick} = E "lyric {lyric_text}"')
            lines.append("}")

        for track_name, events in tracks.items():
            lines.extend([f"[{track_name}]", "{"])
            for ev in events:
                tick, ev_type = ev[0], ev[1]
                args = " ".join(str(a) for a in ev[2:])
                lines.append(f"  {tick} = {ev_type} {args}")
            lines.append("}")

        content = "\n".join(lines) + "\n"
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    @staticmethod
    def create_synthetic_ini(
        filepath: str,
        section_name: str = "song",
        metadata: dict = None,
    ) -> str:
        """
        Creates a valid song.ini configuration file.
        :param filepath: Output path.
        :param section_name: 'song', 'Song', 'foofix', etc.
        :param metadata: key-value dictionary of metadata properties.
        """
        if metadata is None:
            metadata = {
                "name": "Synthetic Test Song",
                "artist": "Fixture Band",
                "album": "Fixture Album",
                "year": "2026",
                "genre": "Rock",
                "charter": "TestWriter",
                "hopo_frequency": "170",
                "diff_guitar": "5",
                "diff_bass": "4",
                "diff_drums": "5",
                "diff_vocals": "3",
                "diff_band": "5",
            }

        lines = [f"[{section_name}]"]
        for k, v in metadata.items():
            lines.append(f"{k} = {v}")

        content = "\n".join(lines) + "\n"
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    @staticmethod
    def create_dummy_ogg(filepath: str, duration_sec: int = 1) -> str:
        """
        Generates a valid minimal playable audio stem file.
        Copies from the pristine sample in data/sounds/ if available,
        or generates a valid standard PCM WAV/audio stream that pygame.mixer cleanly decodes.
        """
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        base = os.path.basename(filepath).split('.')[0].lower()
        sample = STEM_SAMPLE_MAP.get(base, SAMPLE_OGG)
        if not os.path.isfile(sample):
            sample = SAMPLE_OGG
        if os.path.isfile(sample):
            shutil.copyfile(sample, filepath)
        else:
            # Hermetic fallback: 44-byte RIFF WAVE header + 100 bytes silence = 144 bytes
            # Decoded cleanly by pygame.mixer.Sound regardless of .ogg file extension.
            num_samples = 100
            sample_rate = 44100
            byte_rate = sample_rate * 2
            data_size = num_samples * 2
            header = struct.pack(
                "<4sI4s4sIHHIIHH4sI",
                b"RIFF",
                36 + data_size,
                b"WAVE",
                b"fmt ",
                16,             # PCM chunk size
                1,              # Format: PCM
                1,              # Channels: Mono
                sample_rate,    # 44100 Hz
                byte_rate,      # Bytes per second
                2,              # Block align
                16,             # Bits per sample
                b"data",
                data_size,
            )
            with open(filepath, "wb") as f:
                f.write(header + (b"\x00" * data_size))
        return filepath

    @staticmethod
    def create_dummy_image(
        filepath: str,
        format: str = "PNG",
        size: tuple = (64, 64),
        color: tuple = (200, 50, 50),
    ) -> str:
        """
        Generates dummy album art image in PNG or JPEG format using Pillow.
        """
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        img = Image.new("RGB", size, color)
        fmt = "JPEG" if format.upper() in ("JPG", "JPEG") else "PNG"
        img.save(filepath, format=fmt)
        return filepath

    @staticmethod
    def create_synthetic_midi(
        filepath: str,
        division: int = 480,
        track_name: str = "PART GUITAR",
        tempo_bpm: float = 120.0,
        notes: list = None,
        star_power: list = None,
    ) -> str:
        """
        Builds a valid Type 1 Standard MIDI File (SMF).
        :param division: Ticks per quarter note (default 480).
        :param track_name: Instrument track sequence name.
        :param tempo_bpm: BPM (default 120).
        :param notes: list of (tick, duration, pitch, velocity)
        :param star_power: list of (tick, duration) for pitch 103
        """
        if notes is None:
            # Note 96 = Expert Green
            notes = [(0, 240, 96, 100), (240, 240, 97, 100)]
        if star_power is None:
            # Note 103 = Star Power
            star_power = [(0, 480), (720, 480)]

        out = io.BytesIO()
        # MThd: format 1, 2 tracks, division
        out.write(b"MThd\x00\x00\x00\x06\x00\x01\x00\x02" + struct.pack(">H", division))

        # Track 1: Tempo map
        trk1 = io.BytesIO()
        # Calculate microseconds per quarter note
        tempo_us = int(60_000_000 / tempo_bpm)
        b1 = (tempo_us >> 16) & 0xFF
        b2 = (tempo_us >> 8) & 0xFF
        b3 = tempo_us & 0xFF
        trk1.write(encode_vlq(0) + b"\xff\x51\x03" + bytes([b1, b2, b3]))
        trk1.write(encode_vlq(0) + b"\xff\x2f\x00")
        t1_bytes = trk1.getvalue()
        out.write(b"MTrk" + struct.pack(">I", len(t1_bytes)) + t1_bytes)

        # Track 2: Note and Marker events
        trk2 = io.BytesIO()
        name_bytes = track_name.encode("iso-8859-1")
        trk2.write(encode_vlq(0) + b"\xff\x03" + struct.pack("B", len(name_bytes)) + name_bytes)

        # Collect and sort all events by tick
        events = []
        for tick, dur, pitch, vel in notes:
            events.append((tick, 0x90, pitch, vel))       # Note On
            events.append((tick + dur, 0x80, pitch, 0))   # Note Off

        for tick, dur in star_power:
            events.append((tick, 0x90, 103, 100))         # SP On
            events.append((tick + dur, 0x80, 103, 0))     # SP Off

        # Sort chronologically, Note Off before Note On at same tick
        events.sort(key=lambda ev: (ev[0], 0 if ev[1] == 0x80 else 1))

        current_tick = 0
        for ev_tick, status, pitch, vel in events:
            delta = ev_tick - current_tick
            trk2.write(encode_vlq(delta) + bytes([status, pitch, vel]))
            current_tick = ev_tick

        trk2.write(encode_vlq(0) + b"\xff\x2f\x00")
        t2_bytes = trk2.getvalue()
        out.write(b"MTrk" + struct.pack(">I", len(t2_bytes)) + t2_bytes)

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(out.getvalue())
        return filepath

    @staticmethod
    def create_full_song_folder(
        target_dir: str,
        format: str = "chart",
        has_stems: bool = True,
        has_art: bool = True,
        art_format: str = "jpg",
        ini_section: str = "Song",
        meta: dict = None,
        stems: list = None,
    ) -> str:
        """
        Creates a complete song folder inside target_dir.
        :param target_dir: Song folder path.
        :param format: 'chart' or 'mid'.
        :param has_stems: whether to generate audio stem files.
        :param has_art: whether to generate album art.
        :param art_format: 'jpg' or 'png'.
        :param ini_section: 'Song', 'song', etc.
        :param meta: custom song.ini metadata dict.
        :param stems: list of stem basenames, e.g. ['song.ogg', 'guitar.ogg', 'bass.ogg', 'drums.ogg']
        """
        os.makedirs(target_dir, exist_ok=True)

        # 1. Notes file
        if format == "chart":
            SongFixtureFactory.create_synthetic_chart(
                os.path.join(target_dir, "notes.chart")
            )
        else:
            SongFixtureFactory.create_synthetic_midi(
                os.path.join(target_dir, "notes.mid")
            )

        # 2. Metadata file
        SongFixtureFactory.create_synthetic_ini(
            os.path.join(target_dir, "song.ini"),
            section_name=ini_section,
            metadata=meta,
        )

        # 3. Audio stems
        if has_stems:
            if stems is None:
                stems = ["song.ogg", "guitar.ogg"]
            for stem_name in stems:
                SongFixtureFactory.create_dummy_ogg(os.path.join(target_dir, stem_name))

        # 4. Album art
        if has_art:
            art_ext = art_format.lower()
            art_filename = f"album.{art_ext}"
            SongFixtureFactory.create_dummy_image(
                os.path.join(target_dir, art_filename),
                format=art_format,
            )

        return target_dir



class MockChartTrack:
    """Lightweight track mock for ChartReader event accumulation."""
    def __init__(self):
        self.allEvents = []

    def addEvent(self, time, event):
        self.allEvents.append((time, event))


class MockChartSong:
    """Lightweight Song mock satisfying ChartReader.read() contracts."""
    def __init__(self):
        import sys, types
        # Support isolated execution if peer modules (Audio.py) are in transit
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
