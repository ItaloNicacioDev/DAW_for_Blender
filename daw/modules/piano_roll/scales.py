# modules/piano_roll/scales.py
"""
Escalas musicais para o Piano Roll.

Responsabilidade:
    Fornecer intervalos de semitons para escalas comuns,
    verificar se uma nota pertence a uma escala, e sugerir
    notas "in-scale" próximas.
"""
from __future__ import annotations

from typing import List, Tuple

# (identificador, nome, descrição)
SCALE_ITEMS: Tuple[Tuple[str, str, str], ...] = (
    ("CHROMATIC", "Cromática", "Todas as 12 notas"),
    ("MAJOR", "Maior", "Tom-Tom-Semitom-Tom-Tom-Tom-Semitom"),
    ("MINOR", "Menor Natural", "Tom-Semitom-Tom-Tom-Semitom-Tom-Tom"),
    ("MINOR_HARMONIC", "Menor Harmônica", "Tom-Semitom-Tom-Tom-Semitom-1.5Tom-Semitom"),
    ("MINOR_MELODIC", "Menor Melódica", "Tom-Semitom-Tom-Tom-Tom-Tom-Semitom (asc)"),
    ("DORIAN", "Dórico", "Tom-Semitom-Tom-Tom-Tom-Semitom-Tom"),
    ("PHRYGIAN", "Frígio", "Semitom-Tom-Tom-Tom-Semitom-Tom-Tom"),
    ("LYDIAN", "Lídio", "Tom-Tom-Tom-Semitom-Tom-Tom-Semitom"),
    ("MIXOLYDIAN", "Mixolídio", "Tom-Tom-Semitom-Tom-Tom-Semitom-Tom"),
    ("LOCRIAN", "Lócrio", "Semitom-Tom-Tom-Semitom-Tom-Tom-Tom"),
    ("PENTATONIC_MAJOR", "Pentatônica Maior", "Tom-Tom-1.5Tom-Tom-1.5Tom"),
    ("PENTATONIC_MINOR", "Pentatônica Menor", "1.5Tom-Tom-Tom-1.5Tom-Tom"),
    ("BLUES", "Blues", "1.5Tom-Tom-Semitom-Semitom-1.5Tom-Tom"),
)

# Intervalos em semitons a partir da tônica
SCALE_INTERVALS: dict = {
    "CHROMATIC": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "MAJOR": [0, 2, 4, 5, 7, 9, 11],
    "MINOR": [0, 2, 3, 5, 7, 8, 10],
    "MINOR_HARMONIC": [0, 2, 3, 5, 7, 8, 11],
    "MINOR_MELODIC": [0, 2, 3, 5, 7, 9, 11],
    "DORIAN": [0, 2, 3, 5, 7, 9, 10],
    "PHRYGIAN": [0, 1, 3, 5, 7, 8, 10],
    "LYDIAN": [0, 2, 4, 6, 7, 9, 11],
    "MIXOLYDIAN": [0, 2, 4, 5, 7, 9, 10],
    "LOCRIAN": [0, 1, 3, 5, 6, 8, 10],
    "PENTATONIC_MAJOR": [0, 2, 4, 7, 9],
    "PENTATONIC_MINOR": [0, 3, 5, 7, 10],
    "BLUES": [0, 3, 5, 6, 7, 10],
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def get_scale_notes(root_pitch: int, scale_name: str) -> List[int]:
    """Retorna todos os pitches MIDI que pertencem à escala informada."""
    intervals = SCALE_INTERVALS.get(scale_name, SCALE_INTERVALS["CHROMATIC"])
    root = root_pitch % 12
    notes = set()
    for octave in range(11):  # cobre toda a extensão MIDI
        for interval in intervals:
            pitch = root + interval + (octave * 12)
            if 0 <= pitch <= 127:
                notes.add(pitch)
    return sorted(notes)


def is_note_in_scale(pitch: int, root_pitch: int, scale_name: str) -> bool:
    """Verifica se um pitch pertence à escala informada."""
    intervals = SCALE_INTERVALS.get(scale_name, SCALE_INTERVALS["CHROMATIC"])
    relative = (pitch - root_pitch) % 12
    return relative in intervals


def snap_pitch_to_scale(pitch: int, root_pitch: int, scale_name: str) -> int:
    """Arredonda o pitch para a nota mais próxima da escala."""
    if is_note_in_scale(pitch, root_pitch, scale_name):
        return pitch

    scale_notes = get_scale_notes(root_pitch, scale_name)
    if not scale_notes:
        return pitch

    # Encontra a nota mais próxima
    return min(scale_notes, key=lambda n: abs(n - pitch))


def scale_name_for_display(scale_name: str) -> str:
    for identifier, label, _desc in SCALE_ITEMS:
        if identifier == scale_name:
            return label
    return scale_name.title()


def get_note_name(pitch: int) -> str:
    """Nome da nota (ex: 60 -> C4)."""
    octave = (pitch // 12) - 1
    return f"{NOTE_NAMES[pitch % 12]}{octave}"