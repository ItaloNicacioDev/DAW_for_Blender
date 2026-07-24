# modules/patterns/utils.py
"""
Utilitários do módulo Patterns.

Responsabilidade:
    Funções auxiliares numéricas, nomes únicos e ponte com outros
    módulos da DAW (ex: mixer, transporte).
"""
from __future__ import annotations

from typing import Optional


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def clamp_index(index: int, length: int) -> int:
    if length <= 0:
        return 0
    return max(0, min(index, length - 1))


def unique_pattern_name(patterns_props, base_name: str) -> str:
    """Garante que `base_name` seja único entre os patterns existentes."""
    existing = {p.name for p in patterns_props.patterns}
    if base_name not in existing:
        return base_name
    n = 2
    while f"{base_name} ({n})" in existing:
        n += 1
    return f"{base_name} ({n})"


def unique_group_name(patterns_props, base_name: str) -> str:
    """Garante que `base_name` seja único entre os grupos existentes."""
    existing = {g.name for g in patterns_props.groups}
    if base_name not in existing:
        return base_name
    n = 2
    while f"{base_name} ({n})" in existing:
        n += 1
    return f"{base_name} ({n})"


def beat_to_step(beat: float, steps_per_beat: int = 4) -> int:
    """Converte posição em beats para step index."""
    return int(beat * steps_per_beat)


def step_to_beat(step: int, steps_per_beat: int = 4) -> float:
    """Converte step index para posição em beats."""
    return step / steps_per_beat


def midi_note_name(pitch: int) -> str:
    """Converte número MIDI (0-127) para nome de nota (ex: 60 -> C4)."""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    pitch = max(0, min(127, pitch))
    octave = (pitch // 12) - 1
    return f"{names[pitch % 12]}{octave}"