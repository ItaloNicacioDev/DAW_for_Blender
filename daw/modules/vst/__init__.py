# modules/effects/__init__.py
"""
Módulo de Efeitos da DAW.

Responsabilidade:
    Gerenciar, por canal, uma cadeia ordenada de efeitos de inserção
    (chorus, compressor, delay, distortion, EQ, flanger, limiter, phaser,
    reverb), com bypass, presets embutidos e presets salvos pelo usuário.

Arquitetura:
    chorus.py, compressor.py, delay.py, distortion.py, eq.py,
    flanger.py, limiter.py, phaser.py, reverb.py
                      — modelo puro de parâmetros de cada efeito (sem bpy),
                        cada um com sua dataclass de parâmetros + PRESETS
    rack.py           — EffectSlot / EffectsChain / EffectsRack (sem bpy)
    presets.py        — combina presets embutidos com presets do usuário (JSON em disco)
    utils.py          — ponte entre o modelo puro e o RNA do Blender
    properties.py     — PropertyGroups do Blender (estado real da UI)
    operators.py      — Operators do Blender (ações de edição)
    ui.py             — Painéis do Blender
    register.py       — register() / unregister()

Uso no motor de áudio (fora do Blender), a partir do modelo puro:
    from daw.modules.effects import EffectsRack

    rack = EffectsRack()
    chain = rack.get_chain(channel_index=0)
    chain.add_effect("COMPRESSOR")
    chain.add_effect("REVERB")

    for slot in chain.active_slots():
        apply_effect(slot.effect_type, slot.params_dict)  # no motor C++

Uso a partir da cena do Blender (RNA), dentro de um Operator/Panel:
    rack_props = context.scene.daw_effects
    chain = get_or_create_chain(rack_props, channel_index=0)
    for slot in chain.slots:
        ...
"""
from __future__ import annotations

from . import chorus, compressor, delay, distortion, eq, flanger, limiter, phaser, reverb
from .rack import (
    EFFECT_TYPES,
    EffectSlot,
    EffectsChain,
    EffectsRack,
    default_params_for,
    presets_for,
)
from .presets import (
    list_all_preset_names,
    get_preset_params,
    resolve_params,
    save_user_preset,
    delete_user_preset,
)
from .utils import (
    clamp_index,
    get_chain,
    get_or_create_chain,
    params_attr_name,
    apply_params_dict_to_slot,
    slot_params_to_dict,
)
from .register import register, unregister

__all__ = [
    # Módulos de efeito individuais
    "chorus", "compressor", "delay", "distortion", "eq",
    "flanger", "limiter", "phaser", "reverb",
    # Modelo puro (rack)
    "EFFECT_TYPES", "EffectSlot", "EffectsChain", "EffectsRack",
    "default_params_for", "presets_for",
    # Presets
    "list_all_preset_names", "get_preset_params", "resolve_params",
    "save_user_preset", "delete_user_preset",
    # Utils / ponte RNA
    "clamp_index", "get_chain", "get_or_create_chain",
    "params_attr_name", "apply_params_dict_to_slot", "slot_params_to_dict",
    # Blender
    "register", "unregister",
]