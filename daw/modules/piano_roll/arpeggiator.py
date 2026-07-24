# modules/piano_roll/arpeggiator.py
"""
Arpeggiator para o Piano Roll.

Responsabilidade:
    Gerar sequências de notas (arpejos) a partir de um conjunto de
    pitches, com diferentes direções e padrões rítmicos.
"""
from __future__ import annotations

from typing import List

from .notes import PianoRollNote

# Padrões de arpejo
ARPEGGIO_PATTERNS = {
    "UP": lambda notes: sorted(notes),
    "DOWN": lambda notes: sorted(notes, reverse=True),
    "UP_DOWN": lambda notes: sorted(notes) + sorted(notes, reverse=True)[1:-1],
    "DOWN_UP": lambda notes: sorted(notes, reverse=True) + sorted(notes)[1:-1],
    "RANDOM": lambda notes: notes,  # será embaralhado na geração
}

ARPEGGIO_ITEMS = (
    ("UP", "Crescente", "Do grave ao agudo"),
    ("DOWN", "Decrescente", "Do agudo ao grave"),
    ("UP_DOWN", "Crescente/Decrescente", "Sobe e desce"),
    ("DOWN_UP", "Decrescente/Crescente", "Desce e sobe"),
    ("RANDOM", "Aleatório", "Ordem aleatória"),
)


def generate_arpeggio(pitches: List[int], pattern: str = "UP",
                      start_beat: float = 0.0, step_beats: float = 0.25,
                      duration_beats: float = 0.2, velocity: float = 0.8,
                      octaves: int = 1) -> List[PianoRollNote]:
    """
    Gera um arpejo a partir de uma lista de pitches.

    Args:
        pitches: lista de pitches MIDI base
        pattern: nome do padrão (UP, DOWN, etc.)
        start_beat: beat inicial
        step_beats: intervalo entre notas em beats
        duration_beats: duração de cada nota
        velocity: velocity base
        octaves: quantas oitavas expandir

    Returns:
        Lista de PianoRollNote
    """
    import random

    # Expande para o número de oitavas
    expanded = []
    for oct_ in range(octaves):
        for p in pitches:
            new_pitch = p + (oct_ * 12)
            if 0 <= new_pitch <= 127:
                expanded.append(new_pitch)

    if not expanded:
        return []

    # Aplica o padrão
    if pattern == "RANDOM":
        random.shuffle(expanded)
        ordered = expanded
    else:
        fn = ARPEGGIO_PATTERNS.get(pattern, ARPEGGIO_PATTERNS["UP"])
        ordered = fn(expanded)

    notes = []
    for i, pitch in enumerate(ordered):
        note = PianoRollNote(
            pitch=pitch,
            start_beat=start_beat + (i * step_beats),
            duration_beats=duration_beats,
            velocity=velocity,
        )
        notes.append(note)

    return notes