# modules/effects/flanger.py
"""
Modelo de parâmetros do efeito Flanger (sem dependência de bpy).
Processamento real de áudio acontece no motor C++ — ver chorus.py para
a nota completa sobre a arquitetura.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

EFFECT_TYPE = "FLANGER"


@dataclass
class FlangerParams:
    """Parâmetros do Flanger."""

    rate: float = 0.25        # Hz — velocidade do LFO
    depth: float = 0.5        # 0.0 - 1.0
    feedback: float = 0.4     # 0.0 - 0.95 — regeneração (ressonância metálica)
    manual_ms: float = 1.0    # ms — atraso base antes da modulação
    mix: float = 0.5          # 0.0 (seco) - 1.0 (100% processado)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlangerParams":
        valid = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**valid)


DEFAULT = FlangerParams()

PRESETS: Dict[str, FlangerParams] = {
    "Suave":    FlangerParams(rate=0.15, depth=0.3, feedback=0.2, mix=0.35),
    "Clássico": FlangerParams(rate=0.25, depth=0.5, feedback=0.4, mix=0.5),
    "Jato":     FlangerParams(rate=0.5, depth=0.8, feedback=0.7, mix=0.65),
}