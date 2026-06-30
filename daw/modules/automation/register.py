# modules/automation/register.py
"""
Registro e desregistro do módulo de automação no Blender.
Chamado por daw/__init__.py (ou pelo módulo pai) no register()/unregister().
"""
from __future__ import annotations

import bpy

from .properties import (
    AutomationPointProperties,
    AutomationCurveProperties,
    AutomationProperties,
)
from .operators import classes as operator_classes
from .ui import classes as ui_classes


_all_classes = [
    AutomationPointProperties,
    AutomationCurveProperties,
    AutomationProperties,
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

    bpy.types.Scene.daw_automation = bpy.props.PointerProperty(
        type=AutomationProperties
    )
    print("[DAW] Módulo automation registrado")


def unregister():
    if hasattr(bpy.types.Scene, "daw_automation"):
        del bpy.types.Scene.daw_automation

    for cls in reversed(_all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[DAW] Módulo automation desregistrado")