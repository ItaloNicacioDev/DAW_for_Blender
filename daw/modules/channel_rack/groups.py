# modules/channel_rack/groups.py
"""
Grupos de canais do Channel Rack (sem dependência de bpy).

Responsabilidade:
    Permitir organizar canais em grupos nomeados e coloridos (ex: "Bateria",
    "Baixo", "Leads"), usados para colapsar/filtrar a visualização e para
    mute/solo em lote.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

from .colors import Color, get_color_by_index

if TYPE_CHECKING:
    from .channels import Channel


@dataclass
class ChannelGroup:
    """Um grupo de canais (metadados apenas — a associação vive em Channel.group_index)."""

    name: str = "Novo Grupo"
    color: Color = field(default_factory=lambda: get_color_by_index(0))
    collapsed: bool = False
    muted: bool = False   # mute em lote de todo o grupo


def channels_in_group(channels: List["Channel"], group_index: int) -> List["Channel"]:
    """Retorna todos os canais pertencentes ao grupo `group_index`."""
    return [c for c in channels if c.group_index == group_index]

def ungrouped_channels(channels: List["Channel"]) -> List["Channel"]:
    """Retorna os canais que não pertencem a nenhum grupo (group_index == -1)."""
    return [c for c in channels if c.group_index == -1]


def apply_group_mute(channels: List["Channel"], group_index: int, muted: bool) -> None:
    """Aplica mute/unmute a todos os canais de um grupo de uma vez."""
    for c in channels_in_group(channels, group_index):
        c.mute = muted


def remove_group(groups: List[ChannelGroup], channels: List["Channel"], group_index: int) -> None:
    """
    Remove um grupo da lista e desassocia (group_index = -1) todos os canais
    que pertenciam a ele. Reindexa os group_index dos canais restantes.
    """
    if not (0 <= group_index < len(groups)):
        return

    del groups[group_index]

    for c in channels:
        if c.group_index == group_index:
            c.group_index = -1
        elif c.group_index > group_index:
            c.group_index -= 1