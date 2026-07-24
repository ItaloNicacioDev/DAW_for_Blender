# modules/piano_roll/utils.py
"""
Utilitários do Piano Roll.

Responsabilidade:
    Funções auxiliares numéricas, conversões e helpers de UI.
"""
from __future__ import annotations

import math
from typing import Tuple


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def clamp_index(index: int, length: int) -> int:
    if length <= 0:
        return 0
    return max(0, min(index, length - 1))


def pitch_to_y(pitch: int, key_height: float = 10.0, min_pitch: int = 0) -> float:
    """Converte pitch MIDI para coordenada Y no piano roll."""
    return (pitch - min_pitch) * key_height


def y_to_pitch(y: float, key_height: float = 10.0, min_pitch: int = 0) -> int:
    """Converte coordenada Y para pitch MIDI."""
    return int(y / key_height) + min_pitch


def beat_to_x(beat: float, pixels_per_beat: float = 40.0) -> float:
    """Converte posição em beats para coordenada X."""
    return beat * pixels_per_beat


def x_to_beat(x: float, pixels_per_beat: float = 40.0) -> float:
    """Converte coordenada X para posição em beats."""
    return x / pixels_per_beat


def is_black_key(pitch: int) -> bool:
    """Verifica se um pitch MIDI é uma tecla preta do piano."""
    return (pitch % 12) in [1, 3, 6, 8, 10]


def get_key_color(pitch: int) -> Tuple[float, float, float]:
    """Retorna a cor de fundo de uma tecla do piano roll."""
    if is_black_key(pitch):
        return (0.15, 0.15, 0.15)
    # Cores para notas C (raiz das oitavas)
    if (pitch % 12) == 0:
        return (0.35, 0.35, 0.35)
    return (0.25, 0.25, 0.25)


def format_beat(beat: float) -> str:
    """Formata um valor em beats como "bar.beat" (ex: 4.1 -> "1.1.0")."""
    bar = int(beat // 4) + 1
    beat_in_bar = int(beat % 4) + 1
    fraction = int((beat % 1.0) * 100)
    return f"{bar}.{beat_in_bar}.{fraction:02d}"