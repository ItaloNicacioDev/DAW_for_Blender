# modules/piano_roll/humanize.py
"""
Humanização de notas para o Piano Roll.

Responsabilidade:
    Aplicar variações aleatórias sutis no timing, velocity e duração
    das notas para simular a imperfeição natural de um performance
    humano.
"""
from __future__ import annotations

import random
from typing import List

from .notes import PianoRollNote


def humanize_timing(notes: List[PianoRollNote], amount: float = 0.1,
                    max_offset_beats: float = 0.05) -> None:
    """
    Aplica variação aleatória no timing das notas.

    Args:
        amount: intensidade 0.0-1.0
        max_offset_beats: deslocamento máximo em beats
    """
    if amount <= 0.0:
        return
    for note in notes:
        offset = (random.random() * 2.0 - 1.0) * max_offset_beats * amount
        note.start_beat = max(0.0, note.start_beat + offset)


def humanize_velocity(notes: List[PianoRollNote], amount: float = 0.1) -> None:
    """Aplica variação aleatória na velocity das notas."""
    if amount <= 0.0:
        return
    for note in notes:
        delta = (random.random() * 2.0 - 1.0) * amount
        note.velocity = max(0.0, min(1.0, note.velocity + delta))


def humanize_duration(notes: List[PianoRollNote], amount: float = 0.1,
                      max_offset_beats: float = 0.05) -> None:
    """Aplica variação aleatória na duração das notas."""
    if amount <= 0.0:
        return
    for note in notes:
        offset = (random.random() * 2.0 - 1.0) * max_offset_beats * amount
        note.duration_beats = max(0.01, note.duration_beats + offset)


def humanize(notes: List[PianoRollNote], timing_amount: float = 0.1,
             velocity_amount: float = 0.1, duration_amount: float = 0.05) -> None:
    """Aplica humanização completa (timing + velocity + duração)."""
    humanize_timing(notes, timing_amount)
    humanize_velocity(notes, velocity_amount)
    humanize_duration(notes, duration_amount)