# modules/automation/register.py
"""
Registro e desregistro do módulo de automação no Blender.
Chamado por daw/__init__.py (ou pelo módulo pai) no register()/unregister().
"""
from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from . import runtime, store
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


@persistent
def _on_frame_change(scene, depsgraph=None):
    """Aplica a automação no frame atual (reprodução e scrub)."""
    try:
        runtime.apply_at_current_frame(scene)
    except Exception as exc:
        print(f"[DAW][automation] Falha ao aplicar automação: {exc}")


@persistent
def _on_load_post(_dummy=None):
    """Outro .blend foi aberto: descarta o cache (ele recarrega da cena sob demanda)."""
    store.clear_cache()


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

    if _on_frame_change not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(_on_frame_change)
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)
    print("[DAW] Módulo automation registrado")


def unregister():
    if _on_frame_change in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(_on_frame_change)
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    store.clear_cache()

    if hasattr(bpy.types.Scene, "daw_automation"):
        del bpy.types.Scene.daw_automation

    for cls in reversed(_all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[DAW] Módulo automation desregistrado")