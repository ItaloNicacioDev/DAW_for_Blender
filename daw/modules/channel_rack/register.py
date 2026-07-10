# modules/channel_rack/register.py
"""
Registro e desregistro do módulo Channel Rack no Blender.
Chamado por daw/__init__.py (ou pelo módulo pai) no register()/unregister().
"""
from __future__ import annotations

import bpy

from .properties import (
    ChannelProperties,
    ChannelGroupProperties,
    ChannelRackProperties,
)
from .operators import classes as operator_classes
from .ui import classes as ui_classes


_all_classes = [
    ChannelProperties,
    ChannelGroupProperties,
    ChannelRackProperties,
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

    bpy.types.Scene.daw_channel_rack = bpy.props.PointerProperty(
        type=ChannelRackProperties
    )
    print("[DAW] Módulo channel_rack registrado")


def unregister():
    if hasattr(bpy.types.Scene, "daw_channel_rack"):
        del bpy.types.Scene.daw_channel_rack

    for cls in reversed(_all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[DAW] Módulo channel_rack desregistrado")