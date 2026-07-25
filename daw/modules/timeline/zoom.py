"""
timeline/zoom.py
Controle de zoom e scroll da timeline:
  - Zoom centrado no cursor do mouse ou no playhead
  - Scroll horizontal e vertical
  - Fit de zoom (encaixar toda a sessão na view)
  - Presets de zoom
"""

import math
import bpy
from .utils import get_timeline, px_to_beat, beat_to_px, clamp


# ---------------------------------------------------------------------------
# Limites
# ---------------------------------------------------------------------------

ZOOM_MIN = 0.05   # muito recuado
ZOOM_MAX = 32.0   # muito aproximado
PIXELS_PER_BEAT_BASE = 80.0


# ---------------------------------------------------------------------------
# Zoom
# ---------------------------------------------------------------------------

def zoom_in(factor: float = 1.25, pivot_beat: float = None, context=None):
    """
    Aumenta o zoom.
    pivot_beat: beat em torno do qual o zoom é centrado (mantém essa posição fixa na tela).
    """
    _apply_zoom(factor, pivot_beat, context)


def zoom_out(factor: float = 1.25, pivot_beat: float = None, context=None):
    """Diminui o zoom."""
    _apply_zoom(1.0 / factor, pivot_beat, context)


def set_zoom(zoom_level: float, pivot_beat: float = None, context=None):
    """Define zoom absoluto."""
    tl = get_timeline(context)
    old_zoom = tl.zoom_level
    new_zoom = clamp(zoom_level, ZOOM_MIN, ZOOM_MAX)

    if pivot_beat is not None:
        # Ajusta scroll para manter o pivot no mesmo lugar na tela
        _adjust_scroll_for_pivot(tl, pivot_beat, old_zoom, new_zoom)

    tl.zoom_level = new_zoom
    _request_redraw()


def get_zoom(context=None) -> float:
    return get_timeline(context).zoom_level


def zoom_to_fit(total_beats: float = None, context=None, area_width: float = None):
    """
    Ajusta zoom e scroll para que toda a sessão caiba na view.
    total_beats: duração total em beats; se None, calcula pelo conteúdo.
    """
    tl = get_timeline(context)

    if total_beats is None:
        total_beats = _compute_session_length(tl)
        if total_beats <= 0:
            total_beats = 16.0

    w = area_width or _get_area_content_width(tl)
    if w <= 0:
        return

    pixels_per_beat = w / total_beats
    tl.zoom_level    = clamp(pixels_per_beat / PIXELS_PER_BEAT_BASE, ZOOM_MIN, ZOOM_MAX)
    tl.scroll_offset = 0.0
    _request_redraw()


def zoom_to_selection(context=None, area_width: float = None):
    """Ajusta zoom para mostrar apenas os clips selecionados."""
    tl = get_timeline(context)

    selected_clips = []
    for track in tl.tracks:
        for clip in track.clips:
            if clip.selected:
                selected_clips.append(clip)

    if not selected_clips:
        return

    start = min(c.start_beat for c in selected_clips)
    end   = max(c.start_beat + c.length_beats for c in selected_clips)

    padding = (end - start) * 0.1
    zoom_to_range(start - padding, end + padding, context, area_width)


def zoom_to_range(start_beat: float, end_beat: float,
                  context=None, area_width: float = None):
    """Ajusta zoom e scroll para mostrar o range [start_beat, end_beat]."""
    tl = get_timeline(context)
    w  = area_width or _get_area_content_width(tl)
    if w <= 0:
        return

    span = end_beat - start_beat
    if span <= 0:
        return

    pixels_per_beat = w / span
    tl.zoom_level    = clamp(pixels_per_beat / PIXELS_PER_BEAT_BASE, ZOOM_MIN, ZOOM_MAX)
    tl.scroll_offset = max(0.0, start_beat)
    _request_redraw()


# ---------------------------------------------------------------------------
# Presets de zoom
# ---------------------------------------------------------------------------

ZOOM_PRESETS = {
    "overview":  0.1,    # sessão inteira ~200 beats na tela
    "session":   0.25,
    "section":   0.5,
    "bar":       1.0,    # ~20 beats visíveis
    "beat":      4.0,
    "note":      16.0,
}


def apply_preset(preset_name: str, context=None):
    """Aplica preset de zoom por nome."""
    level = ZOOM_PRESETS.get(preset_name)
    if level is not None:
        set_zoom(level, context=context)


# ---------------------------------------------------------------------------
# Scroll horizontal
# ---------------------------------------------------------------------------

def scroll_to(beat: float, context=None):
    """Define o scroll horizontal exato (em beats)."""
    tl = get_timeline(context)
    tl.scroll_offset = max(0.0, beat)
    _request_redraw()


def scroll_by(delta_beats: float, context=None):
    """Desloca o scroll horizontal por delta_beats."""
    tl = get_timeline(context)
    tl.scroll_offset = max(0.0, tl.scroll_offset + delta_beats)
    _request_redraw()


def scroll_by_px(delta_px: float, context=None):
    """Desloca o scroll horizontal por pixels (converte para beats)."""
    tl = get_timeline(context)
    pxb = tl.pixels_per_beat * tl.zoom_level
    if pxb > 0:
        tl.scroll_offset = max(0.0, tl.scroll_offset + delta_px / pxb)
        _request_redraw()


def get_scroll_offset(context=None) -> float:
    return get_timeline(context).scroll_offset


# ---------------------------------------------------------------------------
# Scroll vertical
# ---------------------------------------------------------------------------

def scroll_y_by(delta_px: float, context=None):
    """Desloca o scroll vertical por pixels."""
    tl = get_timeline(context)
    tl.scroll_y = max(0.0, tl.scroll_y + delta_px)
    _request_redraw()


def scroll_y_to(y_px: float, context=None):
    tl = get_timeline(context)
    tl.scroll_y = max(0.0, y_px)
    _request_redraw()


# ---------------------------------------------------------------------------
# Zoom por scroll do mouse (wheel)
# ---------------------------------------------------------------------------

def handle_wheel_zoom(delta: int, mouse_beat: float = None, context=None):
    """
    Processa evento de scroll de mouse para zoom.
    delta: +1 = zoom in, -1 = zoom out.
    mouse_beat: posição sob o cursor do mouse (pivot).
    """
    factor = 1.2 if delta > 0 else 1.0 / 1.2
    _apply_zoom(factor, mouse_beat, context)


def handle_wheel_scroll(delta: int, context=None, horizontal: bool = True):
    """
    Processa scroll de mouse para navegação (sem Ctrl).
    delta: +1 = direita/baixo, -1 = esquerda/cima.
    """
    tl = get_timeline(context)
    step = 2.0 / tl.zoom_level  # 2 beats de deslocamento base

    if horizontal:
        scroll_by(delta * step, context)
    else:
        scroll_y_by(delta * 30, context)


# ---------------------------------------------------------------------------
# Cálculo de beats visíveis
# ---------------------------------------------------------------------------

def get_visible_range(area_width: float, context=None) -> tuple:
    """Retorna (start_beat, end_beat) da área visível."""
    tl  = get_timeline(context)
    pxb = tl.pixels_per_beat * tl.zoom_level
    w   = area_width - tl.track_header_width
    if pxb > 0:
        end = tl.scroll_offset + w / pxb
    else:
        end = tl.scroll_offset + 16.0
    return tl.scroll_offset, end


def get_pixels_per_beat(context=None) -> float:
    tl = get_timeline(context)
    return tl.pixels_per_beat * tl.zoom_level


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _apply_zoom(factor: float, pivot_beat: float, context):
    tl       = get_timeline(context)
    old_zoom = tl.zoom_level
    new_zoom = clamp(old_zoom * factor, ZOOM_MIN, ZOOM_MAX)

    if pivot_beat is not None:
        _adjust_scroll_for_pivot(tl, pivot_beat, old_zoom, new_zoom)

    tl.zoom_level = new_zoom
    _request_redraw()


def _adjust_scroll_for_pivot(tl, pivot_beat: float, old_zoom: float, new_zoom: float):
    """
    Calcula novo scroll_offset para que pivot_beat permaneça no mesmo ponto
    visual após a mudança de zoom.
    """
    pxb_old = tl.pixels_per_beat * old_zoom
    pxb_new = tl.pixels_per_beat * new_zoom

    if pxb_old > 0 and pxb_new > 0:
        # Pixel da posição do pivot antes do zoom
        pivot_px = (pivot_beat - tl.scroll_offset) * pxb_old
        # Novo scroll para manter pivot_px no mesmo lugar
        tl.scroll_offset = max(0.0, pivot_beat - pivot_px / pxb_new)


def _compute_session_length(tl) -> float:
    """Estima a duração total da sessão em beats."""
    max_beat = 0.0
    for track in tl.tracks:
        for clip in track.clips:
            end = clip.start_beat + clip.length_beats
            if end > max_beat:
                max_beat = end
    return max_beat


def _get_area_content_width(tl) -> float:
    """Tenta obter largura da área de conteúdo da timeline."""
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                # Ajuste o tipo de área conforme a área do DAW for Blender
                if area.type in ("SEQUENCE_EDITOR", "DOPESHEET_EDITOR", "VIEW_3D"):
                    return float(area.width) - tl.track_header_width
    except Exception:
        pass
    return 800.0


def _request_redraw():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except Exception:
        pass