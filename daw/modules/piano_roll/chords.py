# modules/piano_roll/chords.py
"""
Acordes musicais para o Piano Roll.

Responsabilidade:
    Definir intervalos de acordes comuns e gerar as notas MIDI
    correspondentes a partir de uma nota raiz.
"""
from __future__ import annotations

from typing import List, Tuple

# (identificador, nome, descrição)
CHORD_ITEMS: Tuple[Tuple[str, str, str], ...] = (
    ("MAJOR", "Maior", "1-3-5"),
    ("MINOR", "Menor", "1-b3-5"),
    ("DIMINISHED", "Diminuto", "1-b3-b5"),
    ("AUGMENTED", "Aumentado", "1-3-#5"),
    ("MAJOR7", "Maior com 7ª", "1-3-5-7"),
    ("MINOR7", "Menor com 7ª", "1-b3-5-b7"),
    ("DOMINANT7", "Dominante 7ª", "1-3-5-b7"),
    ("SUS2", "Sus2", "1-2-5"),
    ("SUS4", "Sus4", "1-4-5"),
    ("MAJOR9", "Maior 9ª", "1-3-5-7-9"),
    ("MINOR9", "Menor 9ª", "1-b3-5-b7-9"),
    ("POWER", "Power Chord", "1-5"),
)

CHORD_INTERVALS: dict = {
    "MAJOR": [0, 4, 7],
    "MINOR": [0, 3, 7],
    "DIMINISHED": [0, 3, 6],
    "AUGMENTED": [0, 4, 8],
    "MAJOR7": [0, 4, 7, 11],
    "MINOR7": [0, 3, 7, 10],
    "DOMINANT7": [0, 4, 7, 10],
    "SUS2": [0, 2, 7],
    "SUS4": [0, 5, 7],
    "MAJOR9": [0, 4, 7, 11, 14],
    "MINOR9": [0, 3, 7, 10, 14],
    "POWER": [0, 7],
}


def get_chord_notes(root_pitch: int, chord_name: str) -> List[int]:
    """Retorna os pitches MIDI de um acorde a partir da raiz."""
    intervals = CHORD_INTERVALS.get(chord_name, CHORD_INTERVALS["MAJOR"])
    return [max(0, min(127, root_pitch + interval)) for interval in intervals]


def chord_name_for_display(chord_name: str) -> str:
    for identifier, label, _desc in CHORD_ITEMS:
        if identifier == chord_name:
            return label
    return chord_name.title()


def generate_chord_notes(root_pitch: int, chord_name: str, start_beat: float = 0.0,
                         duration_beats: float = 0.25, velocity: float = 0.8) -> List[dict]:
    """Gera notas prontas para inserção no piano roll."""
    pitches = get_chord_notes(root_pitch, chord_name)
    return [
        {
            "pitch": p,
            "start_beat": start_beat,
            "duration_beats": duration_beats,
            "velocity": velocity,
        }
        for p in pitches
    ]