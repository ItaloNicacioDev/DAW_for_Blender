# modules/effects/compressor.py
"""
Modelo de parâmetros do efeito Compressor (sem dependência de bpy).
Processamento real de áudio acontece no motor C++ — ver chorus.py para
a nota completa sobre a arquitetura.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

EFFECT_TYPE = "COMPRESSOR"


@dataclass
class CompressorParams:
    """Parâmetros do Compressor."""

    threshold_db: float = -18.0   # dB — nível a partir do qual comprime
    ratio: float = 4.0            # N:1
    attack_ms: float = 10.0       # ms
    release_ms: float = 120.0     # ms
    knee_db: float = 6.0          # dB — suavidade do joelho
    makeup_gain_db: float = 0.0   # dB — ganho de compensação
    mix: float = 1.0              # 0.0 - 1.0 — compressão paralela

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompressorParams":
        valid = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**valid)


DEFAULT = CompressorParams()

PRESETS: Dict[str, CompressorParams] = {
    "Vocal Suave":  CompressorParams(threshold_db=-20.0, ratio=3.0, attack_ms=15.0, release_ms=150.0, makeup_gain_db=3.0),
    "Bateria Punch": CompressorParams(threshold_db=-14.0, ratio=6.0, attack_ms=2.0, release_ms=80.0, makeup_gain_db=4.0),
    "Bus Master":   CompressorParams(threshold_db=-10.0, ratio=2.0, attack_ms=30.0, release_ms=250.0, makeup_gain_db=1.5),
}