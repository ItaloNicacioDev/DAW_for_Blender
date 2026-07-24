# modules/playlist/markers.py
"""
Marcadores da Timeline — sem dependência de bpy.

Responsabilidade:
    Representar marcadores de posição na timeline (intro, drop,
    breakdown, etc.) com nome, cor e posição em beats.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimelineMarker:
    """Um marcador na timeline."""

    name: str = "Marcador"
    beat: float = 0.0
    color: tuple = field(default_factory=lambda: (0.9, 0.3, 0.3))

    def __repr__(self) -> str:
        return f"TimelineMarker(name={self.name!r}, beat={self.beat:.2f})"