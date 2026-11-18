# -*- coding: iso-8859-1 -*-
#
# ChartReader.py - Suporte ao formato .chart do Clone Hero no FoFiX
#
# Converte notes.chart para as mesmas estruturas internas que o MidiReader usa,
# permitindo que musicas do Clone Hero rodem no FoFiX sem conversao previa.

import copy
import os
import Log

# Mapeamento: nome da track no .chart -> (part_id, diff_id)
# Os IDs sao as constantes definidas em Song.py
CHART_TRACK_MAP = {
    'ExpertSingle':        (0, 0),   # GUITAR_PART, EXP_DIF
    'HardSingle':          (0, 1),   # GUITAR_PART, HAR_DIF
    'MediumSingle':        (0, 2),   # GUITAR_PART, MED_DIF
    'EasySingle':          (0, 3),   # GUITAR_PART, EAS_DIF
    'ExpertDoubleBass':    (2, 0),   # BASS_PART,   EXP_DIF
    'HardDoubleBass':      (2, 1),
    'MediumDoubleBass':    (2, 2),
    'EasyDoubleBass':      (2, 3),
    'ExpertDoubleRhythm':  (1, 0),   # RHYTHM_PART, EXP_DIF
    'HardDoubleRhythm':    (1, 1),
    'MediumDoubleRhythm':  (1, 2),
    'EasyDoubleRhythm':    (1, 3),
    'ExpertDrums':         (4, 0),   # DRUM_PART,   EXP_DIF
    'HardDrums':           (4, 1),
    'MediumDrums':         (4, 2),
    'EasyDrums':           (4, 3),
    'ExpertKeyboard':      (3, 0),   # LEAD_PART,   EXP_DIF
    'HardKeyboard':        (3, 1),
    'MediumKeyboard':      (3, 2),
    'EasyKeyboard':        (3, 3),
    # Aliases usados por algumas ferramentas de charting
    'ExpertGHLGuitar':     (0, 0),
    'HardGHLGuitar':       (0, 1),
    'MediumGHLGuitar':     (0, 2),
    'EasyGHLGuitar':       (0, 3),
}

STAR_POWER_NOTE = 103   # starPowerMarkingNote do Song.py

# Reverse mapping: (part_id, diff_id) -> human-readable names
_PART_ID_TO_NAME = {0: 'Guitar', 1: 'Rhythm', 2: 'Bass', 3: 'Keys', 4: 'Drums'}
_DIFF_ID_TO_NAME = {0: 'Expert', 1: 'Hard', 2: 'Medium', 3: 'Easy'}


def _build_ms_table(tempo_markers, resolution):
    """Pre-calcula o tempo em ms de cada marcador de BPM."""
    # Guard: resolution must be positive
    if resolution <= 0:
        resolution = 192
    markers = []
    for tick, bpm in tempo_markers:
        if bpm <= 0:
            bpm = 120.0
        markers.append((tick, bpm))
    markers.sort(key=lambda x: x[0])
    if not markers or markers[0][0] != 0:
        markers.insert(0, (0, 120.0))

    table = []  # lista de (tick, bpm, ms_at_tick)
    ms = 0.0
    prev_tick = 0
    prev_bpm = 120.0
    for tick, bpm in markers:
        ms += (tick - prev_tick) / float(resolution) * 60000.0 / prev_bpm
        table.append((tick, bpm, ms))
        prev_tick = tick
        prev_bpm = bpm
    return table, prev_tick, prev_bpm, ms


def _ticks_to_ms(tick, resolution, ms_table, last_tick, last_bpm, last_ms):
    """Converte tick absoluto para milissegundos usando a tabela pre-calculada."""
    # Guard: resolution must be positive
    if resolution <= 0:
        resolution = 192
    if not ms_table:
        return tick / float(resolution) * 60000.0 / 120.0
    # Encontra o marcador anterior ao tick
    base_tick, base_bpm, base_ms = ms_table[0][0], ms_table[0][1], ms_table[0][2]
    for t, bpm, ms in ms_table:
        if t > tick:
            break
        base_tick, base_bpm, base_ms = t, bpm, ms
    return base_ms + (tick - base_tick) / float(resolution) * 60000.0 / base_bpm


class ChartReader(object):
    """
    Le um arquivo .chart do Clone Hero e popula um objeto Song do FoFiX.
    Substitui o MidiReader quando o arquivo de notas e .chart.
    """

    def __init__(self, song):
        self.song = song

    def read(self, filename):
        # Tenta abrir como UTF-8 (com ou sem BOM); fallback para latin-1
        data = None
        for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
            try:
                with open(filename, 'rb') as fh:
                    raw = fh.read()
                data = raw.decode(enc, errors='replace')
                break
            except Exception as e:
                Log.warn("ChartReader: encoding %s falhou em %s: %s" % (enc, filename, e))

        if data is None:
            Log.error("ChartReader: nao foi possivel abrir %s" % filename)
            return

        sections = self._parse_sections(data)

        # --- [Song] ---
        resolution = 192
        song_meta = sections.get('Song', {})
        try:
            resolution = int(song_meta.get('Resolution', 192))
        except (ValueError, TypeError):
            pass
        if resolution <= 0:
            resolution = 192

        # --- [SyncTrack] ---
        tempo_markers = []  # [(tick, bpm)]
        for line in sections.get('SyncTrack', []):
            tick, tokens = self._split_event(line)
            if tick is None or not tokens:
                continue
            if tokens[0] == 'B' and len(tokens) >= 2:
                try:
                    bpm = int(tokens[1]) / 1000.0
                    # Guard: BPM must be positive
                    if bpm <= 0:
                        bpm = 120.0
                    tempo_markers.append((tick, bpm))
                except ValueError:
                    pass

        tempo_markers.sort(key=lambda x: x[0])

        # Garante BPM inicial
        if not tempo_markers or tempo_markers[0][0] != 0:
            tempo_markers.insert(0, (0, 120.0))

        # Pre-calcula tabela de ms por marcador
        ms_table, last_tick, last_bpm, last_ms = _build_ms_table(tempo_markers, resolution)

        def to_ms(tick):
            return _ticks_to_ms(tick, resolution, ms_table, last_tick, last_bpm, last_ms)

        # Define BPM inicial no song
        self.song.setBpm(tempo_markers[0][1])

        # Adiciona eventos de tempo na faixa de tempo do song
        from Song import Tempo as SongTempo
        for tick, bpm in tempo_markers:
            self.song.tempoEventTrack.addEvent(to_ms(tick), SongTempo(bpm))

        # --- [Events] (secoes) ---
        from Song import TextEvent, TK_SECTIONS
        for line in sections.get('Events', []):
            tick, tokens = self._split_event(line)
            if tick is None or not tokens or tokens[0] != 'E':
                continue
            text = ' '.join(tokens[1:]).strip().strip('"')
            if text.lower().startswith('section '):
                name = text[8:]
                self.song.eventTracks[TK_SECTIONS].addEvent(to_ms(tick), TextEvent(name, 0))

        # --- Tracks de notas ---
        from Song import Note as SongNote, MarkerNote, parts as song_parts, difficulties

        for section_name, lines in sections.items():
            if section_name not in CHART_TRACK_MAP:
                continue
            part_id, diff_id = CHART_TRACK_MAP[section_name]

            # Encontra o objeto Part correspondente
            target_part = None
            for p in song_parts.values():
                if p.id == part_id:
                    target_part = p
                    break
            if target_part is None or target_part not in self.song.parts:
                continue

            part_indices = [i for i, p in enumerate(self.song.parts) if p == target_part]
            if not part_indices:
                continue

            notes_at_tick = {}  # tick -> [(fret, sustain_ticks)]
            hopo_force = set()  # ticks com HOPO forcado (fret 5)
            star_power = []     # [(tick_start, tick_len)]

            for line in lines:
                tick, tokens = self._split_event(line)
                if tick is None or not tokens:
                    continue

                if tokens[0] == 'N' and len(tokens) >= 3:
                    try:
                        fret = int(tokens[1])
                        sustain = int(tokens[2])
                    except ValueError:
                        continue
                    if fret == 5:           # HOPO forcado
                        hopo_force.add(tick)
                    elif fret == 6:         # tap note (trata como normal)
                        pass
                    elif fret == 7:         # open note — sem suporte nativo no FoFiX, ignora
                        pass
                    elif 0 <= fret <= 4:
                        if tick not in notes_at_tick:
                            notes_at_tick[tick] = []
                        notes_at_tick[tick].append((fret, sustain))

                elif tokens[0] == 'S' and len(tokens) >= 3:
                    try:
                        sp_type = int(tokens[1])
                        sp_len = int(tokens[2])
                    except ValueError:
                        continue
                    if sp_type == 2:        # Star Power
                        star_power.append((tick, sp_len))

            # Adiciona star power
            for sp_tick, sp_len in star_power:
                sp_ms = to_ms(sp_tick)
                sp_end_ms = to_ms(sp_tick + sp_len)
                sp_dur = sp_end_ms - sp_ms
                for pi in part_indices:
                    midi_tracks = self.song.midiEventTracks[pi]
                    if diff_id < len(midi_tracks) and midi_tracks[diff_id] is not None:
                        midi_tracks[diff_id].addEvent(sp_ms, MarkerNote(STAR_POWER_NOTE, sp_dur))
                        midi_tracks[diff_id].addEvent(sp_end_ms + 1, MarkerNote(STAR_POWER_NOTE, 1, endMarker=True))
                self.song.hasStarpowerPaths = True

            # Adiciona notas
            for tick in sorted(notes_at_tick.keys()):
                time_ms = to_ms(tick)
                forced = tick in hopo_force
                for fret, sustain_ticks in notes_at_tick[tick]:
                    if sustain_ticks > 0:
                        length_ms = max(0.0, to_ms(tick + sustain_ticks) - time_ms)
                    else:
                        length_ms = 0.0
                    note_ev = SongNote(fret, length_ms, special=forced)
                    for pi in part_indices:
                        if diff_id < len(self.song.tracks[pi]):
                            self.song.tracks[pi][diff_id].addEvent(time_ms, copy.deepcopy(note_ev))

    @staticmethod
    def _split_event(line):
        """
        Divide 'tick = TYPE args...' em (tick_int, [TYPE, args...]).
        Retorna (None, None) se a linha nao e valida.
        """
        if '=' not in line:
            return None, None
        tick_str, _, rest = line.partition('=')
        try:
            tick = int(tick_str.strip())
        except ValueError:
            return None, None
        tokens = rest.strip().split()
        return tick, tokens

    @staticmethod
    def _parse_sections(data):
        """
        Faz o parse de um arquivo .chart em um dicionario de secoes.
        [Song] -> dict de chave/valor
        Outros -> lista de linhas brutas dentro das chaves
        """
        sections = {}
        current_section = None
        inside = False

        for raw in data.splitlines():
            line = raw.strip()
            if not line or line.startswith('//'):
                continue
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1].strip()
                inside = False
                continue
            if line == '{':
                inside = True
                if current_section == 'Song':
                    sections[current_section] = {}
                else:
                    sections.setdefault(current_section, [])
                continue
            if line == '}':
                inside = False
                current_section = None
                continue
            if not inside or current_section is None:
                continue
            if current_section == 'Song':
                if '=' in line:
                    k, _, v = line.partition('=')
                    sections['Song'][k.strip()] = v.strip().strip('"')
            else:
                sections[current_section].append(line)

        return sections


def get_parts_and_diffs(chart_path):
    """
    Scan a .chart file and return a dict mapping human-readable part names
    to lists of difficulty names present for that part.

    Example return: {'Guitar': ['Expert', 'Hard'], 'Drums': ['Expert']}
    """
    try:
        with open(chart_path, 'rb') as fh:
            raw = fh.read()
        data = raw.decode('utf-8-sig', errors='replace')
    except Exception:
        return {}

    sections = ChartReader._parse_sections(data)
    result = {}  # part_name -> set of diff_names

    for section_name in sections:
        if section_name in CHART_TRACK_MAP:
            part_id, diff_id = CHART_TRACK_MAP[section_name]
            part_name = _PART_ID_TO_NAME.get(part_id, 'Part%d' % part_id)
            diff_name = _DIFF_ID_TO_NAME.get(diff_id, 'Diff%d' % diff_id)
            if part_name not in result:
                result[part_name] = []
            if diff_name not in result[part_name]:
                result[part_name].append(diff_name)

    return result


def get_sections(chart_path):
    """
    Scan a .chart file and return a list of (timestamp_ms, section_name) tuples
    from the [Events] section, sorted by timestamp.
    """
    try:
        with open(chart_path, 'rb') as fh:
            raw = fh.read()
        data = raw.decode('utf-8-sig', errors='replace')
    except Exception:
        return []

    sections = ChartReader._parse_sections(data)

    # Get resolution
    resolution = 192
    song_meta = sections.get('Song', {})
    try:
        resolution = int(song_meta.get('Resolution', 192))
    except (ValueError, TypeError):
        pass
    if resolution <= 0:
        resolution = 192

    # Get tempo markers
    tempo_markers = []
    for line in sections.get('SyncTrack', []):
        tick, tokens = ChartReader._split_event(line)
        if tick is None or not tokens:
            continue
        if tokens[0] == 'B' and len(tokens) >= 2:
            try:
                bpm = int(tokens[1]) / 1000.0
                if bpm <= 0:
                    bpm = 120.0
                tempo_markers.append((tick, bpm))
            except ValueError:
                pass

    tempo_markers.sort(key=lambda x: x[0])
    if not tempo_markers or tempo_markers[0][0] != 0:
        tempo_markers.insert(0, (0, 120.0))

    ms_table, last_tick, last_bpm, last_ms = _build_ms_table(tempo_markers, resolution)

    # Extract sections from [Events]
    result = []
    for line in sections.get('Events', []):
        tick, tokens = ChartReader._split_event(line)
        if tick is None or not tokens or tokens[0] != 'E':
            continue
        text = ' '.join(tokens[1:]).strip().strip('"')
        if text.lower().startswith('section '):
            name = text[8:]
            ms = _ticks_to_ms(tick, resolution, ms_table, last_tick, last_bpm, last_ms)
            result.append((ms, name))

    result.sort(key=lambda x: x[0])
    return result
