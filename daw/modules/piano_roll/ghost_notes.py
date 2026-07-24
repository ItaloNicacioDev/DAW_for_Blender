# modules/piano_roll/ghost_notes.py
"""
Ghost Notes (notas fantasma) para o Piano Roll.

Responsabilidade:
    Exibir notas de outros patterns ou faixas como referência visual
    semi-transparente no piano roll, facilitando a composição
    harmônica e rítmica.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .notes import PianoRollNote


@dataclass
class GhostNote:
    """Uma nota fantasma (referência visual apenas)."""

    pitch: int = 60
    start_beat: float = 0.0
    duration_beats: float = 0.25
    color: tuple = field(default_factory=lambda: (0.5, 0.5, 0.5))
    source_name: str = ""   # nome do pattern/faixa de origem


def create_ghost_notes_from_pattern(notes: List[PianoRollNote],
                                    color: tuple = (0.4, 0.4, 0.4),
                                    source_name: str = "") -> List[GhostNote]:
    """Converte notas reais em ghost notes para exibição de referência."""
    return [
        GhostNote(
            pitch=n.pitch,
            start_beat=n.start_beat,
            duration_beats=n.duration_beats,
            color=color,
            source_name=source_name,
        )
        for n in notes
    ]


def filter_ghost_notes_in_range(ghosts: List[GhostNote],
                                beat_start: float, beat_end: float,
                                pitch_min: int = 0, pitch_max: int = 127) -> List[GhostNote]:
    """Filtra ghost notes visíveis dentro de um range de tempo e pitch."""
    return [
        g for g in ghosts
        if beat_start <= g.start_beat < beat_end
        and pitch_min <= g.pitch <= pitch_max
    ]