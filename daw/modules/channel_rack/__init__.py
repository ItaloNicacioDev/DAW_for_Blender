# modules/channel_rack/__init__.py
"""
Módulo Channel Rack da DAW.

Responsabilidade:
    Gerenciar os canais (instrumentos/samples/áudio) organizados em um
    step sequencer, com mute/solo, cor, agrupamento e patterns de steps —
    o equivalente ao "Channel Rack" de DAWs baseadas em step sequencer.

Arquitetura:
    colors.py       — paleta de cores e conversão HEX/RGB
    icons.py        — mapeamento de ícones do Blender por tipo/estado
    channels.py      — Channel: modelo puro de um canal (sem bpy)
    groups.py        — ChannelGroup: agrupamento de canais (sem bpy)
    rack.py           — ChannelRack: contêiner central de canais/grupos (sem bpy)
    utils.py          — helpers + ponte entre o modelo puro e o RNA do Blender
    properties.py     — PropertyGroups do Blender (estado real da UI)
    operators.py       — Operators do Blender (ações de edição)
    ui.py             — Painéis do Blender
    register.py        — register() / unregister()

Uso no Scheduler (reprodução), a partir do modelo puro:
    from daw.modules.channel_rack import ChannelRack

    rack = ChannelRack()
    kick = rack.add_channel("Kick", instrument_type="DRUM")
    kick.set_step(0, True)

    for ch in rack.channels_at_step(rack.current_step):
        play(ch)

Uso a partir da cena do Blender (RNA), dentro de um Operator/Panel:
    rack_props = context.scene.daw_channel_rack
    for channel in rack_props.channels:
        ...
"""
from __future__ import annotations

from .colors import (
    get_color_by_index,
    hex_to_rgb,
    rgb_to_hex,
    lighten,
    darken,
    DEFAULT_PALETTE,
)
from .icons import (
    icon_for_instrument,
    icon_for_mute,
    icon_for_solo,
    icon_for_step,
)
from .channels import Channel, INSTRUMENT_TYPES, MAX_STEPS, DEFAULT_STEP_COUNT
from .groups import (
    ChannelGroup,
    channels_in_group,
    ungrouped_channels,
    apply_group_mute,
    remove_group,
)
from .rack import ChannelRack
from .utils import (
    unique_channel_name,
    clamp_index,
    channel_props_to_model,
    apply_model_to_channel_props,
    any_solo_active,
    is_channel_audible,
)
from .register import register, unregister

__all__ = [
    # Cores / ícones
    "get_color_by_index", "hex_to_rgb", "rgb_to_hex", "lighten", "darken",
    "DEFAULT_PALETTE",
    "icon_for_instrument", "icon_for_mute", "icon_for_solo", "icon_for_step",
    # Modelo puro
    "Channel", "INSTRUMENT_TYPES", "MAX_STEPS", "DEFAULT_STEP_COUNT",
    "ChannelGroup", "channels_in_group", "ungrouped_channels",
    "apply_group_mute", "remove_group",
    "ChannelRack",
    # Utils / ponte RNA
    "unique_channel_name", "clamp_index",
    "channel_props_to_model", "apply_model_to_channel_props",
    "any_solo_active", "is_channel_audible",
    # Blender
    "register", "unregister",
]