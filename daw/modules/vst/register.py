# modules/vst/register.py
"""
Registro e desregistro do módulo VST no Blender.

Mudanças em relação à versão anterior:
    - Registra os novos operadores e classes de UI adicionados (scroll,
      instalação do sounddevice, monitor ao vivo).
    - Adiciona handler de depsgraph para desligar o monitor ao vivo
      quando o Blender fecha (evita thread órfã).
    - Auto-scan no startup (opcional, configurável em DawVstSettings).
"""
from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from .properties import register as _properties_register, unregister as _properties_unregister
from .operators import classes as _operator_classes
from .ui import classes as _ui_classes


# ---------------------------------------------------------------------- #
# Handler: desligar monitor ao vivo ao fechar o Blender
# ---------------------------------------------------------------------- #
@persistent
def _on_load_pre(filepath):
    """Para o monitor ao vivo antes de carregar um novo arquivo."""
    try:
        from .live_monitor import get_live_monitor
        monitor = get_live_monitor()
        if monitor.is_running:
            monitor.stop()
            # Atualizar o RNA se a cena ainda existir
            scene = bpy.context.scene if bpy.context and bpy.context.scene else None
            if scene and hasattr(scene, "daw_vst"):
                scene.daw_vst.is_live_monitoring = False
    except Exception:
        pass


# ---------------------------------------------------------------------- #
# Auto-scan no startup
# ---------------------------------------------------------------------- #
@persistent
def _on_depsgraph_update_post(scene, depsgraph):
    """
    Dispara o auto-scan uma única vez no startup, se configurado.
    Remove a si mesmo após o primeiro disparo (one-shot).
    """
    try:
        settings = scene.daw_vst
        if settings.auto_scan_on_startup and settings.vst_directories.strip():
            bpy.ops.daw.scan_vst_directories_async()
    except Exception:
        pass
    finally:
        # Remove este handler — só executa uma vez ao iniciar
        if _on_depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update_post)


# ---------------------------------------------------------------------- #
# register / unregister
# ---------------------------------------------------------------------- #
def register():
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

    # Handlers
    if _on_load_pre not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(_on_load_pre)

    # Auto-scan one-shot: registra só se houver diretórios configurados
    # (evita disparo inútil em instalações limpas)
    if _on_depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update_post)

    print("[DAW] Módulo vst registrado")


def unregister():
    # Para o monitor ao vivo antes de desregistrar
    try:
        from .live_monitor import get_live_monitor
        get_live_monitor().stop()
    except Exception:
        pass

    # Remove handlers
    if _on_load_pre in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_on_load_pre)
    if _on_depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update_post)

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