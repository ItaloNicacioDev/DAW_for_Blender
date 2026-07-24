# modules/mixer/routing.py
"""
Buses e roteamento de saída do Mixer — sem dependência de bpy.

Responsabilidade:
    Gerenciar os buses de saída disponíveis (Master + buses auxiliares
    criados pelo usuário) e o roteamento de cada faixa para um desses
    buses. Buses auxiliares recebem tanto sinal roteado diretamente
    (output_bus da faixa) quanto sinal de sends (ver sends.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .tracks import MASTER_TRACK_NAME


@dataclass
class MixerBus:
    """Um bus de saída (Master ou auxiliar)."""

    name: str = "Bus"
    volume: float = 0.8       # 0.0 - 1.0 linear
    mute: bool = False
    is_master: bool = False

    peak_left: float = 0.0
    peak_right: float = 0.0


def create_master_bus() -> MixerBus:
    return MixerBus(name=MASTER_TRACK_NAME, volume=0.8, is_master=True)


def add_bus(buses: List[MixerBus], name: str, volume: float = 0.8) -> Optional[MixerBus]:
    """Cria um novo bus auxiliar com nome único."""
    if any(b.name == name for b in buses):
        return None
    bus = MixerBus(name=name, volume=volume, is_master=False)
    buses.append(bus)
    return bus


def remove_bus(buses: List[MixerBus], index: int, tracks: Optional[list] = None) -> bool:
    """
    Remove um bus auxiliar pelo índice (o Master, index 0, nunca é removido).
    Se `tracks` for informado, reatribui faixas roteadas para este bus ao Master
    e remove sends apontando para ele.
    """
    if not (0 <= index < len(buses)) or buses[index].is_master:
        return False

    removed_name = buses[index].name
    del buses[index]

    if tracks:
        from .sends import remove_sends_to_bus
        for track in tracks:
            if track.output_bus == removed_name:
                track.output_bus = MASTER_TRACK_NAME
            remove_sends_to_bus(track.sends, removed_name)

    return True


def get_bus_by_name(buses: List[MixerBus], name: str) -> Optional[MixerBus]:
    for b in buses:
        if b.name == name:
            return b
    return None


def bus_names(buses: List[MixerBus]) -> List[str]:
    return [b.name for b in buses]


def set_track_output(track, buses: List[MixerBus], bus_name: str) -> bool:
    """Roteia a saída de uma faixa para um bus existente pelo nome."""
    if get_bus_by_name(buses, bus_name) is None:
        return False
    track.output_bus = bus_name
    return True


def tracks_routed_to(tracks: list, bus_name: str) -> list:
    """Retorna as faixas cuja saída direta está roteada para o bus informado."""
    return [t for t in tracks if t.output_bus == bus_name]