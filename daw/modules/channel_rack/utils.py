# modules/channel_rack/utils.py
"""
Utilitários do Channel Rack.

Responsabilidade:
    Funções auxiliares usadas pelos operadores e pela UI: nomes únicos,
    clamp de índices e sincronização entre o modelo puro (channels.py)
    e as propriedades RNA do Blender (properties.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .channels import Channel

if TYPE_CHECKING:
    from .properties import ChannelProperties, ChannelRackProperties


def unique_channel_name(rack_props: "ChannelRackProperties", base_name: str) -> str:
    """
    Garante que `base_name` seja único dentro da coleção de canais.
    Se já existir, acrescenta ' (2)', ' (3)', etc.
    """
    existing = {c.name for c in rack_props.channels}
    if base_name not in existing:
        return base_name

    n = 2
    while f"{base_name} ({n})" in existing:
        n += 1
    return f"{base_name} ({n})"


def clamp_index(index: int, length: int) -> int:
    """Restringe um índice ao range válido [0, length-1]. Retorna 0 se length <= 0."""
    if length <= 0:
        return 0
    return max(0, min(index, length - 1))


def channel_props_to_model(props: "ChannelProperties") -> Channel:
    """Converte um ChannelProperties (RNA) no modelo puro Channel (para lógica/áudio)."""
    return Channel(
        name=props.name,
        instrument_type=props.instrument_type,
        sample_path=props.sample_path,
        color=tuple(props.color),
        volume=props.volume,
        pan=props.pan,
        mute=props.mute,
        solo=props.solo,
        locked=props.locked,
        group_index=props.group_index,
        steps=list(props.steps),
        step_count=props.step_count,
    )


def apply_model_to_channel_props(channel: Channel, props: "ChannelProperties") -> None:
    """Copia os valores do modelo puro Channel de volta para o ChannelProperties (RNA)."""
    props.name = channel.name
    props.instrument_type = channel.instrument_type
    props.sample_path = channel.sample_path
    props.color = channel.color
    props.volume = channel.volume
    props.pan = channel.pan
    props.mute = channel.mute
    props.solo = channel.solo
    props.locked = channel.locked
    props.group_index = channel.group_index
    props.step_count = channel.step_count
    for i, value in enumerate(channel.steps):
        if i < len(props.steps):
            props.steps[i] = value


def any_solo_active(rack_props: "ChannelRackProperties") -> bool:
    """Verifica se algum canal está em modo solo (RNA)."""
    return any(c.solo for c in rack_props.channels)


def is_channel_audible(props: "ChannelProperties", solo_active: bool) -> bool:
    """Mesma regra de audibilidade do modelo puro, aplicada a um ChannelProperties (RNA)."""
    if props.mute:
        return False
    if solo_active and not props.solo:
        return False
    return True