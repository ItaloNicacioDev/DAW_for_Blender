# modules/piano_roll/quantize.py
"""
Quantização de notas para o Piano Roll.

Responsabilidade:
    Alinhar o timing (start_beat) e opcionalmente a duração das notas
    ao grid musical, com controle de intensidade (0.0 = nenhuma
    quantização, 1.0 = quantização total).
"""
from __future__ import annotations

from typing import List

from .notes import PianoRollNote


def quantize_beat(beat: float, grid_division: float = 0.25, strength: float = 1.0) -> float:
    """
    Quantiza um valor em beats para o grid mais próximo.

    Args:
        beat: posição em beats
        grid_division: divisão do grid (0.25 = 1/4 de beat = 16th note)
        strength: 0.0-1.0 (0 = sem quantização, 1 = total)

    Returns:
        Posição quantizada
    """
    if strength <= 0.0 or grid_division <= 0.0:
        return beat

    target = round(beat / grid_division) * grid_division
    return beat + (target - beat) * strength


def quantize_notes(notes: List[PianoRollNote], grid_division: float = 0.25,
                   strength: float = 1.0, quantize_duration: bool = False) -> None:
    """Quantiza o timing de uma lista de notas in-place."""
    for note in notes:
        note.start_beat = quantize_beat(note.start_beat, grid_division, strength)
        if quantize_duration:
            note.duration_beats = max(0.01, quantize_beat(note.duration_beats, grid_division, strength))


def quantize_note_starts_only(notes: List[PianoRollNote], grid_division: float = 0.25,
                              strength: float = 1.0) -> None:
    """Quantiza apenas os pontos de início das notas."""
    quantize_notes(notes, grid_division, strength, quantize_duration=False)