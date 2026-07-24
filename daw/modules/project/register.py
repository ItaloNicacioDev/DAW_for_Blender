# modules/project/register.py
"""
Registro e desregistro do módulo Project no Blender.
Chamado por daw/__init__.py no register()/unregister().
"""
from __future__ import annotations

import bpy

from .properties import _ALL_CLASSES as property_classes, ProjectProperties
from .operators import classes as operator_classes
from .ui import classes as ui_classes
from . import autosave


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

    bpy.types.Scene.daw_project = bpy.props.PointerProperty(type=ProjectProperties)
    bpy.types.Scene.daw_project_name = bpy.props.StringProperty(name="Nome do Projeto", default="Untitled")

    autosave.register()

    print("[DAW] Módulo project registrado")


def unregister():
    autosave.unregister()

    if hasattr(bpy.types.Scene, "daw_project_name"):
        del bpy.types.Scene.daw_project_name
    if hasattr(bpy.types.Scene, "daw_project"):
        del bpy.types.Scene.daw_project

    for cls in reversed(_all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    print("[DAW] Módulo project desregistrado")