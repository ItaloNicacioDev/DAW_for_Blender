# modules/sampler/register.py
"""
Registro centralizado de todas as classes e módulos do Sampler.
"""
from __future__ import annotations

import bpy
from . import (
    adsr,
    envelopes,
    looping,
    pitch,
    player,
    properties,
    slicing,
    timestretch,
    utils,
    operators,
    ui,
)


def register():
    """Registra todos os módulos do Sampler."""
    # Propriedades (PropertyGroups necessários antes de operadores/UI)
    properties.register()

    # Módulos utilitários (sem classes Blender)
    adsr.register()
    envelopes.register()
    looping.register()
    pitch.register()
    player.register()
    slicing.register()
    timestretch.register()
    utils.register()

    # Operadores e UI
    operators.register()
    ui.register()


def unregister():
    """Desregistra todos os módulos do Sampler."""
    # Ordem reversa: UI/Operadores primeiro
    ui.unregister()
    operators.unregister()

    # Módulos utilitários
    utils.unregister()
    timestretch.unregister()
    slicing.unregister()
    player.unregister()
    pitch.unregister()
    looping.unregister()
    envelopes.unregister()
    adsr.unregister()

    # Propriedades por último
    properties.unregister()