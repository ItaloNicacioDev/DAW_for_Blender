# modules/mixer/mixer.py
"""
Mixer — modelo central do módulo (sem dependência de bpy).

Responsabilidade:
    Gerenciar a coleção de faixas (MixerTrack) e buses (MixerBus), resolver
    mute/solo, e fornecer os coeficientes de ganho/pan usados tanto pela UI
    (via properties.py, que espelha estes dados em RNA) quanto pelo motor
    de áudio (ver daw/daw_engine/mixer/mixer.py e daw/core/register.py).

Uso típico fora do Blender (ex: testes, scheduler):
    from daw.modules.mixer import Mixer

    mixer = Mixer()
    kick = mixer.add_track("Kick")
    kick.set_volume(0.9)
    mixer.set_solo(0, True)

    for track in mixer.audible_tracks():
        ...  # enviar para o motor de áudio
"""
from __future__ import annotations

import math
from typing import List, Optional

from .tracks import MixerTrack, MASTER_TRACK_NAME, get_color_by_index
from .routing import MixerBus, create_master_bus, add_bus, remove_bus, get_bus_by_name
from .utils import clamp, linear_pan_gains


class Mixer:
    """Contêiner de faixas e buses do Mixer."""

    def __init__(self) -> None:
        self.tracks: List[MixerTrack] = []
        self.buses: List[MixerBus] = [create_master_bus()]
        self.active_track_index: int = 0
        self.master_volume: float = 0.85

    # ------------------------------------------------------------------ #
    # Faixas
    # ------------------------------------------------------------------ #
    def add_track(self, name: str = "Nova Faixa") -> MixerTrack:
        track = MixerTrack(name=name, color=get_color_by_index(len(self.tracks)))
        self.tracks.append(track)
        self.active_track_index = len(self.tracks) - 1
        return track

    def remove_track(self, index: int) -> bool:
        if not (0 <= index < len(self.tracks)):
            return False
        del self.tracks[index]
        self.active_track_index = max(0, min(self.active_track_index, len(self.tracks) - 1))
        return True

    def duplicate_track(self, index: int) -> Optional[MixerTrack]:
        if not (0 <= index < len(self.tracks)):
            return None
        new_track = self.tracks[index].duplicate()
        self.tracks.insert(index + 1, new_track)
        self.active_track_index = index + 1
        return new_track

    def move_track(self, index: int, direction: int) -> bool:
        target = index + direction
        if not (0 <= index < len(self.tracks)) or not (0 <= target < len(self.tracks)):
            return False
        self.tracks[index], self.tracks[target] = self.tracks[target], self.tracks[index]
        self.active_track_index = target
        return True

    def get_active_track(self) -> Optional[MixerTrack]:
        if 0 <= self.active_track_index < len(self.tracks):
            return self.tracks[self.active_track_index]
        return None

    def get_track_by_name(self, name: str) -> Optional[MixerTrack]:
        for t in self.tracks:
            if t.name == name:
                return t
        return None

    # ------------------------------------------------------------------ #
    # Mute / Solo
    # ------------------------------------------------------------------ #
    def any_solo_active(self) -> bool:
        return any(t.solo for t in self.tracks)

    def audible_tracks(self) -> List[MixerTrack]:
        """Faixas que efetivamente soam, respeitando mute/solo."""
        solo_active = self.any_solo_active()
        return [t for t in self.tracks if t.is_audible(solo_active)]

    def set_mute(self, index: int, mute: bool) -> bool:
        if not (0 <= index < len(self.tracks)):
            return False
        self.tracks[index].mute = mute
        return True

    def set_solo(self, index: int, solo: bool) -> bool:
        if not (0 <= index < len(self.tracks)):
            return False
        self.tracks[index].solo = solo
        return True

    # ------------------------------------------------------------------ #
    # Buses / roteamento
    # ------------------------------------------------------------------ #
    def add_bus(self, name: str, volume: float = 0.8) -> Optional[MixerBus]:
        return add_bus(self.buses, name, volume)

    def remove_bus(self, index: int) -> bool:
        return remove_bus(self.buses, index, tracks=self.tracks)

    def get_master_bus(self) -> MixerBus:
        return self.buses[0]

    def get_bus(self, name: str) -> Optional[MixerBus]:
        return get_bus_by_name(self.buses, name)

    # ------------------------------------------------------------------ #
    # Ganhos resolvidos (usados pelo motor de áudio / meters)
    # ------------------------------------------------------------------ #
    def resolved_gain(self, track: MixerTrack) -> float:
        """Ganho linear efetivo da faixa, considerando mute/solo e volume do bus."""
        if not track.is_audible(self.any_solo_active()):
            return 0.0
        bus = self.get_bus(track.output_bus) or self.get_master_bus()
        bus_gain = 0.0 if bus.mute else bus.volume
        return clamp(track.volume, 0.0, 1.0) * bus_gain

    def resolved_pan_gains(self, track: MixerTrack) -> tuple:
        """Coeficientes (esq, dir) de pan de potência constante para a faixa."""
        return linear_pan_gains(track.pan)

    # ------------------------------------------------------------------ #
    # Utilidades gerais
    # ------------------------------------------------------------------ #
    def clear(self) -> None:
        """Remove todas as faixas e buses auxiliares (ex: novo projeto)."""
        self.tracks.clear()
        self.buses = [create_master_bus()]
        self.active_track_index = 0

    def __repr__(self) -> str:
        return (
            f"Mixer(tracks={len(self.tracks)}, buses={len(self.buses)}, "
            f"master_vol={self.master_volume:.2f})"
        )