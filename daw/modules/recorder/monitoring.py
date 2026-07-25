# modules/recorder/monitoring.py
"""
Monitoramento de níveis de áudio (VU / Peak).
"""
from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from .input import get_input_manager


class MonitorState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.is_monitoring = False


def get_monitor_state() -> MonitorState:
    return MonitorState()


@persistent
def monitor_frame_handler(scene):
    """Atualiza níveis de monitoramento a cada frame."""
    settings = scene.daw_recorder_settings
    mgr = get_input_manager()

    if settings.monitor_input or settings.is_recording:
        peak, rms = mgr.get_levels()
        settings.current_peak = peak
        settings.current_rms = rms
    else:
        settings.current_peak *= 0.9
        settings.current_rms *= 0.9


def start_monitoring():
    state = get_monitor_state()
    if not state.is_monitoring:
        if monitor_frame_handler not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(monitor_frame_handler)
        state.is_monitoring = True


def stop_monitoring():
    state = get_monitor_state()
    if state.is_monitoring:
        if monitor_frame_handler in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.remove(monitor_frame_handler)
        state.is_monitoring = False


classes = []


def register():
    pass


def unregister():
    stop_monitoring()
    get_input_manager().stop()