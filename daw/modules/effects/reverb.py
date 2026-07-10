# modules/effects/reverb.py
"""
Modelo de parâmetros do efeito Reverb (sem dependência de bpy).
Processamento real de áudio acontece no motor C++ — ver chorus.py para
a nota completa sobre a arquitetura.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

EFFECT_TYPE = "REVERB"


@dataclass
class ReverbParams:
    """Parâmetros do Reverb."""

    room_size: float = 0.5     # 0.0 (pequeno) - 1.0 (catedral)
    damping: float = 0.5       # 0.0 (brilhante) - 1.0 (abafado)
    width: float = 1.0         # 0.0 (mono) - 1.0 (estéreo largo)
    pre_delay_ms: float = 20.0 # ms — atraso antes do início da reverberação
    mix: float = 0.3           # 0.0 (seco) - 1.0 (100% processado)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReverbParams":
        valid = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**valid)


DEFAULT = ReverbParams()

PRESETS: Dict[str, ReverbParams] = {
    "Sala Pequena": ReverbParams(room_size=0.25, damping=0.4, pre_delay_ms=10.0, mix=0.2),
    "Hall":         ReverbParams(room_size=0.6, damping=0.5, pre_delay_ms=25.0, mix=0.35),
    "Catedral":     ReverbParams(room_size=0.9, damping=0.3, pre_delay_ms=40.0, mix=0.5),
    "Plate":        ReverbParams(room_size=0.45, damping=0.6, width=0.8, pre_delay_ms=5.0, mix=0.3),
}