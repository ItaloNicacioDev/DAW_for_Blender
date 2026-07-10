# modules/effects/phaser.py
"""
Modelo de parâmetros do efeito Phaser (sem dependência de bpy).
Processamento real de áudio acontece no motor C++ — ver chorus.py para
a nota completa sobre a arquitetura.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

EFFECT_TYPE = "PHASER"


@dataclass
class PhaserParams:
    """Parâmetros do Phaser."""

    rate: float = 0.5         # Hz — velocidade do LFO
    depth: float = 0.6        # 0.0 - 1.0
    feedback: float = 0.3     # 0.0 - 0.95
    stages: int = 4           # 2 - 12 (pares de all-pass) — mais estágios = mais "entalhes"
    mix: float = 0.5          # 0.0 (seco) - 1.0 (100% processado)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhaserParams":
        valid = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**valid)


DEFAULT = PhaserParams()

PRESETS: Dict[str, PhaserParams] = {
    "Suave":     PhaserParams(rate=0.3, depth=0.4, feedback=0.2, stages=4, mix=0.35),
    "Clássico":  PhaserParams(rate=0.5, depth=0.6, feedback=0.3, stages=4, mix=0.5),
    "Intenso":   PhaserParams(rate=0.8, depth=0.85, feedback=0.6, stages=8, mix=0.7),
}