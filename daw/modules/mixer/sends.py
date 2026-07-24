# modules/mixer/sends.py
"""
Sends (envios auxiliares) de uma faixa do mixer para um bus — sem bpy.

Responsabilidade:
    Representar o envio de uma parcela do sinal de uma faixa para um bus
    auxiliar (ex: um bus de reverb compartilhado por várias faixas),
    mantendo o nível de envio e se o envio é pré ou pós-fader.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

MAX_SENDS_PER_TRACK = 4


@dataclass
class Send:
    """Um envio auxiliar de uma faixa para um bus."""

    bus_name: str = ""
    level: float = 0.0        # 0.0 - 1.0 linear (subtype FACTOR na UI)
    pre_fader: bool = False   # False = pós-fader (padrão), True = pré-fader
    enabled: bool = True

    def set_level(self, level: float) -> None:
        self.level = max(0.0, min(1.0, level))

    def toggle_pre_fader(self) -> bool:
        self.pre_fader = not self.pre_fader
        return self.pre_fader


def can_add_send(sends: List[Send]) -> bool:
    return len(sends) < MAX_SENDS_PER_TRACK


def add_send(sends: List[Send], bus_name: str, level: float = 0.0) -> Optional[Send]:
    if not can_add_send(sends):
        return None
    if any(s.bus_name == bus_name for s in sends):
        return None  # já existe um envio para este bus
    send = Send(bus_name=bus_name, level=level)
    sends.append(send)
    return send


def remove_send(sends: List[Send], index: int) -> bool:
    if not (0 <= index < len(sends)):
        return False
    del sends[index]
    return True


def get_send_by_bus(sends: List[Send], bus_name: str) -> Optional[Send]:
    for s in sends:
        if s.bus_name == bus_name:
            return s
    return None


def set_send_level(sends: List[Send], index: int, level: float) -> bool:
    if not (0 <= index < len(sends)):
        return False
    sends[index].set_level(level)
    return True


def remove_sends_to_bus(sends: List[Send], bus_name: str) -> None:
    """Remove todos os envios apontando para um bus (usado ao remover o bus)."""
    sends[:] = [s for s in sends if s.bus_name != bus_name]