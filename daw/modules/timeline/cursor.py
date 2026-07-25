"""
timeline/cursor.py
Gerencia o cursor/playhead da timeline:
  - Leitura e escrita da posição em beats
  - Sincronização com o clock/transport da DAW engine
  - Callbacks de atualização de UI
"""

import bpy
from .utils import get_timeline, beat_to_seconds, seconds_to_beat, clamp


# ---------------------------------------------------------------------------
# Acesso à posição
# ---------------------------------------------------------------------------

def get_cursor_beat(context=None) -> float:
    """Retorna a posição atual do cursor em beats."""
    tl = get_timeline(context)
    return tl.cursor_beat


def set_cursor_beat(beat: float, context=None):
    """
    Define a posição do cursor em beats.
    Garante mínimo de 0.0 e sincroniza com a engine de áudio se disponível.
    """
    tl = get_timeline(context)
    tl.cursor_beat = max(0.0, beat)
    _sync_engine_cursor(tl.cursor_beat, context)
    _request_redraw()


def get_cursor_seconds(context=None) -> float:
    """Retorna a posição do cursor em segundos (requer BPM da sessão)."""
    beat = get_cursor_beat(context)
    bpm  = _get_bpm(context)
    return beat_to_seconds(beat, bpm)


def set_cursor_seconds(seconds: float, context=None):
    """Define a posição do cursor a partir de segundos."""
    bpm  = _get_bpm(context)
    beat = seconds_to_beat(seconds, bpm)
    set_cursor_beat(beat, context)


# ---------------------------------------------------------------------------
# Loop region
# ---------------------------------------------------------------------------

def get_loop_region(context=None) -> tuple:
    """Retorna (loop_start_beat, loop_end_beat)."""
    tl = get_timeline(context)
    return tl.loop_start, tl.loop_end


def set_loop_region(start: float, end: float, context=None):
    """Define a região de loop. start < end obrigatório."""
    tl = get_timeline(context)
    start = max(0.0, start)
    end   = max(start + 0.25, end)
    tl.loop_start = start
    tl.loop_end   = end
    _request_redraw()


def toggle_loop(context=None):
    """Ativa/desativa o loop."""
    tl = get_timeline(context)
    tl.loop_enabled = not tl.loop_enabled
    _request_redraw()


# ---------------------------------------------------------------------------
# Arrasto interativo do cursor (usado pelo operador modal)
# ---------------------------------------------------------------------------

class CursorDragState:
    """Estado interno para o drag modal do cursor."""
    active     = False
    start_x    = 0
    start_beat = 0.0


_drag = CursorDragState()


def begin_cursor_drag(mouse_beat: float):
    """Inicia arrasto do cursor."""
    _drag.active     = True
    _drag.start_beat = mouse_beat


def update_cursor_drag(beat: float, context=None):
    """Atualiza posição durante arrasto."""
    if _drag.active:
        set_cursor_beat(beat, context)


def end_cursor_drag():
    """Finaliza arrasto."""
    _drag.active = False


def is_dragging() -> bool:
    return _drag.active


# ---------------------------------------------------------------------------
# Verificação de posição na região de loop
# ---------------------------------------------------------------------------

def wrap_cursor_if_looping(context=None):
    """
    Se o loop estiver ativo e o cursor passar do loop_end, retorna ao loop_start.
    Chamado periodicamente pelo playback.
    """
    tl = get_timeline(context)
    if tl.loop_enabled and tl.cursor_beat >= tl.loop_end:
        set_cursor_beat(tl.loop_start, context)


# ---------------------------------------------------------------------------
# Auto-scroll: mantém cursor visível
# ---------------------------------------------------------------------------

def ensure_cursor_visible(context=None):
    """
    Ajusta scroll_offset para que o cursor fique dentro da área visível.
    Usa margem de 10% da view para não ficar colando na borda.
    """
    tl = get_timeline(context)
    cursor = tl.cursor_beat
    pxb    = tl.pixels_per_beat * tl.zoom_level

    # Estimativa de beats visíveis (fallback 20 beats se não há área)
    try:
        area_w = next(
            a.width for a in (context or bpy.context).screen.areas
            if a.type == "VIEW_3D"  # substituir pelo tipo correto da área DAW
        )
    except StopIteration:
        area_w = 800

    visible_beats = (area_w - tl.track_header_width) / pxb if pxb > 0 else 20.0
    margin = visible_beats * 0.1

    view_start = tl.scroll_offset
    view_end   = view_start + visible_beats

    if cursor < view_start + margin:
        tl.scroll_offset = max(0.0, cursor - margin)
        _request_redraw()
    elif cursor > view_end - margin:
        tl.scroll_offset = cursor - visible_beats + margin
        _request_redraw()


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _get_bpm(context=None) -> float:
    """Tenta obter BPM da sessão DAW; fallback 120."""
    try:
        return (context or bpy.context).scene.daw_session.bpm
    except Exception:
        return 120.0


def _sync_engine_cursor(beat: float, context=None):
    """Envia nova posição do cursor ao transport da engine, se disponível."""
    try:
        from daw.daw_engine.transport import Transport
        Transport.instance().seek(beat)
    except Exception:
        pass


def _request_redraw():
    """Solicita redesenho de todas as áreas do Blender."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()