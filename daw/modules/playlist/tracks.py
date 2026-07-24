# modules/playlist/tracks.py
"""
Tracks da Playlist (Arrangement) — sem dependência de bpy.

Responsabilidade:
    Representar as faixas horizontais da timeline onde os clips
    são posicionados. Cada track da playlist está vinculada a uma
    faixa do mixer pelo índice.

Arquitetura:
    tracks.py   → PlaylistTrack: modelo puro de faixa da playlist
    clips.py    → PlaylistClip: clip posicionado na timeline
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class PlaylistTrack:
    """Uma faixa da playlist/timeline."""

    name: str = "Track 1"
    mixer_track_index: int = 0   # índice da faixa correspondente no mixer
    color: tuple = field(default_factory=lambda: (0.6, 0.6, 0.6))

    muted: bool = False
    solo: bool = False
    locked: bool = False         # impede edição de clips

    height: int = 40             # altura em pixels (para UI)

    def __repr__(self) -> str:
        return f"PlaylistTrack(name={self.name!r}, mixer={self.mixer_track_index})"