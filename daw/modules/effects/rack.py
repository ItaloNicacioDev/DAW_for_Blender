# modules/effects/rack.py
"""
EffectsRack — modelo central da cadeia de inserts (sem dependência de bpy).

Responsabilidade:
    Gerenciar, por canal, uma cadeia ordenada de efeitos (inserts). Cada
    slot guarda o tipo de efeito e seus parâmetros (ver chorus.py,
    compressor.py, delay.py, distortion.py, eq.py, flanger.py, limiter.py,
    phaser.py, reverb.py). É o "core" usado tanto pela UI (via
    properties.py, que espelha estes dados em RNA) quanto pelo motor de
    áudio (core/engine.py), que aplica a cadeia por canal a cada buffer.

Uso típico:
    from daw.modules.effects import EffectsRack

    rack = EffectsRack()
    chain = rack.get_chain(channel_index=0)
    chain.add_effect("COMPRESSOR")
    chain.add_effect("REVERB")
    chain.slots[0].params_dict["ratio"] = 6.0
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import chorus, compressor, delay, distortion, eq, flanger, limiter, phaser, reverb

EFFECT_TYPES = (
    "CHORUS", "COMPRESSOR", "DELAY", "DISTORTION", "EQ",
    "FLANGER", "LIMITER", "PHASER", "REVERB",
)

# Mapeia tipo de efeito -> (classe de parâmetros, instância DEFAULT, dict de PRESETS)
_EFFECT_MODULES = {
    "CHORUS": chorus,
    "COMPRESSOR": compressor,
    "DELAY": delay,
    "DISTORTION": distortion,
    "EQ": eq,
    "FLANGER": flanger,
    "LIMITER": limiter,
    "PHASER": phaser,
    "REVERB": reverb,
}


def default_params_for(effect_type: str) -> Dict[str, Any]:
    """Retorna os parâmetros padrão (como dict) para um tipo de efeito."""
    module = _EFFECT_MODULES.get(effect_type)
    if module is None:
        return {}
    return module.DEFAULT.to_dict()


def presets_for(effect_type: str) -> Dict[str, Any]:
    """Retorna o dict de presets nomeados disponíveis para um tipo de efeito."""
    module = _EFFECT_MODULES.get(effect_type)
    if module is None:
        return {}
    return module.PRESETS


@dataclass
class EffectSlot:
    """Um efeito dentro da cadeia de inserts de um canal."""

    effect_type: str = "EQ"
    enabled: bool = True
    bypass: bool = False
    params_dict: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.params_dict:
            self.params_dict = default_params_for(self.effect_type)

    def apply_preset(self, preset_name: str) -> bool:
        """Aplica um preset nomeado (ex: 'Hall', 'Loudness') a este slot."""
        presets = presets_for(self.effect_type)
        preset = presets.get(preset_name)
        if preset is None:
            return False
        self.params_dict = preset.to_dict()
        return True

    def reset_to_default(self) -> None:
        self.params_dict = default_params_for(self.effect_type)

    def is_active(self) -> bool:
        return self.enabled and not self.bypass


@dataclass
class EffectsChain:
    """Cadeia ordenada de EffectSlot aplicada a um único canal."""

    slots: List[EffectSlot] = field(default_factory=list)

    def add_effect(self, effect_type: str, index: Optional[int] = None) -> EffectSlot:
        slot = EffectSlot(effect_type=effect_type)
        if index is None or index >= len(self.slots):
            self.slots.append(slot)
        else:
            self.slots.insert(max(0, index), slot)
        return slot

    def remove_effect(self, index: int) -> bool:
        if not (0 <= index < len(self.slots)):
            return False
        del self.slots[index]
        return True

    def move_effect(self, index: int, direction: int) -> bool:
        target = index + direction
        if not (0 <= index < len(self.slots)) or not (0 <= target < len(self.slots)):
            return False
        self.slots[index], self.slots[target] = self.slots[target], self.slots[index]
        return True

    def active_slots(self) -> List[EffectSlot]:
        """Retorna apenas os slots que devem ser processados (não bypassados)."""
        return [s for s in self.slots if s.is_active()]

    def clear(self) -> None:
        self.slots.clear()


class EffectsRack:
    """Contêiner de EffectsChain, uma por índice de canal (ver channel_rack)."""

    def __init__(self) -> None:
        self._chains: Dict[int, EffectsChain] = {}

    def get_chain(self, channel_index: int) -> EffectsChain:
        """Retorna a cadeia do canal, criando uma vazia se ainda não existir."""
        if channel_index not in self._chains:
            self._chains[channel_index] = EffectsChain()
        return self._chains[channel_index]

    def remove_chain(self, channel_index: int) -> None:
        self._chains.pop(channel_index, None)

    def has_chain(self, channel_index: int) -> bool:
        return channel_index in self._chains and len(self._chains[channel_index].slots) > 0

    def clear(self) -> None:
        self._chains.clear()