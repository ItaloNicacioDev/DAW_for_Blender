# modules/instruments/register.py
"""
Registro e desregistro do módulo Instrumentos no Blender.
Chamado por daw/__init__.py (ou pelo módulo pai) no register()/unregister().
"""
from __future__ import annotations

import bpy

from .properties import InstrumentProperties, InstrumentsRackProperties
from .operators import classes as operator_classes
from .ui import classes as ui_classes


_all_classes = [
    InstrumentProperties,
    InstrumentsRackProperties,
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

    bpy.types.Scene.daw_instruments = bpy.props.PointerProperty(
        type=InstrumentsRackProperties
    )
    print("[DAW] Módulo instruments registrado")


def unregister():
    if hasattr(bpy.types.Scene, "daw_instruments"):
        del bpy.types.Scene.daw_instruments

    for cls in reversed(_all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[DAW] Módulo instruments desregistrado")