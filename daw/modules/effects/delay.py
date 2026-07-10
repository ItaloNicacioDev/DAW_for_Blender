# modules/effects/delay.py
"""
Modelo de parâmetros do efeito Delay (sem dependência de bpy).
Processamento real de áudio acontece no motor C++ — ver chorus.py para
a nota completa sobre a arquitetura.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

EFFECT_TYPE = "DELAY"

# Divisões de tempo disponíveis quando sync=True (fração do compasso)
SYNC_DIVISIONS = ("1/1", "1/2", "1/4", "1/8", "1/16", "1/4T", "1/8T", "1/16T")


@dataclass
class DelayParams:
    """Parâmetros do Delay."""

    time_ms: float = 350.0        # ms — usado quando sync=False
    sync: bool = False            # se True, usa sync_division + BPM do projeto
    sync_division: str = "1/4"
    feedback: float = 0.35        # 0.0 - 0.95
    ping_pong: bool = False       # alterna repetições entre L/R
    mix: float = 0.35             # 0.0 (seco) - 1.0 (100% processado)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DelayParams":
        valid = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**valid)


DEFAULT = DelayParams()

PRESETS: Dict[str, DelayParams] = {
    "Slapback":   DelayParams(time_ms=90.0, feedback=0.05, mix=0.25),
    "Eco Clássico": DelayParams(time_ms=350.0, feedback=0.35, mix=0.35),
    "Ping Pong Sync": DelayParams(sync=True, sync_division="1/8", feedback=0.45, ping_pong=True, mix=0.4),
}


def sync_division_to_beats(division: str) -> float:
    """Converte uma divisão de sync (ex: '1/8T') em fração de semínima (beat)."""
    table = {
        "1/1": 4.0, "1/2": 2.0, "1/4": 1.0, "1/8": 0.5, "1/16": 0.25,
        "1/4T": 1.0 * (2 / 3), "1/8T": 0.5 * (2 / 3), "1/16T": 0.25 * (2 / 3),
    }
    return table.get(division, 1.0)