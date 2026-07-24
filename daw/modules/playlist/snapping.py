# modules/playlist/snapping.py
"""
Snap na Timeline da Playlist — sem dependência de bpy.

Responsabilidade:
    Funções de snap para posicionamento de clips na timeline,
    incluindo snap a grid, a clips vizinhos, e a marcadores.
"""
from __future__ import annotations

from typing import List, Optional

SNAP_DIVISIONS = {
    "BAR": 4.0,
    "HALF": 2.0,
    "BEAT": 1.0,
    "HALF_BEAT": 0.5,
    "QUARTER_BEAT": 0.25,
    "EIGHTH_BEAT": 0.125,
}

SNAP_ITEMS = (
    ("BAR", "Barra", "Snap a cada barra"),
    ("HALF", "1/2", "Snap a meias barras"),
    ("BEAT", "Beat", "Snap a cada beat"),
    ("HALF_BEAT", "1/2 Beat", "Snap a 1/2 beat"),
    ("QUARTER_BEAT", "1/4 Beat", "Snap a 1/4 beat"),
    ("EIGHTH_BEAT", "1/8 Beat", "Snap a 1/8 beat"),
    ("NONE", "Desligado", "Sem snap"),
)


def snap_to_grid(beat: float, division_name: str) -> float:
    """Encaixa um valor em beats ao grid."""
    if division_name == "NONE":
        return beat
    grid = SNAP_DIVISIONS.get(division_name, 1.0)
    if grid <= 0.0:
        return beat
    return round(beat / grid) * grid


def snap_to_nearest_clip_edge(beat: float, clip_starts: List[float],
                              clip_ends: List[float], threshold: float = 0.1) -> float:
    """Snap ao início ou fim do clip mais próximo dentro do threshold."""
    edges = clip_starts + clip_ends
    if not edges:
        return beat

    nearest = min(edges, key=lambda e: abs(e - beat))
    if abs(nearest - beat) <= threshold:
        return nearest
    return beat


def snap_to_marker(beat: float, marker_beats: List[float],
                   threshold: float = 0.1) -> float:
    """Snap ao marcador mais próximo dentro do threshold."""
    if not marker_beats:
        return beat
    nearest = min(marker_beats, key=lambda m: abs(m - beat))
    if abs(nearest - beat) <= threshold:
        return nearest
    return beat