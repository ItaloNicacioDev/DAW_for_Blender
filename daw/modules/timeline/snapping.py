"""
timeline/snapping.py
Lógica de snapping da timeline:
  - Snap de beats ao grid (por resolução)
  - Snap de clips às bordas de outros clips
  - Snap ao cursor e a marcadores
  - Detecção de qual snap está mais perto
"""

import math
from .utils import get_timeline, get_snap_resolution, SNAP_VALUES
from .markers import nearest_marker_beat


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

SNAP_MARKER_THRESHOLD = 0.25   # beats — dentro desse raio, snap ao marcador
SNAP_CLIP_EDGE_THRESHOLD = 0.2 # beats — dentro desse raio, snap à borda de clip
SNAP_CURSOR_THRESHOLD = 0.2    # beats — dentro desse raio, snap ao cursor


# ---------------------------------------------------------------------------
# Snap principal (entry point)
# ---------------------------------------------------------------------------

def apply_snap(beat: float, context=None,
               snap_to_clips: bool = True,
               snap_to_markers: bool = True,
               snap_to_cursor: bool = False) -> float:
    """
    Aplica todos os snaps ativos e retorna o beat mais próximo encontrado.
    Prioridade: marcadores > cursor > bordas de clips > grid.
    """
    tl = get_timeline(context)

    if not tl.snap_enabled:
        return beat

    candidates = []

    # 1. Snap ao marcador
    if snap_to_markers and tl.show_markers:
        m_beat = nearest_marker_beat(beat, context, SNAP_MARKER_THRESHOLD)
        if m_beat != beat:
            candidates.append((abs(m_beat - beat), m_beat, "marker"))

    # 2. Snap ao cursor
    if snap_to_cursor:
        cursor = tl.cursor_beat
        if abs(cursor - beat) <= SNAP_CURSOR_THRESHOLD:
            candidates.append((abs(cursor - beat), cursor, "cursor"))

    # 3. Snap às bordas de clips
    if snap_to_clips:
        edge = nearest_clip_edge(beat, tl)
        if edge is not None and abs(edge - beat) <= SNAP_CLIP_EDGE_THRESHOLD:
            candidates.append((abs(edge - beat), edge, "clip_edge"))

    # 4. Snap ao grid
    grid_beat = snap_to_grid(beat, tl)
    candidates.append((abs(grid_beat - beat), grid_beat, "grid"))

    # Retorna o candidato com menor distância
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1] if candidates else beat


# ---------------------------------------------------------------------------
# Snap ao grid
# ---------------------------------------------------------------------------

def snap_to_grid(beat: float, settings=None, context=None) -> float:
    """Retorna o beat mais próximo no grid de acordo com o snap_mode."""
    if settings is None:
        settings = get_timeline(context)

    if not settings.snap_enabled or settings.snap_mode == "FREE":
        return beat

    res = get_snap_resolution(settings)
    if res <= 0:
        return beat

    return round(beat / res) * res


def snap_to_grid_floor(beat: float, settings=None, context=None) -> float:
    """Snap para o beat de grid imediatamente abaixo (útil para início de clip)."""
    if settings is None:
        settings = get_timeline(context)

    res = get_snap_resolution(settings)
    if res <= 0:
        return beat

    return math.floor(beat / res) * res


def get_grid_lines(view_start: float, view_end: float, settings) -> list:
    """
    Retorna lista de beats onde devem ser desenhadas linhas de grid.
    Varia a densidade de acordo com zoom e resolução.
    """
    res = get_snap_resolution(settings)
    if res <= 0:
        res = 1.0

    # Adapta a resolução conforme zoom (evita linhas demais)
    pxb = settings.pixels_per_beat * settings.zoom_level
    min_px_between = 8.0
    while res * pxb < min_px_between:
        res *= 2

    lines = []
    beat = math.floor(view_start / res) * res
    while beat <= view_end:
        lines.append(beat)
        beat += res
        beat = round(beat / 1e-9) * 1e-9  # evita acúmulo de float

    return lines


def get_bar_lines(view_start: float, view_end: float, settings,
                  time_sig_num: int = 4) -> list:
    """Retorna apenas as linhas de compasso (beats múltiplos de time_sig_num)."""
    beat = math.floor(view_start / time_sig_num) * time_sig_num
    lines = []
    while beat <= view_end:
        lines.append(beat)
        beat += time_sig_num
    return lines


# ---------------------------------------------------------------------------
# Snap à borda de clips
# ---------------------------------------------------------------------------

def nearest_clip_edge(beat: float, settings) -> float | None:
    """
    Procura a borda de clip (início ou fim) mais próxima do beat dado.
    Retorna None se não encontrar nenhum clip.
    """
    best_dist = float("inf")
    best_edge = None

    for track in settings.tracks:
        for clip in track.clips:
            edges = [clip.start_beat, clip.start_beat + clip.length_beats]
            for edge in edges:
                dist = abs(edge - beat)
                if dist < best_dist:
                    best_dist = dist
                    best_edge = edge

    return best_edge


# ---------------------------------------------------------------------------
# Snap de duração de clip
# ---------------------------------------------------------------------------

def snap_clip_length(length_beats: float, settings) -> float:
    """
    Snap da duração do clip ao grid.
    Garante comprimento mínimo de 1 subdivisão.
    """
    if not settings.snap_enabled:
        return length_beats

    res = get_snap_resolution(settings)
    if res <= 0:
        return length_beats

    snapped = round(length_beats / res) * res
    return max(res, snapped)


# ---------------------------------------------------------------------------
# Snap magnético (detecta se está "perto" de um ponto de snap)
# ---------------------------------------------------------------------------

def is_near_snap_point(beat: float, settings, threshold_px: float = 8.0) -> bool:
    """
    Verifica se beat está próximo de um ponto de snap (para highlight visual).
    threshold_px é convertido para beats usando pixels_per_beat e zoom.
    """
    pxb = settings.pixels_per_beat * settings.zoom_level
    threshold_beats = threshold_px / pxb if pxb > 0 else 0.1

    snapped = snap_to_grid(beat, settings)
    return abs(beat - snapped) <= threshold_beats


# ---------------------------------------------------------------------------
# Helpers de label de snap
# ---------------------------------------------------------------------------

SNAP_LABELS = {
    "BAR":       "Compasso",
    "BEAT":      "Beat",
    "HALF":      "1/2",
    "QUARTER":   "1/4",
    "EIGHTH":    "1/8",
    "SIXTEENTH": "1/16",
    "FREE":      "Livre",
}


def get_snap_label(settings) -> str:
    return SNAP_LABELS.get(settings.snap_mode, settings.snap_mode)