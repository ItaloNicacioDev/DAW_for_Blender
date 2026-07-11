# modules/instruments/instruments.py
"""
Modelo de dados de um Instrumento (sem dependência de bpy).

Responsabilidade:
    Representar um instrumento configurado a partir do sintetizador
    interno (synth.py — INSTRUMENTS 0-7, estilo GM): qual timbre usa,
    volume/pan, deslocamento de oitava, modo mono/poly e limite de vozes.
    Este é o "dado real"; o estado editável exposto ao Blender vive em
    properties.py (RNA), que espelha estes campos para desenho da UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import synth

MIN_OCTAVE_SHIFT = -3
MAX_OCTAVE_SHIFT = 3


def gm_instrument_names() -> list[tuple[int, str]]:
    """Lista (id, nome) de todos os timbres GM disponíveis em synth.INSTRUMENTS."""
    return [(iid, data["name"]) for iid, data in sorted(synth.INSTRUMENTS.items())]


@dataclass
class Instrument:
    """Um instrumento do rack, referenciando um timbre do sintetizador interno."""

    name: str = "Novo Instrumento"
    instrument_id: int = 0          # chave em synth.INSTRUMENTS (0-7)

    volume: float = 0.8             # 0.0 - 1.0
    pan: float = 0.0                # -1.0 (esquerda) .. 1.0 (direita)

    octave_shift: int = 0           # desloca a nota tocada em oitavas antes de sintetizar
    mono: bool = False              # True = monofônico (corta nota anterior ao tocar outra)
    polyphony: int = 8              # limite de vozes simultâneas quando mono=False

    pitch_bend_range: int = 2       # semitons — reservado para uso futuro com MIDI externo
    mute: bool = False
    solo: bool = False

    def gm_name(self) -> str:
        """Nome amigável do timbre GM associado (ex: 'Acoustic Piano')."""
        inst = synth.INSTRUMENTS.get(self.instrument_id)
        return inst["name"] if inst else f"Timbre {self.instrument_id}"

    def apply_octave_shift(self, pitch: int) -> int:
        """Aplica o deslocamento de oitava a uma nota MIDI, mantendo-a no range válido (0-127)."""
        shifted = pitch + (self.octave_shift * 12)
        return max(0, min(127, shifted))

    def is_audible(self, any_solo_active: bool) -> bool:
        if self.mute:
            return False
        if any_solo_active and not self.solo:
            return False
        return True

    def duplicate(self, new_name: Optional[str] = None) -> "Instrument":
        return Instrument(
            name=new_name or f"{self.name} (cópia)",
            instrument_id=self.instrument_id,
            volume=self.volume,
            pan=self.pan,
            octave_shift=self.octave_shift,
            mono=self.mono,
            polyphony=self.polyphony,
            pitch_bend_range=self.pitch_bend_range,
            mute=self.mute,
            solo=False,
        )