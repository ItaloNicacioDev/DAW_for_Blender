"""
timeline/utils.py
Utilitários compartilhados do módulo de timeline:
  - Conversões entre beats, pixels, segundos e compassos
  - Helpers de seleção e iteração de clips/tracks
  - Cálculo de grid de snapping
"""

import bpy
import math


# ---------------------------------------------------------------------------
# Acesso ao settings
# ---------------------------------------------------------------------------

def get_timeline(context=None):
    """Retorna DAW_TimelineSettings da cena ativa."""
    ctx = context or bpy.context
    return ctx.scene.daw_timeline


# ---------------------------------------------------------------------------
# Conversões Beat ↔ Pixel
# ---------------------------------------------------------------------------

def beat_to_px(beat: float, settings) -> float:
    """Converte um valor em beats para pixels relativos à área da timeline."""
    return (beat - settings.scroll_offset) * settings.pixels_per_beat * settings.zoom_level


def px_to_beat(px: float, settings) -> float:
    """Converte pixels (relativos ao início da área de clips) para beats."""
    denom = settings.pixels_per_beat * settings.zoom_level
    if denom == 0:
        return 0.0
    return px / denom + settings.scroll_offset


def beat_to_px_abs(beat: float, settings, header_width: float = 0.0) -> float:
    """Posição em pixels absolutos (incluindo header width)."""
    return header_width + beat_to_px(beat, settings)


# ---------------------------------------------------------------------------
# Conversões Beat ↔ Segundo
# ---------------------------------------------------------------------------

def beat_to_seconds(beat: float, bpm: float) -> float:
    """Converte beats para segundos dado o BPM."""
    if bpm <= 0:
        return 0.0
    return beat * 60.0 / bpm


def seconds_to_beat(seconds: float, bpm: float) -> float:
    """Converte segundos para beats dado o BPM."""
    if bpm <= 0:
        return 0.0
    return seconds * bpm / 60.0


# ---------------------------------------------------------------------------
# Conversões Beat ↔ Compasso / Batida
# ---------------------------------------------------------------------------

def beat_to_bar_beat(beat: float, time_signature_num: int = 4) -> tuple:
    """
    Retorna (compasso, beat_dentro_do_compasso) a partir de um beat absoluto.
    Compasso e beat são 1-indexados.
    """
    bar = int(beat // time_signature_num) + 1
    b   = (beat % time_signature_num) + 1
    return bar, b


def bar_beat_to_beat(bar: int, beat: int, time_signature_num: int = 4) -> float:
    """Converte (compasso, beat) para beat absoluto (0-indexed)."""
    return (bar - 1) * time_signature_num + (beat - 1)


def format_beat_label(beat: float, time_signature_num: int = 4) -> str:
    """Retorna string formatada 'Compasso:Beat' ex: '3:2'."""
    bar, b = beat_to_bar_beat(beat, time_signature_num)
    b_int = int(b)
    return f"{bar}:{b_int}"


# ---------------------------------------------------------------------------
# Snapping
# ---------------------------------------------------------------------------

SNAP_VALUES = {
    "BAR":       None,   # resolvido dinamicamente
    "BEAT":      1.0,
    "HALF":      0.5,
    "QUARTER":   0.25,
    "EIGHTH":    0.125,
    "SIXTEENTH": 0.0625,
    "FREE":      0.0,
}


def get_snap_resolution(settings) -> float:
    """Retorna a resolução de snap em beats para o modo configurado."""
    mode = settings.snap_mode
    if mode == "BAR":
        # Obtém time signature da cena se disponível, senão 4
        try:
            ts = bpy.context.scene.daw_session.time_signature_num
        except Exception:
            ts = 4
        return float(ts)
    return SNAP_VALUES.get(mode, 1.0)


def snap_beat(beat: float, settings) -> float:
    """Aplica snap ao valor de beat se snap estiver habilitado."""
    if not settings.snap_enabled:
        return beat
    res = get_snap_resolution(settings)
    if res <= 0:
        return beat
    return round(beat / res) * res


def snap_beat_floor(beat: float, settings) -> float:
    """Snap para baixo (floor)."""
    if not settings.snap_enabled:
        return beat
    res = get_snap_resolution(settings)
    if res <= 0:
        return beat
    return math.floor(beat / res) * res


# ---------------------------------------------------------------------------
# Iteradores de tracks e clips
# ---------------------------------------------------------------------------

def iter_tracks(settings):
    """Itera sobre todas as tracks."""
    for track in settings.tracks:
        yield track


def iter_clips(settings):
    """Itera sobre todos os clips de todas as tracks com (track_index, clip)."""
    for ti, track in enumerate(settings.tracks):
        for clip in track.clips:
            yield ti, clip


def iter_visible_clips(settings):
    """Clips visíveis na janela atual (baseado em scroll e zoom)."""
    view_start = settings.scroll_offset
    view_end = view_start + px_to_beat(10000, settings)  # estimativa larga
    for ti, clip in iter_clips(settings):
        if clip.start_beat + clip.length_beats >= view_start and clip.start_beat <= view_end:
            yield ti, clip


# ---------------------------------------------------------------------------
# Seleção
# ---------------------------------------------------------------------------

def get_selected_clips(settings):
    """Retorna lista de (track_index, clip) selecionados."""
    return [(ti, c) for ti, c in iter_clips(settings) if c.selected]


def get_clip_at(track, beat: float):
    """
    Retorna o clip da track que contém o beat dado, ou None.
    Retorna o último clip em caso de sobreposição.
    """
    result = None
    for clip in track.clips:
        if clip.start_beat <= beat < clip.start_beat + clip.length_beats:
            result = clip
    return result


def deselect_all_clips(settings):
    """Desmarca todos os clips."""
    for _, clip in iter_clips(settings):
        clip.selected = False


# ---------------------------------------------------------------------------
# Posição Y de tracks
# ---------------------------------------------------------------------------

def get_track_y_positions(settings, area_height: float, ruler_height: float = 28.0):
    """
    Retorna lista de (y_top, y_bottom) em pixels para cada track,
    de cima para baixo na área de clips.
    Já desconta o scroll vertical.
    """
    positions = []
    y = area_height - ruler_height - settings.scroll_y
    for track in settings.tracks:
        h = track.height if not track.collapsed else 24.0
        positions.append((y, y - h))
        y -= h
    return positions


def track_at_y(settings, y: float, area_height: float, ruler_height: float = 28.0):
    """
    Retorna (track_index, track) para a posição Y em pixels (origem bottom-left do Blender).
    Retorna (None, None) se não houver track.
    """
    positions = get_track_y_positions(settings, area_height, ruler_height)
    for i, (y_top, y_bot) in enumerate(positions):
        if y_bot <= y <= y_top:
            return i, settings.tracks[i]
    return None, None


# ---------------------------------------------------------------------------
# Cores
# ---------------------------------------------------------------------------

TRACK_DEFAULT_COLORS = [
    (0.2, 0.5, 0.9),
    (0.9, 0.3, 0.3),
    (0.3, 0.8, 0.4),
    (0.9, 0.6, 0.1),
    (0.7, 0.3, 0.9),
    (0.3, 0.8, 0.8),
    (0.9, 0.9, 0.2),
    (0.9, 0.5, 0.7),
]


def get_track_color(index: int) -> tuple:
    """Cor padrão ciclada para uma nova track."""
    return TRACK_DEFAULT_COLORS[index % len(TRACK_DEFAULT_COLORS)]


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------

def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def clips_overlap(clip_a, clip_b) -> bool:
    """Verifica se dois clips da mesma track se sobrepõem."""
    a_end = clip_a.start_beat + clip_a.length_beats
    b_end = clip_b.start_beat + clip_b.length_beats
    return clip_a.start_beat < b_end and b_end > clip_a.start_beat


def validate_clip_position(clip, track) -> bool:
    """
    Verifica se o clip não conflita com outros clips da track.
    Retorna True se a posição for válida.
    """
    for other in track.clips:
        if other == clip:
            continue
        if clips_overlap(clip, other):
            return False
    return True