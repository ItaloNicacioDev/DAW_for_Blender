# modules/effects/limiter.py
"""
Modelo de parâmetros do efeito Limiter (sem dependência de bpy).
Processamento real de áudio acontece no motor C++ — ver chorus.py para
a nota completa sobre a arquitetura.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

EFFECT_TYPE = "LIMITER"


@dataclass
class LimiterParams:
    """Parâmetros do Limiter (geralmente usado como último efeito da cadeia)."""

    ceiling_db: float = -0.3     # dB — nível máximo de saída (true peak)
    release_ms: float = 50.0     # ms
    lookahead_ms: float = 5.0    # ms
    input_gain_db: float = 0.0   # dB — ganho de entrada antes de limitar

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LimiterParams":
        valid = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**valid)


DEFAULT = LimiterParams()

PRESETS: Dict[str, LimiterParams] = {
    "Transparente": LimiterParams(ceiling_db=-0.3, release_ms=80.0, lookahead_ms=5.0),
    "Loudness":     LimiterParams(ceiling_db=-0.1, release_ms=30.0, lookahead_ms=3.0, input_gain_db=3.0),
    "Master Seguro": LimiterParams(ceiling_db=-1.0, release_ms=100.0, lookahead_ms=8.0),
}