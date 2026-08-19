"""
timeline/__init__.py
Módulo de timeline do DAW for Blender.
Gerencia clips, tracks, cursor de reprodução, marcadores, zoom e snapping.
"""

from . import (
    properties,
    operators,
    ui,
    cursor,
    markers,
    playback,
    snapping,
    zoom,
    utils,
)
# [FIX] Ver comentário equivalente em modules/settings/__init__.py -- sem
# alias, `from . import register` colidia com `def register()` abaixo e
# quebrava com "AttributeError: 'function' object has no attribute
# 'register'", impedindo o módulo timeline de registrar.
from . import register as register_module

__all__ = [
    "properties",
    "operators",
    "ui",
    "cursor",
    "markers",
    "playback",
    "snapping",
    "zoom",
    "utils",
    "register_module",
]


def register():
    register_module.register()


def unregister():
    register_module.unregister()