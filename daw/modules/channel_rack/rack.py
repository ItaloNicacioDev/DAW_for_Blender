# modules/channel_rack/rack.py
"""
ChannelRack — modelo central (sem dependência de bpy).

Responsabilidade:
    Gerenciar a coleção de canais e grupos, e resolver quais canais devem
    soar em cada step (respeitando mute/solo). É o "core" usado tanto pela
    UI (via properties.py, que espelha estes dados em RNA) quanto pelo
    scheduler de reprodução (ver core/engine.py / core/timeline.py).

Uso típico no scheduler:
    from daw.modules.channel_rack import ChannelRack

    rack = ChannelRack()
    rack.add_channel("Kick", instrument_type="DRUM")
    rack.channels[0].set_step(0, True)
    rack.channels[0].set_step(4, True)

    for step in range(rack.step_count):
        for ch in rack.channels_at_step(step):
            play(ch)  # dispara a nota/sample do canal
"""
from __future__ import annotations

from typing import List, Optional

from .channels import Channel, DEFAULT_STEP_COUNT, MAX_STEPS
from .colors import get_color_by_index
from .groups import ChannelGroup


class ChannelRack:
    """Contêiner de canais e grupos do Channel Rack."""

    def __init__(self, step_count: int = DEFAULT_STEP_COUNT) -> None:
        self.channels: List[Channel] = []
        self.groups: List[ChannelGroup] = []
        self.step_count: int = step_count
        self.current_step: int = 0
        self.active_channel_index: int = 0

    # ------------------------------------------------------------------ #
    # Canais
    # ------------------------------------------------------------------ #
    def add_channel(
        self,
        name: str = "Novo Canal",
        instrument_type: str = "SAMPLER",
        sample_path: str = "",
    ) -> Channel:
        channel = Channel(
            name=name,
            instrument_type=instrument_type,
            sample_path=sample_path,
            color=get_color_by_index(len(self.channels)),
            step_count=self.step_count,
        )
        self.channels.append(channel)
        self.active_channel_index = len(self.channels) - 1
        return channel

    def remove_channel(self, index: int) -> bool:
        if not (0 <= index < len(self.channels)):
            return False
        del self.channels[index]
        self.active_channel_index = max(0, min(self.active_channel_index, len(self.channels) - 1))
        return True

    def duplicate_channel(self, index: int) -> Optional[Channel]:
        if not (0 <= index < len(self.channels)):
            return None
        new_channel = self.channels[index].duplicate()
        self.channels.insert(index + 1, new_channel)
        self.active_channel_index = index + 1
        return new_channel

    def move_channel(self, index: int, direction: int) -> bool:
        """Move um canal para cima (direction=-1) ou para baixo (direction=1)."""
        target = index + direction
        if not (0 <= index < len(self.channels)) or not (0 <= target < len(self.channels)):
            return False
        self.channels[index], self.channels[target] = self.channels[target], self.channels[index]
        self.active_channel_index = target
        return True

    def get_active_channel(self) -> Optional[Channel]:
        if 0 <= self.active_channel_index < len(self.channels):
            return self.channels[self.active_channel_index]
        return None

    # ------------------------------------------------------------------ #
    # Reprodução / steps
    # ------------------------------------------------------------------ #
    def any_solo_active(self) -> bool:
        return any(c.solo for c in self.channels)

    def channels_at_step(self, step: int) -> List[Channel]:
        """Retorna os canais audíveis (não mutados / respeitando solo) que disparam neste step."""
        solo_active = self.any_solo_active()
        result = []
        for c in self.channels:
            if not c.is_audible(solo_active):
                continue
            if 0 <= step < len(c.steps) and c.steps[step]:
                result.append(c)
        return result

    def advance_step(self) -> int:
        """Avança o step atual (wrap-around) e o retorna. Chamado pelo clock/scheduler."""
        self.current_step = (self.current_step + 1) % max(1, self.step_count)
        return self.current_step

    def reset_playback(self) -> None:
        self.current_step = 0

    def set_step_count(self, count: int) -> None:
        """Altera a quantidade de steps ativos do rack (compartilhada por todos os canais)."""
        count = max(1, min(count, MAX_STEPS))
        self.step_count = count
        for c in self.channels:
            c.step_count = count

    # ------------------------------------------------------------------ #
    # Grupos
    # ------------------------------------------------------------------ #
    def add_group(self, name: str = "Novo Grupo") -> ChannelGroup:
        group = ChannelGroup(name=name, color=get_color_by_index(len(self.groups)))
        self.groups.append(group)
        return group

    def clear(self) -> None:
        """Remove todos os canais e grupos (ex: ao criar um novo projeto)."""
        self.channels.clear()
        self.groups.clear()
        self.current_step = 0
        self.active_channel_index = 0