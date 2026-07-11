# modules/metronome/register.py
"""
Registro e desregistro do módulo Metrônomo no Blender.
Chamado por daw/__init__.py (ou pelo módulo pai) no register()/unregister().
"""
from __future__ import annotations

import bpy

from .properties import MetronomeProperties
from .operators import classes as operator_classes
from .ui import classes as ui_classes


_all_classes = [
    MetronomeProperties,
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

    bpy.types.Scene.daw_metronome = bpy.props.PointerProperty(
        type=MetronomeProperties
    )
    print("[DAW] Módulo metronome registrado")


def unregister():
    if hasattr(bpy.types.Scene, "daw_metronome"):
        del bpy.types.Scene.daw_metronome

    for cls in reversed(_all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[DAW] Módulo metronome desregistrado")