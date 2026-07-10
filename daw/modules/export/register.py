# modules/export/register.py
"""
Registro e desregistro do módulo de Exportação no Blender.
Chamado por daw/__init__.py (ou pelo módulo pai) no register()/unregister().
"""
from __future__ import annotations

import bpy

from .properties import ExportProperties
from .operators import classes as operator_classes
from .ui import classes as ui_classes


_all_classes = [
    ExportProperties,
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

    bpy.types.Scene.daw_export = bpy.props.PointerProperty(
        type=ExportProperties
    )
    print("[DAW] Módulo export registrado")


def unregister():
    if hasattr(bpy.types.Scene, "daw_export"):
        del bpy.types.Scene.daw_export

    for cls in reversed(_all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[DAW] Módulo export desregistrado")