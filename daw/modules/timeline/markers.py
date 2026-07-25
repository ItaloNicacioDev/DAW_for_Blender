"""
timeline/markers.py
Gerencia marcadores da timeline:
  - Adicionar / remover / renomear marcadores
  - Navegar entre marcadores
  - Snap de cursor ao marcador mais próximo
"""

import bpy
from .utils import get_timeline, snap_beat
from .cursor import set_cursor_beat


# ---------------------------------------------------------------------------
# CRUD de marcadores
# ---------------------------------------------------------------------------

def add_marker(name: str = "", position_beat: float = None, context=None) -> int:
    """
    Adiciona um marcador na posição do cursor (ou em position_beat).
    Retorna o índice do marcador criado.
    """
    tl = get_timeline(context)
    beat = position_beat if position_beat is not None else tl.cursor_beat

    m = tl.markers.add()
    m.name          = name or f"Marker {len(tl.markers)}"
    m.position_beat = max(0.0, beat)

    # Ativa o marcador recém-criado
    tl.active_marker_index = len(tl.markers) - 1

    _sort_markers(tl)
    _request_redraw()
    return tl.active_marker_index


def remove_marker(index: int = None, context=None):
    """Remove marcador pelo índice (default: ativo)."""
    tl = get_timeline(context)
    idx = index if index is not None else tl.active_marker_index

    if 0 <= idx < len(tl.markers):
        if tl.markers[idx].locked:
            return  # marcador travado não pode ser removido
        tl.markers.remove(idx)
        tl.active_marker_index = max(0, idx - 1)
        _request_redraw()


def remove_all_markers(context=None):
    """Remove todos os marcadores não travados."""
    tl = get_timeline(context)
    # Itera de trás para frente para preservar índices
    for i in range(len(tl.markers) - 1, -1, -1):
        if not tl.markers[i].locked:
            tl.markers.remove(i)
    tl.active_marker_index = 0
    _request_redraw()


def rename_marker(name: str, index: int = None, context=None):
    """Renomeia o marcador ativo ou pelo índice."""
    tl  = get_timeline(context)
    idx = index if index is not None else tl.active_marker_index
    if 0 <= idx < len(tl.markers):
        tl.markers[idx].name = name


def move_marker(beat: float, index: int = None, context=None):
    """Move marcador para novo beat."""
    tl  = get_timeline(context)
    idx = index if index is not None else tl.active_marker_index
    if 0 <= idx < len(tl.markers):
        if not tl.markers[idx].locked:
            tl.markers[idx].position_beat = max(0.0, beat)
            _sort_markers(tl)
            _request_redraw()


def toggle_lock_marker(index: int = None, context=None):
    """Trava/destrava o marcador ativo."""
    tl  = get_timeline(context)
    idx = index if index is not None else tl.active_marker_index
    if 0 <= idx < len(tl.markers):
        tl.markers[idx].locked = not tl.markers[idx].locked


# ---------------------------------------------------------------------------
# Navegação entre marcadores
# ---------------------------------------------------------------------------

def go_to_next_marker(context=None):
    """Move o cursor para o próximo marcador à frente da posição atual."""
    tl     = get_timeline(context)
    cursor = tl.cursor_beat
    candidates = [
        m for m in tl.markers
        if m.position_beat > cursor + 1e-6
    ]
    if candidates:
        target = min(candidates, key=lambda m: m.position_beat)
        set_cursor_beat(target.position_beat, context)


def go_to_prev_marker(context=None):
    """Move o cursor para o marcador anterior à posição atual."""
    tl     = get_timeline(context)
    cursor = tl.cursor_beat
    candidates = [
        m for m in tl.markers
        if m.position_beat < cursor - 1e-6
    ]
    if candidates:
        target = max(candidates, key=lambda m: m.position_beat)
        set_cursor_beat(target.position_beat, context)


def go_to_marker(index: int, context=None):
    """Move o cursor para o marcador pelo índice."""
    tl = get_timeline(context)
    if 0 <= index < len(tl.markers):
        set_cursor_beat(tl.markers[index].position_beat, context)
        tl.active_marker_index = index


# ---------------------------------------------------------------------------
# Snap de beat ao marcador mais próximo
# ---------------------------------------------------------------------------

def nearest_marker_beat(beat: float, context=None, threshold_beats: float = 0.5) -> float:
    """
    Retorna o beat do marcador mais próximo se estiver dentro de threshold_beats.
    Caso contrário retorna o beat original.
    """
    tl = get_timeline(context)
    best_dist = threshold_beats
    result    = beat
    for m in tl.markers:
        dist = abs(m.position_beat - beat)
        if dist < best_dist:
            best_dist = dist
            result    = m.position_beat
    return result


def get_markers_in_range(start: float, end: float, context=None) -> list:
    """Retorna lista de marcadores dentro do range [start, end]."""
    tl = get_timeline(context)
    return [m for m in tl.markers if start <= m.position_beat <= end]


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _sort_markers(tl):
    """Ordena marcadores por posição (sem suporte nativo de sort no CollectionProperty)."""
    data = [(m.name, m.position_beat, tuple(m.color), m.locked)
            for m in tl.markers]
    data.sort(key=lambda x: x[1])

    # Limpa e reinseere na ordem correta
    while len(tl.markers) > 0:
        tl.markers.remove(0)
    for name, pos, color, locked in data:
        m = tl.markers.add()
        m.name          = name
        m.position_beat = pos
        m.color         = color
        m.locked        = locked


def _request_redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()