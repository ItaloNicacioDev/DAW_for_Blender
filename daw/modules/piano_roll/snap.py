# modules/piano_roll/snap.py
"""
Snap (encaixe ao grid) para o Piano Roll.

Responsabilidade:
    Funções de snap para posição e duração de notas, além de
    snap a eventos específicos (barra, beat, subdivisão).
"""
from __future__ import annotations

from typing import List, Optional


SNAP_DIVISIONS = {
    "BAR": 4.0,       # 1 bar (4 beats)
    "HALF": 2.0,      # 1/2 bar
    "QUARTER": 1.0,   # 1/4 bar = 1 beat
    "EIGHTH": 0.5,    # 1/8
    "SIXTEENTH": 0.25, # 1/16
    "THIRTYSECOND": 0.125,  # 1/32
    "TRIPLET_EIGHTH": 2.0 / 3.0,
    "TRIPLET_SIXTEENTH": 1.0 / 3.0,
}

SNAP_ITEMS = (
    ("BAR", "Barra", "Snap a cada barra"),
    ("HALF", "1/2", "Snap a meias barras"),
    ("QUARTER", "1/4", "Snap a beats"),
    ("EIGHTH", "1/8", "Snap a oitavos"),
    ("SIXTEENTH", "1/16", "Snap a dezesseis avos"),
    ("THIRTYSECOND", "1/32", "Snap a trinta e dois avos"),
    ("TRIPLET_EIGHTH", "1/8T", "Snap a oitavos em terçina"),
    ("TRIPLET_SIXTEENTH", "1/16T", "Snap a dezesseis avos em terçina"),
    ("NONE", "Desligado", "Sem snap"),
)


def snap_value(value: float, division_name: str) -> float:
    """Encaixa um valor ao grid de snap informado."""
    if division_name == "NONE":
        return value
    grid = SNAP_DIVISIONS.get(division_name, 0.25)
    if grid <= 0.0:
        return value
    return round(value / grid) * grid


def snap_beat_to_bar(beat: float) -> float:
    """Snap ao início da barra mais próxima."""
    return round(beat / 4.0) * 4.0


def snap_beat_to_beat(beat: float) -> float:
    """Snap ao beat mais próximo."""
    return round(beat)


def get_division_value(division_name: str) -> float:
    """Retorna o valor em beats da divisão de snap."""
    return SNAP_DIVISIONS.get(division_name, 0.25)