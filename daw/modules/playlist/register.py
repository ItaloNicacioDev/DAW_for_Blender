# modules/playlist/register.py
"""
Registro e desregistro do módulo Playlist no Blender.
Chamado por daw/__init__.py no register()/unregister().
"""
from __future__ import annotations

import bpy

from .properties import _ALL_CLASSES as property_classes, PlaylistProperties
from .operators import classes as operator_classes
from .ui import classes as ui_classes


_all_classes = [
    *property_classes,
    *operator_classes,
    *ui_classes,
]


def register():
    for cls in _all_classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)

    bpy.types.Scene.daw_playlist = bpy.props.PointerProperty(type=PlaylistProperties)

    print("[DAW] Módulo playlist registrado")


def unregister():
    if hasattr(bpy.types.Scene, "daw_playlist"):
        del bpy.types.Scene.daw_playlist

    for cls in reversed(_all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    print("[DAW] Módulo playlist desregistrado")