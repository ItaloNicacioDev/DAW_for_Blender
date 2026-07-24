# modules/patterns/patterns.py
"""
Modelo de dados de um Pattern (sequência musical) — sem dependência de bpy.

Responsabilidade:
    Representar um pattern como uma grade de passos (step sequencer) ou
    lista de notas/eventos MIDI. Cada pattern tem um nome, cor, comprimento
    em passos, e uma coleção de notas.

Arquitetura:
    patterns.py  — Pattern, PatternNote: modelo puro (este arquivo)
    clips.py     — PatternClip: instância de pattern na timeline
    groups.py    — PatternGroup: agrupamento lógico de patterns
    colors.py    — paleta de cores
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .colors import get_color_by_index

DEFAULT_PATTERN_LENGTH = 16   # 16 steps (1 bar em 1/16)
DEFAULT_VELOCITY = 0.8
DEFAULT_PITCH = 60            # C4


@dataclass
class PatternNote:
    """Uma nota/evento dentro de um pattern."""

    pitch: int = DEFAULT_PITCH          # MIDI note number (0-127)
    velocity: float = DEFAULT_VELOCITY  # 0.0 - 1.0
    start_step: int = 0                 # posição no grid (0-based)
    duration_steps: int = 1             # duração em steps
    enabled: bool = True

    def __post_init__(self):
        self.pitch = max(0, min(127, self.pitch))
        self.velocity = max(0.0, min(1.0, self.velocity))
        self.start_step = max(0, self.start_step)
        self.duration_steps = max(1, self.duration_steps)


@dataclass
class Pattern:
    """Um pattern/sequência musical (step sequencer style)."""

    name: str = "Novo Pattern"
    color: tuple = field(default_factory=lambda: get_color_by_index(0))

    length_steps: int = DEFAULT_PATTERN_LENGTH
    bpm: float = 120.0
    time_signature_num: int = 4
    time_signature_den: int = 4

    notes: List[PatternNote] = field(default_factory=list)

    # Metadados
    is_looping: bool = True
    swing: float = 0.0   # 0.0 - 1.0

    # ------------------------------------------------------------------
    # Notas
    # ------------------------------------------------------------------
    def add_note(self, pitch: int = DEFAULT_PITCH, velocity: float = DEFAULT_VELOCITY,
                 start_step: int = 0, duration_steps: int = 1) -> PatternNote:
        note = PatternNote(pitch=pitch, velocity=velocity,
                           start_step=start_step, duration_steps=duration_steps)
        self.notes.append(note)
        return note

    def remove_note(self, index: int) -> bool:
        if not (0 <= index < len(self.notes)):
            return False
        del self.notes[index]
        return True

    def get_notes_at_step(self, step: int) -> List[PatternNote]:
        """Retorna todas as notas que começam no step informado."""
        return [n for n in self.notes if n.start_step == step and n.enabled]

    def clear_notes(self) -> None:
        self.notes.clear()

    # ------------------------------------------------------------------
    # Grid / steps
    # ------------------------------------------------------------------
    def resize(self, new_length: int) -> None:
        """Redimensiona o pattern, removendo notas fora do novo range."""
        self.length_steps = max(1, new_length)
        self.notes = [n for n in self.notes
                      if n.start_step < self.length_steps]

    def duplicate(self, new_name: str = None) -> "Pattern":
        return Pattern(
            name=new_name or f"{self.name} (cópia)",
            color=self.color,
            length_steps=self.length_steps,
            bpm=self.bpm,
            time_signature_num=self.time_signature_num,
            time_signature_den=self.time_signature_den,
            notes=[PatternNote(**vars(n)) for n in self.notes],
            is_looping=self.is_looping,
            swing=self.swing,
        )

    def __repr__(self) -> str:
        return (
            f"Pattern(name={self.name!r}, steps={self.length_steps}, "
            f"notes={len(self.notes)}, bpm={self.bpm})"
        )