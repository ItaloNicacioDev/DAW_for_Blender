# modules/effects/register.py
"""
Registro e desregistro do módulo Efeitos no Blender.
Chamado por daw/__init__.py (ou pelo módulo pai) no register()/unregister().
"""
from __future__ import annotations

import bpy

from .properties import _ALL_CLASSES as property_classes, EffectsRackProperties
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

    bpy.types.Scene.daw_effects = bpy.props.PointerProperty(
        type=EffectsRackProperties
    )
    print("[DAW] Módulo effects registrado")


def unregister():
    if hasattr(bpy.types.Scene, "daw_effects"):
        del bpy.types.Scene.daw_effects

    for cls in reversed(_all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[DAW] Módulo effects desregistrado")