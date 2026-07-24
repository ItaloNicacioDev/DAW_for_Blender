# modules/project/autosave.py
"""
Autosave automático de projetos da DAW.

Responsabilidade:
    Manter um timer periódico que salva automaticamente o estado
    atual do projeto em um arquivo temporário, evitando perda de
    trabalho em caso de crash.
"""
from __future__ import annotations

import bpy

from .backup import create_backup

_AUTOSAVE_INTERVAL = 120.0  # segundos (2 minutos)
_autosave_running = False
_autosave_timer = None


def _autosave_tick() -> Optional[float]:
    """Callback do timer de autosave."""
    scene = bpy.context.scene
    project_name = getattr(scene, "daw_project_name", "autosave")
    filepath = create_backup(scene, project_name, max_backups=5)
    if filepath:
        print(f"[DAW] Autosave: {filepath}")
    return _AUTOSAVE_INTERVAL


def start_autosave() -> None:
    """Inicia o timer de autosave."""
    global _autosave_running
    if _autosave_running:
        return
    if not bpy.app.timers.is_registered(_autosave_tick):
        bpy.app.timers.register(_autosave_tick, first_interval=_AUTOSAVE_INTERVAL, persistent=True)
    _autosave_running = True
    print("[DAW] Autosave iniciado")


def stop_autosave() -> None:
    """Para o timer de autosave."""
    global _autosave_running
    if bpy.app.timers.is_registered(_autosave_tick):
        bpy.app.timers.unregister(_autosave_tick)
    _autosave_running = False
    print("[DAW] Autosave parado")


def register() -> None:
    # Não inicia automaticamente — deixa para o usuário ativar via UI
    pass


def unregister() -> None:
    stop_autosave()