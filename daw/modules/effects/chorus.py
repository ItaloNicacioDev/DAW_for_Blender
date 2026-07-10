# modules/effects/chorus.py
"""
Modelo de parâmetros do efeito Chorus (sem dependência de bpy).

O processamento de áudio real acontece no motor C++ (core/engine.py via
daw_bridge); esta classe representa apenas o conjunto de parâmetros que é
enviado ao motor e espelhado pela UI (ver properties.py / ui.py).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

EFFECT_TYPE = "CHORUS"


@dataclass
class ChorusParams:
    """Parâmetros do Chorus."""

    rate: float = 1.2        # Hz — velocidade do LFO de modulação
    depth: float = 0.35      # 0.0 - 1.0 — profundidade da modulação
    voices: int = 2          # 1 - 4 — número de vozes duplicadas
    feedback: float = 0.15   # 0.0 - 0.9
    mix: float = 0.5         # 0.0 (seco) - 1.0 (100% processado)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChorusParams":
        valid = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**valid)


DEFAULT = ChorusParams()

PRESETS: Dict[str, ChorusParams] = {
    "Sutil":  ChorusParams(rate=0.6, depth=0.20, voices=2, feedback=0.05, mix=0.30),
    "Clássico": ChorusParams(rate=1.2, depth=0.35, voices=2, feedback=0.15, mix=0.50),
    "Amplo":  ChorusParams(rate=1.8, depth=0.55, voices=4, feedback=0.25, mix=0.65),
}