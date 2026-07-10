# modules/channel_rack/channels.py
"""
Modelo de dados de um canal do Channel Rack (sem dependência de bpy).

Responsabilidade:
    Representar um canal (instrumento/sample/áudio) com seu pattern de
    steps, volume, pan, mute/solo e cor. Este é o "dado real"; o estado
    editável exposto ao Blender vive em properties.py (RNA), que espelha
    estes campos para desenho da UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .colors import Color, get_color_by_index

MAX_STEPS = 64
DEFAULT_STEP_COUNT = 16

INSTRUMENT_TYPES = ("SAMPLER", "SYNTH", "AUDIO", "MIDI", "DRUM")


@dataclass
class Channel:
    """Um canal individual do rack."""

    name: str = "Novo Canal"
    instrument_type: str = "SAMPLER"
    sample_path: str = ""

    color: Color = field(default_factory=lambda: get_color_by_index(0))

    volume: float = 0.78          # 0.0 - 1.0 (linear, subtype FACTOR na UI)
    pan: float = 0.0              # -1.0 (esquerda) .. 1.0 (direita)
    mute: bool = False
    solo: bool = False
    locked: bool = False          # impede edição acidental dos steps

    group_index: int = -1         # -1 = sem grupo (ver groups.py)

    steps: List[bool] = field(default_factory=lambda: [False] * MAX_STEPS)
    step_count: int = DEFAULT_STEP_COUNT

    def toggle_step(self, index: int) -> bool:
        """Alterna um step e retorna o novo estado. Ignora índices fora do range ativo."""
        if self.locked or not (0 <= index < self.step_count):
            return self.steps[index] if 0 <= index < len(self.steps) else False
        self.steps[index] = not self.steps[index]
        return self.steps[index]

    def set_step(self, index: int, value: bool) -> None:
        if self.locked or not (0 <= index < len(self.steps)):
            return
        self.steps[index] = value

    def clear_steps(self) -> None:
        if self.locked:
            return
        self.steps = [False] * MAX_STEPS

    def active_steps(self) -> List[int]:
        """Índices dos steps ativos dentro do range de step_count atual."""
        return [i for i in range(self.step_count) if self.steps[i]]

    def is_audible(self, any_solo_active: bool) -> bool:
        """
        Um canal soa se:
          - não estiver mutado, E
          - (nenhum canal do rack está em solo) OU (este canal está em solo).
        """
        if self.mute:
            return False
        if any_solo_active and not self.solo:
            return False
        return True

    def duplicate(self, new_name: Optional[str] = None) -> "Channel":
        """Cria uma cópia independente deste canal (usado por 'Duplicar Canal')."""
        return Channel(
            name=new_name or f"{self.name} (cópia)",
            instrument_type=self.instrument_type,
            sample_path=self.sample_path,
            color=self.color,
            volume=self.volume,
            pan=self.pan,
            mute=self.mute,
            solo=False,
            locked=False,
            group_index=self.group_index,
            steps=list(self.steps),
            step_count=self.step_count,
        )