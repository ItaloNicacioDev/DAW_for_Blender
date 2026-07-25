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
    register,
)

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
    "register",
]


def register():
    register.register()


def unregister():
    register.unregister()