# modules/effects/distortion.py
"""
Modelo de parâmetros do efeito Distortion (sem dependência de bpy).
Processamento real de áudio acontece no motor C++ — ver chorus.py para
a nota completa sobre a arquitetura.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

EFFECT_TYPE = "DISTORTION"

DISTORTION_MODES = ("SOFT", "HARD", "FUZZ", "BITCRUSH")


@dataclass
class DistortionParams:
    """Parâmetros da Distorção."""

    drive: float = 0.4        # 0.0 - 1.0 — quantidade de saturação
    tone: float = 0.5         # 0.0 (escuro) - 1.0 (brilhante)
    mode: str = "SOFT"        # ver DISTORTION_MODES
    output_gain_db: float = 0.0
    mix: float = 1.0          # 0.0 (seco) - 1.0 (100% processado)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DistortionParams":
        valid = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**valid)


DEFAULT = DistortionParams()

PRESETS: Dict[str, DistortionParams] = {
    "Overdrive Suave": DistortionParams(drive=0.25, tone=0.55, mode="SOFT"),
    "Distorção Pesada": DistortionParams(drive=0.75, tone=0.45, mode="HARD"),
    "Fuzz Vintage":    DistortionParams(drive=0.85, tone=0.35, mode="FUZZ"),
    "Lo-Fi Bitcrush":  DistortionParams(drive=0.5, tone=0.3, mode="BITCRUSH", mix=0.8),
}