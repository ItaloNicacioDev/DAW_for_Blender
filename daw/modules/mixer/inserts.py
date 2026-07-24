# modules/mixer/tracks.py
"""
Modelo de dados de uma faixa (channel strip) do Mixer — sem dependência de bpy.

Responsabilidade:
    Representar uma faixa do mixer (volume, pan, mute/solo, cor, inserts de
    efeito, sends para buses auxiliares e roteamento de saída). Este é o
    "dado real"; o estado editável exposto ao Blender vive em properties.py
    (RNA), que espelha estes campos para desenho da UI.

Arquitetura (ver mixer/__init__.py para o mapa completo do módulo):
    tracks.py   — MixerTrack: modelo puro de uma faixa (este arquivo)
    inserts.py  — InsertSlot: slot de efeito dentro de uma faixa
    sends.py    — Send: envio auxiliar de uma faixa para um bus
    routing.py  — buses/roteamento de saída (Master + auxiliares)
    mixer.py    — Mixer: contêiner central de faixas/buses (sem bpy)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .inserts import InsertSlot
from .sends import Send

MASTER_TRACK_NAME = "Master"

# Paleta padrão (RGB 0-1) usada para colorir faixas automaticamente por índice.
DEFAULT_PALETTE = [
    (0.90, 0.30, 0.30),   # vermelho
    (0.95, 0.55, 0.20),   # laranja
    (0.95, 0.80, 0.25),   # amarelo
    (0.55, 0.85, 0.35),   # verde-limão
    (0.25, 0.75, 0.45),   # verde
    (0.25, 0.75, 0.75),   # ciano
    (0.30, 0.55, 0.95),   # azul
    (0.45, 0.35, 0.90),   # roxo-azulado
    (0.70, 0.35, 0.90),   # roxo
    (0.90, 0.35, 0.70),   # magenta
]


def get_color_by_index(index: int):
    if not DEFAULT_PALETTE:
        return (0.6, 0.6, 0.6)
    return DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)]


@dataclass
class MixerTrack:
    """Uma faixa individual do mixer (channel strip)."""

    name: str = "Nova Faixa"
    color: tuple = field(default_factory=lambda: get_color_by_index(0))

    volume: float = 0.78          # 0.0 - 1.0 linear (subtype FACTOR na UI)
    pan: float = 0.0              # -1.0 (esquerda) .. 1.0 (direita)
    mute: bool = False
    solo: bool = False

    output_bus: str = MASTER_TRACK_NAME   # nome do bus de destino

    inserts: List[InsertSlot] = field(default_factory=list)
    sends: List[Send] = field(default_factory=list)

    # Metragem (últimos valores conhecidos, atualizados por meters.py)
    peak_left: float = 0.0
    peak_right: float = 0.0

    # ------------------------------------------------------------------
    # Inserts
    # ------------------------------------------------------------------
    def add_insert(self, effect_type: str) -> InsertSlot:
        slot = InsertSlot(effect_type=effect_type)
        self.inserts.append(slot)
        return slot

    def remove_insert(self, index: int) -> bool:
        if not (0 <= index < len(self.inserts)):
            return False
        del self.inserts[index]
        return True

    def move_insert(self, index: int, direction: int) -> bool:
        target = index + direction
        if not (0 <= index < len(self.inserts)) or not (0 <= target < len(self.inserts)):
            return False
        self.inserts[index], self.inserts[target] = self.inserts[target], self.inserts[index]
        return True

    # ------------------------------------------------------------------
    # Sends
    # ------------------------------------------------------------------
    def add_send(self, bus_name: str, level: float = 0.0) -> Send:
        send = Send(bus_name=bus_name, level=level)
        self.sends.append(send)
        return send

    def remove_send(self, index: int) -> bool:
        if not (0 <= index < len(self.sends)):
            return False
        del self.sends[index]
        return True

    def get_send(self, bus_name: str):
        for send in self.sends:
            if send.bus_name == bus_name:
                return send
        return None

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    def is_audible(self, any_solo_active: bool) -> bool:
        """Uma faixa soa se não estiver mutada, e (nenhuma em solo) ou (esta em solo)."""
        if self.mute:
            return False
        if any_solo_active and not self.solo:
            return False
        return True

    def duplicate(self, new_name: str = None) -> "MixerTrack":
        return MixerTrack(
            name=new_name or f"{self.name} (cópia)",
            color=self.color,
            volume=self.volume,
            pan=self.pan,
            mute=self.mute,
            solo=False,
            output_bus=self.output_bus,
            inserts=[InsertSlot(**vars(i)) for i in self.inserts],
            sends=[Send(**vars(s)) for s in self.sends],
        )