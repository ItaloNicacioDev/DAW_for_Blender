"""transport/utils.py

Funções utilitárias compartilhadas por todo o módulo de transporte:
acesso ao PropertyGroup, conversões frame <-> segundos <-> batida, e
redraw da UI.
"""

import bpy


def get_transport(context=None):
    """Retorna o DAW_TransportProperties da cena atual."""
    context = context or bpy.context
    return context.scene.daw_transport


def get_fps(context=None):
    context = context or bpy.context
    render = context.scene.render
    return render.fps / render.fps_base


def frame_to_seconds(context, frame):
    return frame / get_fps(context)


def seconds_to_frame(context, seconds):
    return round(seconds * get_fps(context))


def frame_to_beat(context, frame):
    """Converte um frame da timeline em número de batida, usando o BPM atual."""
    transport = get_transport(context)
    seconds = frame_to_seconds(context, frame)
    return seconds * (transport.bpm / 60.0)


def beat_to_frame(context, beat):
    """Converte um número de batida em frame da timeline, usando o BPM atual."""
    transport = get_transport(context)
    seconds = beat * (60.0 / transport.bpm)
    return seconds_to_frame(context, seconds)


def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def redraw_ui(context=None):
    """Força o redraw de todas as áreas para refletir mudanças de estado
    imediatamente (útil pois handlers rodam fora do ciclo normal de UI)."""
    context = context or bpy.context
    wm = getattr(context, "window_manager", None) or bpy.context.window_manager
    for window in wm.windows:
        for area in window.screen.areas:
            area.tag_redraw()