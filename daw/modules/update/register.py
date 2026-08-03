# modules/updater/register.py
"""
Registro e desregistro do módulo Updater no Blender.
Chamado por daw/__init__.py no register()/unregister() geral.
"""
from __future__ import annotations

import bpy

from . import jobs, properties, operators


def register():
    properties.register()
    operators.register()

    # Agenda a checagem automática (respeita a preferência
    # "check_for_updates" e o intervalo mínimo entre checagens —
    # ver jobs.maybe_auto_check_on_startup). Só roda alguns segundos
    # depois do Blender abrir, para não competir com o carregamento
    # inicial do addon.
    bpy.app.timers.register(_startup_check, first_interval=5.0)

    print("[DAW] Módulo updater registrado")


def unregister():
    if bpy.app.timers.is_registered(_startup_check):
        bpy.app.timers.unregister(_startup_check)

    operators.unregister()
    properties.unregister()

    print("[DAW] Módulo updater desregistrado")


def _startup_check():
    try:
        jobs.maybe_auto_check_on_startup()
    except Exception as e:
        print(f"[DAW] Updater: falha na checagem automática: {e}")
    return None