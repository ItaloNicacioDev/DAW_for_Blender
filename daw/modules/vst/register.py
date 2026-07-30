# modules/vst/register.py
"""
Registro e desregistro do módulo VST no Blender.
Chamado por daw/__init__.py no register()/unregister() geral do addon.
"""
from __future__ import annotations

import bpy

from .properties import register as _properties_register, unregister as _properties_unregister
from .operators import classes as _operator_classes
from .ui import classes as _ui_classes


def register():
    # properties.py já cuida do próprio register/unregister (classes +
    # bpy.types.Scene.daw_vst*), então só registramos operators/ui aqui.
    _properties_register()

    for cls in _operator_classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)

    for cls in _ui_classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)

    print("[DAW] Módulo vst registrado")


def unregister():
    for cls in reversed(_ui_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    for cls in reversed(_operator_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    _properties_unregister()

    print("[DAW] Módulo vst desregistrado")