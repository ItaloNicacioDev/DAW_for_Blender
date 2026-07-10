# modules/export/midi.py
"""
Exportador MIDI.

Responsabilidade:
    Gravar um arquivo Standard MIDI File (.mid, formato 0) real a partir
    das notas do Piano Roll, usando apenas a biblioteca padrão do Python
    (sem dependências externas como `mido`).

Referência do formato: Standard MIDI File 1.0 (formato 0, um único track).
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Iterable, List, Tuple, Union

from .wav import ExportNote

DEFAULT_PPQ = 480  # pulsos por semínima (resolução temporal do MIDI)


def _write_varlen(value: int) -> bytes:
    """Codifica um inteiro no formato 'variable length quantity' usado pelo SMF."""
    buffer = value & 0x7F
    out = bytearray()
    value >>= 7
    while value:
        buffer <<= 8
        buffer |= 0x80
        buffer |= value & 0x7F
        value >>= 7
    while True:
        out.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break
    return bytes(out)


def _tempo_meta_event(bpm: float) -> bytes:
    """Evento de meta-tempo (microssegundos por semínima)."""
    microseconds_per_beat = int(60_000_000 / max(1.0, bpm))
    data = microseconds_per_beat.to_bytes(3, "big")
    return b"\x00\xFF\x51\x03" + data


def _track_name_meta_event(name: str) -> bytes:
    name_bytes = name.encode("ascii", errors="replace")
    return b"\x00\xFF\x03" + _write_varlen(len(name_bytes)) + name_bytes


def _end_of_track_event() -> bytes:
    return b"\x00\xFF\x2F\x00"


def notes_to_midi_bytes(
    notes: Iterable[ExportNote],
    bpm: float,
    ppq: int = DEFAULT_PPQ,
    channel: int = 0,
    track_name: str = "DAW Export",
) -> bytes:
    """
    Converte uma lista de ExportNote (pitch/start/length em beats, velocity)
    em bytes de um arquivo .mid válido (formato 0, single track).
    """
    notes = list(notes)
    channel = max(0, min(15, channel))

    # Monta lista de eventos brutos: (tick_absoluto, tipo_ordem, bytes_evento_sem_delta)
    # tipo_ordem garante que "note off" no mesmo tick venha antes de "note on"
    events: List[Tuple[int, int, bytes]] = []

    for note in notes:
        start_tick = round(note.start * ppq)
        end_tick = round((note.start + max(note.length, 1e-6)) * ppq)
        velocity = max(1, min(127, note.velocity))
        pitch = max(0, min(127, note.pitch))

        note_on = bytes([0x90 | channel, pitch, velocity])
        note_off = bytes([0x80 | channel, pitch, 0])

        events.append((start_tick, 1, note_on))
        events.append((end_tick, 0, note_off))

    events.sort(key=lambda e: (e[0], e[1]))

    track_data = bytearray()
    track_data += _track_name_meta_event(track_name)
    track_data += _tempo_meta_event(bpm)

    last_tick = 0
    for tick, _, event_bytes in events:
        delta = max(0, tick - last_tick)
        track_data += _write_varlen(delta)
        track_data += event_bytes
        last_tick = tick

    track_data += _end_of_track_event()

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq)
    track_chunk = b"MTrk" + struct.pack(">I", len(track_data)) + bytes(track_data)

    return header + track_chunk


def export_notes_to_midi(
    notes: Iterable[ExportNote],
    bpm: float,
    filepath: Union[str, Path],
    ppq: int = DEFAULT_PPQ,
    channel: int = 0,
    track_name: str = "DAW Export",
) -> Path:
    """Atalho: converte as notas e grava direto em `filepath`. Retorna o Path final."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    data = notes_to_midi_bytes(notes, bpm, ppq=ppq, channel=channel, track_name=track_name)
    filepath.write_bytes(data)
    return filepath