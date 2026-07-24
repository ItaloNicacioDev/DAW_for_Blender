# modules/piano_roll/notes.py
"""
Modelo de dados de uma nota no Piano Roll — sem dependência de bpy.

Responsabilidade:
    Representar uma nota individual no editor piano roll com posição
    temporal (beat), pitch MIDI, velocity, duração e estado de seleção.

Arquitetura:
    notes.py      → PianoRollNote: modelo puro de nota (este arquivo)
    scales.py     → escalas musicais
    chords.py     → acordes
    quantize.py   → quantização de timing
    snap.py       → snap a grid
    humanize.py   → variação aleatória natural
    arpeggiator.py→ geração de arpejos
    ghost_notes.py→ notas fantasma de referência
    selection.py  → gerenciamento de seleção
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PianoRollNote:
    """Uma nota no piano roll."""

    pitch: int = 60              # MIDI note number (0-127)
    start_beat: float = 0.0      # posição de início em beats
    duration_beats: float = 0.25 # duração em beats
    velocity: float = 0.8        # 0.0 - 1.0

    selected: bool = False
    muted: bool = False

    # Metadados para edição
    original_start: Optional[float] = None   # usado durante drag
    original_pitch: Optional[int] = None     # usado durante drag

    def __post_init__(self):
        self.pitch = max(0, min(127, self.pitch))
        self.velocity = max(0.0, min(1.0, self.velocity))
        self.start_beat = max(0.0, self.start_beat)
        self.duration_beats = max(0.01, self.duration_beats)

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.duration_beats

    @property
    def midi_velocity(self) -> int:
        """Velocity em escala MIDI 0-127."""
        return int(self.velocity * 127)

    def move(self, delta_beats: float, delta_pitch: int = 0) -> None:
        self.start_beat = max(0.0, self.start_beat + delta_beats)
        self.pitch = max(0, min(127, self.pitch + delta_pitch))

    def resize(self, delta_beats: float) -> None:
        self.duration_beats = max(0.01, self.duration_beats + delta_beats)

    def duplicate(self) -> "PianoRollNote":
        return PianoRollNote(
            pitch=self.pitch,
            start_beat=self.start_beat,
            duration_beats=self.duration_beats,
            velocity=self.velocity,
            selected=False,
            muted=self.muted,
        )

    def __repr__(self) -> str:
        return (
            f"PianoRollNote(pitch={self.pitch}, start={self.start_beat:.3f}, "
            f"dur={self.duration_beats:.3f}, vel={self.velocity:.2f})"
        )