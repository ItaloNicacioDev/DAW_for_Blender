"""
timeline/ui.py
Renderização visual da timeline no Blender usando gpu/blf.
Desenha: régua de beats, grid, tracks, clips, playhead, marcadores, loop region.
"""

import bpy
import blf
import math

try:
    import gpu
    from gpu_extras.batch import batch_for_shader
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False

from .utils    import get_timeline, beat_to_px, px_to_beat, get_track_y_positions, format_beat_label
from .snapping import get_grid_lines, get_bar_lines
from .playback import is_playing, is_recording


# ---------------------------------------------------------------------------
# Shaders
# ---------------------------------------------------------------------------

_shader_2d = None

def _get_shader():
    global _shader_2d
    if _shader_2d is None and GPU_AVAILABLE:
        _shader_2d = gpu.shader.from_builtin("UNIFORM_COLOR")
    return _shader_2d


# ---------------------------------------------------------------------------
# Cores (tema escuro padrão)
# ---------------------------------------------------------------------------

C = {
    "bg_ruler":         (0.12, 0.12, 0.12, 1.0),
    "bg_content":       (0.10, 0.10, 0.10, 1.0),
    "bg_track_even":    (0.13, 0.13, 0.13, 1.0),
    "bg_track_odd":     (0.11, 0.11, 0.11, 1.0),
    "grid_bar":         (0.25, 0.25, 0.25, 1.0),
    "grid_beat":        (0.17, 0.17, 0.17, 1.0),
    "grid_subdiv":      (0.14, 0.14, 0.14, 1.0),
    "cursor":           (1.0,  0.85, 0.0,  1.0),
    "loop_region":      (0.2,  0.6,  1.0,  0.12),
    "loop_border":      (0.2,  0.6,  1.0,  0.6),
    "marker":           (1.0,  0.75, 0.0,  1.0),
    "clip_border":      (0.0,  0.0,  0.0,  0.4),
    "clip_selected":    (1.0,  1.0,  1.0,  0.3),
    "clip_muted":       (0.4,  0.4,  0.4,  0.5),
    "header_bg":        (0.08, 0.08, 0.08, 1.0),
    "header_sep":       (0.22, 0.22, 0.22, 1.0),
    "text":             (0.85, 0.85, 0.85, 1.0),
    "text_dim":         (0.5,  0.5,  0.5,  1.0),
    "record":           (0.9,  0.1,  0.1,  1.0),
}


# ---------------------------------------------------------------------------
# Primitivas de desenho
# ---------------------------------------------------------------------------

def _draw_rect(x, y, w, h, color):
    if not GPU_AVAILABLE or w <= 0 or h <= 0:
        return
    shader = _get_shader()
    verts  = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    batch  = batch_for_shader(shader, "TRI_FAN", {"pos": verts})
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_line(x1, y1, x2, y2, color, width=1.0):
    if not GPU_AVAILABLE:
        return
    shader = _get_shader()
    batch  = batch_for_shader(shader, "LINES", {"pos": [(x1, y1), (x2, y2)]})
    gpu.state.line_width_set(width)
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_text(text, x, y, size=11, color=None):
    if color is None:
        color = C["text"]
    font_id = 0
    blf.size(font_id, size)
    blf.color(font_id, *color)
    blf.position(font_id, x, y, 0)
    blf.draw(font_id, text)


def _text_width(text, size=11) -> float:
    blf.size(0, size)
    return blf.dimensions(0, text)[0]


# ---------------------------------------------------------------------------
# Desenho principal
# ---------------------------------------------------------------------------

def draw_timeline(context):
    """Entry point do draw handler. Chamado a cada redesenho da área."""
    tl = get_timeline(context)
    if not tl.tracks and not tl.markers:
        return

    region     = context.region
    area_w     = region.width
    area_h     = region.height
    header_w   = tl.track_header_width
    ruler_h    = tl.ruler_height
    content_x  = header_w
    content_w  = area_w - header_w
    content_h  = area_h - ruler_h

    if not GPU_AVAILABLE:
        return

    gpu.state.blend_set("ALPHA")

    # 1. Fundo geral
    _draw_rect(0, 0, area_w, area_h, C["bg_content"])

    # 2. Fundo da régua
    _draw_rect(0, area_h - ruler_h, area_w, ruler_h, C["bg_ruler"])

    # 3. Grid e régua
    view_start, view_end = _get_view_range(tl, content_w)
    _draw_grid(tl, content_x, 0, content_w, area_h - ruler_h, ruler_h, area_h, view_start, view_end)

    # 4. Fundo do header
    _draw_rect(0, 0, header_w, area_h, C["header_bg"])
    _draw_line(header_w, 0, header_w, area_h, C["header_sep"], 1.0)

    # 5. Tracks e clips
    track_positions = get_track_y_positions(tl, area_h, ruler_h)
    _draw_tracks(tl, track_positions, content_x, content_w, header_w, view_start, area_h, ruler_h)

    # 6. Loop region
    if tl.loop_enabled and tl.show_loop_region:
        _draw_loop_region(tl, content_x, 0, content_h, ruler_h, area_h, view_start)

    # 7. Marcadores
    if tl.show_markers:
        _draw_markers(tl, content_x, area_h, ruler_h, view_start)

    # 8. Playhead (cursor)
    _draw_cursor(tl, content_x, area_h, ruler_h, view_start)

    gpu.state.blend_set("NONE")


# ---------------------------------------------------------------------------
# Grid e régua
# ---------------------------------------------------------------------------

def _draw_grid(tl, cx, cy, cw, ch, ruler_h, area_h, view_start, view_end):
    """Desenha linhas de grid e labels na régua."""
    try:
        ts = bpy.context.scene.daw_session.time_signature_num
    except Exception:
        ts = 4

    bar_lines  = get_bar_lines(view_start, view_end, tl, ts)
    beat_lines = get_grid_lines(view_start, view_end, tl)

    # Grid beats (linhas finas)
    for beat in beat_lines:
        x = cx + beat_to_px(beat, tl)
        _draw_line(x, cy, x, cy + ch, C["grid_beat"], 1.0)

    # Grid compassos (linhas mais visíveis)
    for beat in bar_lines:
        x = cx + beat_to_px(beat, tl)
        _draw_line(x, cy, x, cy + ch, C["grid_bar"], 1.0)
        # Label na régua
        if tl.show_beat_numbers:
            label = format_beat_label(beat, ts)
            lx = x + 3
            ly = area_h - ruler_h + 8
            _draw_text(label, lx, ly, size=10, color=C["text_dim"])


# ---------------------------------------------------------------------------
# Tracks e clips
# ---------------------------------------------------------------------------

def _draw_tracks(tl, positions, cx, cw, header_w, view_start, area_h, ruler_h):
    for i, (track, (y_top, y_bot)) in enumerate(zip(tl.tracks, positions)):
        h = y_top - y_bot
        if h <= 0:
            continue

        # Fundo alternado
        bg = C["bg_track_even"] if i % 2 == 0 else C["bg_track_odd"]
        _draw_rect(cx, y_bot, cw, h, bg)

        # Clips
        if not track.collapsed:
            for clip in track.clips:
                _draw_clip(clip, tl, cx, y_bot, h, view_start)

        # Header
        _draw_track_header(track, 0, y_bot, header_w, h)

        # Separador inferior
        _draw_line(0, y_bot, cx + cw, y_bot, C["header_sep"], 1.0)


def _draw_clip(clip, tl, cx, track_y, track_h, view_start):
    x = cx + beat_to_px(clip.start_beat, tl)
    w = clip.length_beats * tl.pixels_per_beat * tl.zoom_level
    y = track_y + 2
    h = track_h - 4

    if w < 1:
        return

    color = tuple(clip.color[:3]) + (0.7 if not clip.muted else 0.35,)
    _draw_rect(x, y, w, h, color)

    # Borda
    border_color = C["clip_selected"] if clip.selected else C["clip_border"]
    _draw_line(x,     y,     x + w, y,     border_color)
    _draw_line(x + w, y,     x + w, y + h, border_color)
    _draw_line(x + w, y + h, x,     y + h, border_color)
    _draw_line(x,     y + h, x,     y,     border_color)

    # Label
    if w > 20:
        label = clip.name
        text_color = C["text_dim"] if clip.muted else C["text"]
        _draw_text(label, x + 4, y + h / 2 - 5, size=10, color=text_color)


def _draw_track_header(track, x, y, w, h):
    # Cor de label
    mute_color = C["text_dim"] if track.muted else C["text"]

    # Faixa de cor
    _draw_rect(x, y, 4, h, (*track.color, 1.0))

    # Nome
    _draw_text(track.name, x + 8, y + h / 2 - 5, size=10, color=mute_color)

    # Ícones de status (texto placeholder)
    status = ""
    if track.muted: status += "M "
    if track.solo:  status += "S "
    if track.armed: status += "● "
    if status:
        sw = _text_width(status, 9)
        _draw_text(status.strip(), x + w - sw - 6, y + h / 2 - 5, size=9,
                   color=C["record"] if track.armed else C["text_dim"])


# ---------------------------------------------------------------------------
# Loop region
# ---------------------------------------------------------------------------

def _draw_loop_region(tl, cx, cy, ch, ruler_h, area_h, view_start):
    lx = cx + beat_to_px(tl.loop_start, tl)
    rx = cx + beat_to_px(tl.loop_end, tl)
    w  = rx - lx
    if w < 1:
        return
    _draw_rect(lx, cy, w, ch, C["loop_region"])
    _draw_line(lx, cy, lx, cy + ch + ruler_h, C["loop_border"], 1.5)
    _draw_line(rx, cy, rx, cy + ch + ruler_h, C["loop_border"], 1.5)


# ---------------------------------------------------------------------------
# Playhead
# ---------------------------------------------------------------------------

def _draw_cursor(tl, cx, area_h, ruler_h, view_start):
    x = cx + beat_to_px(tl.cursor_beat, tl)
    color = C["record"] if is_recording() else C["cursor"]
    _draw_line(x, 0, x, area_h, color, 1.5)
    # Triângulo na régua
    ty = area_h - ruler_h
    verts = [(x, ty), (x - 6, area_h), (x + 6, area_h)]
    shader = _get_shader()
    batch = batch_for_shader(shader, "TRIS", {"pos": verts})
    shader.uniform_float("color", color)
    batch.draw(shader)


# ---------------------------------------------------------------------------
# Marcadores
# ---------------------------------------------------------------------------

def _draw_markers(tl, cx, area_h, ruler_h, view_start):
    for marker in tl.markers:
        x = cx + beat_to_px(marker.position_beat, tl)
        color = tuple(marker.color[:3]) + (1.0,)
        _draw_line(x, 0, x, area_h, (*color[:3], 0.4), 1.0)

        # Flag na régua
        fy = area_h - ruler_h
        verts = [(x, fy), (x + 10, area_h - 4), (x, area_h - 4)]
        shader = _get_shader()
        batch  = batch_for_shader(shader, "TRIS", {"pos": verts})
        shader.uniform_float("color", color)
        batch.draw(shader)

        # Nome
        _draw_text(marker.name, x + 3, fy + 4, size=9, color=color)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_view_range(tl, content_w: float) -> tuple:
    pxb = tl.pixels_per_beat * tl.zoom_level
    if pxb > 0:
        view_end = tl.scroll_offset + content_w / pxb
    else:
        view_end = tl.scroll_offset + 32.0
    return tl.scroll_offset, view_end


# ---------------------------------------------------------------------------
# Handler de draw
# ---------------------------------------------------------------------------

_draw_handle = None


def register_draw_handler(space_type="SEQUENCE_EDITOR", region_type="WINDOW"):
    """Registra o draw handler na área da DAW."""
    global _draw_handle
    if _draw_handle is None:
        space = getattr(bpy.types, space_type, None)
        if space:
            _draw_handle = space.draw_handler_add(
                draw_timeline, (bpy.context,), region_type, "POST_PIXEL"
            )


def unregister_draw_handler(space_type="SEQUENCE_EDITOR", region_type="WINDOW"):
    global _draw_handle
    if _draw_handle is not None:
        space = getattr(bpy.types, space_type, None)
        if space:
            space.draw_handler_remove(_draw_handle, region_type)
        _draw_handle = None


# ---------------------------------------------------------------------------
# Painel de configuração da timeline (sidebar)
# ---------------------------------------------------------------------------

class DAW_PT_timeline_settings(bpy.types.Panel):
    bl_label      = "Timeline"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category   = "DAW"

    def draw(self, context):
        tl     = get_timeline(context)
        layout = self.layout

        # Transport
        row = layout.row(align=True)
        row.operator("daw.timeline_rewind",      text="", icon="REW")
        row.operator("daw.timeline_toggle_play", text="", icon="PLAY" if not is_playing() else "PAUSE")
        row.operator("daw.timeline_stop",        text="", icon="SNAP_FACE")
        row.operator("daw.timeline_record",      text="", icon="REC")

        layout.separator()

        # Zoom
        row = layout.row(align=True)
        row.operator("daw.timeline_zoom_in",  text="", icon="ZOOM_IN")
        row.operator("daw.timeline_zoom_out", text="", icon="ZOOM_OUT")
        row.operator("daw.timeline_zoom_fit", text="Encaixar")

        layout.separator()

        # Snap
        col = layout.column()
        col.prop(tl, "snap_enabled", text="Snap")
        if tl.snap_enabled:
            col.prop(tl, "snap_mode", text="")

        layout.separator()

        # Loop
        col = layout.column()
        col.prop(tl, "loop_enabled", text="Loop")
        if tl.loop_enabled:
            row = col.row(align=True)
            row.prop(tl, "loop_start", text="Início")
            row.prop(tl, "loop_end",   text="Fim")

        layout.separator()

        # Tracks
        col = layout.column()
        col.label(text="Tracks")
        row = col.row(align=True)
        row.operator("daw.timeline_add_track",    text="", icon="ADD")
        row.operator("daw.timeline_remove_track", text="", icon="REMOVE")
        row.operator("daw.timeline_move_track",   text="", icon="TRIA_UP").direction = "UP"
        row.operator("daw.timeline_move_track",   text="", icon="TRIA_DOWN").direction = "DOWN"


PANEL_CLASSES = [DAW_PT_timeline_settings]


def register():
    for cls in PANEL_CLASSES:
        bpy.utils.register_class(cls)
    register_draw_handler()


def unregister():
    unregister_draw_handler()
    for cls in reversed(PANEL_CLASSES):
        bpy.utils.unregister_class(cls)