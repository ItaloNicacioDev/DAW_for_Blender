# modules/patterns/clips.py
"""
Modelo de dados de um Clip (instância de Pattern na timeline) — sem bpy.

Responsabilidade:
    Representar uma ocorrência de um pattern na timeline da DAW.
    Um clip referencia um pattern pelo nome e define quando ele começa,
    por quanto tempo dura, e em qual faixa (track) do mixer ele toca.

Arquitetura:
    patterns.py  — Pattern: modelo puro de sequência
    clips.py     — PatternClip: instância na timeline (este arquivo)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PatternClip:
    """Uma ocorrência de um pattern na timeline da DAW."""

    pattern_name: str = ""           # referência ao pattern
    track_index: int = 0             # índice da faixa do mixer

    start_beat: float = 0.0          # início na timeline (em beats)
    duration_beats: float = 4.0      # duração na timeline (em beats)
    offset_beats: float = 0.0        # offset dentro do pattern (em beats)

    enabled: bool = True
    color_override: Optional[tuple] = None   # None = usa a cor do pattern

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.duration_beats

    def move(self, new_start: float) -> None:
        self.start_beat = max(0.0, new_start)

    def resize(self, new_duration: float) -> None:
        self.duration_beats = max(0.25, new_duration)

    def split(self, at_beat: float) -> Optional["PatternClip"]:
        """Divide o clip em dois no beat informado. Retorna o novo clip (segunda metade)."""
        if at_beat <= self.start_beat or at_beat >= self.end_beat:
            return None

        first_duration = at_beat - self.start_beat
        second_offset = self.offset_beats + first_duration

        # Ajusta o clip original (primeira metade)
        self.duration_beats = first_duration

        # Cria o novo clip (segunda metade)
        new_clip = PatternClip(
            pattern_name=self.pattern_name,
            track_index=self.track_index,
            start_beat=at_beat,
            duration_beats=self.end_beat - at_beat,
            offset_beats=second_offset,
            enabled=self.enabled,
            color_override=self.color_override,
        )
        return new_clip

    def __repr__(self) -> str:
        return (
            f"PatternClip(pattern={self.pattern_name!r}, track={self.track_index}, "
            f"start={self.start_beat:.2f}, dur={self.duration_beats:.2f})"
        )