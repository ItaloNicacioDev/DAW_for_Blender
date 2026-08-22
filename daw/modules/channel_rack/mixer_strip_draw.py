# modules/channel_rack/mixer_strip_draw.py
"""
Desenho (GPU + blf) das channel strips do mixer, no estilo da imagem
de referência: card escuro, uma coluna por canal, número/nome no topo,
knob de pan, fader vertical com cap destacado, medidor de nível
vertical colorido (verde/amarelo/vermelho) e botões M/S no rodapé.

Autocontido -- não importa nada de `overlay.py` de propósito (os dois
módulos podem evoluir/ser removidos de forma independente).
"""
from __future__ import annotations

import math

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

from .colors import darken, lighten
from .mixer_strip_theme import PALETTE, meter_color
from .mixer_strip_geometry import panel_geometry, CORNER_R

_shader = None


def _sh():
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader


def _tris(coords, col):
    s = _sh()
    b = batch_for_shader(s, 'TRIS', {"pos": coords})
    s.uniform_float("color", col)
    b.draw(s)


def _rect(x, y, w, h, col):
    if w <= 0 or h <= 0:
        return
    _tris([(x, y), (x + w, y), (x + w, y + h),
           (x, y), (x + w, y + h), (x, y + h)], col)


def _round_rect(x, y, w, h, col, radius=CORNER_R):
    r = min(radius, w / 2, h / 2)
    if r <= 0:
        _rect(x, y, w, h, col)
        return
    _rect(x + r, y, w - 2 * r, h, col)
    _rect(x, y + r, r, h - 2 * r, col)
    _rect(x + w - r, y + r, r, h - 2 * r, col)
    corners = [
        (x + w - r, y + h - r, 0, 90),
        (x + r, y + h - r, 90, 180),
        (x + r, y + r, 180, 270),
        (x + w - r, y + r, 270, 360),
    ]
    for cx, cy, a0, a1 in corners:
        coords = [(cx, cy)]
        for i in range(7):
            ang = math.radians(a0 + (a1 - a0) * i / 6)
            coords.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
        tris = []
        for i in range(1, len(coords) - 1):
            tris.extend([coords[0], coords[i], coords[i + 1]])
        _tris(tris, col)


def _circle_outline(cx, cy, r, col, thickness=1.6, segments=24):
    coords = []
    for i in range(segments + 1):
        a0 = math.radians(360 * i / segments)
        a1 = math.radians(360 * (i + 1) / segments)
        p0o = (cx + math.cos(a0) * r, cy + math.sin(a0) * r)
        p1o = (cx + math.cos(a1) * r, cy + math.sin(a1) * r)
        p0i = (cx + math.cos(a0) * (r - thickness), cy + math.sin(a0) * (r - thickness))
        p1i = (cx + math.cos(a1) * (r - thickness), cy + math.sin(a1) * (r - thickness))
        coords.extend([p0o, p1o, p1i, p0o, p1i, p0i])
    _tris(coords, col)


def _circle_fill(cx, cy, r, col, segments=24):
    coords = [(cx, cy)]
    for i in range(segments + 1):
        a = math.radians(360 * i / segments)
        coords.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    tris = []
    for i in range(1, len(coords) - 1):
        tris.extend([coords[0], coords[i], coords[i + 1]])
    _tris(tris, col)


def _line(x1, y1, x2, y2, col, thickness=2.0):
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length * thickness / 2, dx / length * thickness / 2
    _tris([
        (x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny),
        (x1 + nx, y1 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny),
    ], col)


def _txt(text, x, y, size, col, font_id=0, center_w=None):
    blf.size(font_id, size)
    if center_w is not None:
        tw, _th = blf.dimensions(font_id, text)
        x = x + (center_w - tw) / 2
    blf.color(font_id, *col)
    blf.position(font_id, x, y, 0)
    blf.draw(font_id, text)


# ------------------------------------------------------------------ #
#  Sub-desenhos de cada elemento da strip
# ------------------------------------------------------------------ #
def _draw_knob(strip, pan_value: float, accent, s: float):
    cx, cy, r = strip.knob_cx, strip.knob_cy, strip.knob_r
    _circle_fill(cx, cy, r, PALETTE["knob_fill"])
    _circle_outline(cx, cy, r, PALETTE["knob_ring"])

    # ponteiro: -1..1 mapeado para -135°..+135° (0 = topo = "12 horas")
    angle = math.radians(90 - pan_value * 135)
    ix = cx + math.cos(angle) * (r - 6 * s)
    iy = cy + math.sin(angle) * (r - 6 * s)
    _line(cx, cy, ix, iy, accent, thickness=2.2 * s)
    _circle_fill(cx, cy, 2.2 * s, accent)

    label = f"{pan_value * 100:+.0f}" if abs(pan_value) > 0.005 else "C"
    _txt(label, cx - strip.strip_w / 2, cy - r - 13 * s, max(7.0, 9.5 * s),
         PALETTE["knob_txt"], center_w=strip.strip_w)


def _draw_fader(strip, volume: float, selected: bool, playing: bool, s: float):
    tx, ty = strip.fader_track_x, strip.fader_track_y
    tw, th = strip.fader_track_w, strip.fader_track_h
    _round_rect(tx, ty, tw, th, PALETTE["fader_track"], radius=3 * s)

    fill_h = th * max(0.0, min(1.0, volume))
    _round_rect(tx, ty, tw, fill_h, PALETTE["fader_fill"], radius=3 * s)

    cap_h = strip.fader_cap_h
    cap_y = ty + fill_h - cap_h / 2
    cap_w = strip.strip_w - 24 * s
    cap_x0 = strip.knob_cx - cap_w / 2
    cap_col = PALETTE["fader_cap_selected"] if selected else PALETTE["fader_cap"]

    # linha caindo do cap até a base do trilho -- só quando a strip
    # selecionada está de fato emitindo áudio (pedido original: "mostrar
    # o audio quando a strip selecionada esta sendo tocada").
    if selected and playing:
        _line(strip.knob_cx, cap_y, strip.knob_cx, ty, PALETTE["fader_cap_selected"], thickness=1.4 * s)

    _round_rect(cap_x0, cap_y, cap_w, cap_h, cap_col, radius=4 * s)
    _rect(cap_x0 + 4 * s, cap_y + cap_h / 2 - 1, cap_w - 8 * s, 1.4 * s, darken(cap_col[:3], 0.25) + (1.0,))

    db = (volume - 1.0) * 60.0 if volume < 1.0 else 0.0
    label = "0.0" if volume >= 0.999 else f"{db:.1f}"
    _txt(label, cap_x0, cap_y + cap_h + 3 * s, max(7.0, 8.5 * s), PALETTE["header_txt_dim"], center_w=cap_w)


def _draw_insert_area(strip, top_y: float, bottom_y: float, s: float):
    """Área vazia entre o knob e o fader, como o 'rack de inserts' vazio
    da referência -- puramente decorativa (linhas finas de slot)."""
    x0 = strip.knob_cx - (strip.strip_w - 24 * s) / 2
    x1 = strip.knob_cx + (strip.strip_w - 24 * s) / 2
    slot_h = 15 * s
    y = top_y - 6 * s
    while y - slot_h > bottom_y:
        _rect(x0, y - slot_h, x1 - x0, 1.0, (1.0, 1.0, 1.0, 0.035))
        y -= slot_h


def _draw_meter(strip, level_l: float, level_r: float, clipping: bool):
    mx, my, mw, mh = strip.meter_x, strip.meter_y, strip.meter_w, strip.meter_h
    _rect(mx, my, mw, mh, PALETTE["meter_bg"])

    half = mw / 2 - 1
    for offset, level in ((0.0, level_l), (half + 1, level_r)):
        seg_x = mx + offset
        level = max(0.0, min(1.0, level))
        fill_h = mh * level
        col = meter_color(level, clipping)
        _rect(seg_x, my, half, fill_h, col)

    # linhas de referência dos limiares (sutil), ajuda a "ler" a escala
    from .mixer_strip_theme import LEVEL_GREEN_MAX, LEVEL_YELLOW_MAX
    for thr in (LEVEL_GREEN_MAX, LEVEL_YELLOW_MAX):
        ly = my + mh * thr
        _rect(mx, ly, mw, 1.0, (0.0, 0.0, 0.0, 0.35))

    if clipping:
        _rect(mx, my + mh - 3, mw, 3, PALETTE["meter_clip"])


def _draw_strip(strip, ch, index: int, active_index: int, is_playing_selected: bool, s: float):
    is_selected = getattr(ch, "selected", False)
    alt = index % 2 == 1
    x0, x1 = strip.x, strip.x + strip.strip_w - 8 * s

    from .mixer_strip_theme import strip_bg_for
    bg = strip_bg_for(ch.mute, alt)
    body_top = strip.header_y + strip.header_h
    body_bottom = strip.footer_y - 6 * s
    _round_rect(x0, body_bottom, x1 - x0, body_top - body_bottom, bg, radius=6 * s)

    # contorno fino em todas as strips selecionadas (multi-seleção estilo
    # DAW) -- distinto do brilho verde, que só aparece quando está tocando
    if is_selected:
        outline = PALETTE["selection_outline"]
        pad = 1.5 * s
        _round_rect(x0 - pad, body_bottom - pad, (x1 - x0) + 2 * pad,
                     (body_top - body_bottom) + 2 * pad, outline, radius=7 * s)
        _round_rect(x0, body_bottom, x1 - x0, body_top - body_bottom, bg, radius=6 * s)

    if is_selected and is_playing_selected:
        glow = PALETTE["strip_selected_glow"]
        pad = 2 * s
        _round_rect(x0 - pad, body_bottom - pad, (x1 - x0) + 2 * pad,
                     (body_top - body_bottom) + 2 * pad, glow, radius=7 * s)
        _round_rect(x0, body_bottom, x1 - x0, body_top - body_bottom, bg, radius=6 * s)

    # header: chip de cor + número + nome -- fundo mais claro quando selecionado
    header_col = lighten(PALETTE["header_bg"][:3], 0.10) + (1.0,) if is_selected else PALETTE["header_bg"]
    _round_rect(x0, strip.header_y, x1 - x0, strip.header_h, header_col, radius=6 * s)
    chip_col = tuple(ch.color) + (1.0,)
    _round_rect(x0 + 6 * s, strip.header_y + strip.header_h / 2 - 4 * s, 8 * s, 8 * s, chip_col, radius=2 * s)
    number = str(getattr(ch, "vse_channel", index + 1))
    _txt(number, x0 + 18 * s, strip.header_y + strip.header_h / 2 - 4 * s, max(7.0, 10 * s), PALETTE["header_txt"])
    name = ch.name if len(ch.name) <= 9 else ch.name[:8] + "…"
    _txt(name, x0, strip.header_y - 12 * s, max(6.0, 9 * s), PALETTE["header_txt_dim"], center_w=(x1 - x0))

    # ponto indicador (verde = audível, apagado = mudo) logo abaixo do header
    dot_col = (0.30, 0.85, 0.35, 1.0) if not ch.mute else (0.30, 0.31, 0.36, 1.0)
    _circle_fill(strip.dot_cx, strip.dot_cy, strip.dot_r, dot_col)

    accent = chip_col if not ch.mute else darken(tuple(ch.color), 0.4) + (1.0,)
    _draw_knob(strip, getattr(ch, "pan", 0.0), accent, s)
    _draw_insert_area(strip, strip.knob_cy - strip.knob_r - 13 * s, strip.fader_track_y + strip.fader_track_h, s)
    _draw_fader(strip, getattr(ch, "volume", 0.78), is_selected, is_playing_selected, s)

    level = max(0.0, min(1.0, getattr(ch, "meter_level", 0.0))) if not ch.mute else 0.0
    pan = getattr(ch, "pan", 0.0)
    level_l = level * min(1.0, 1.0 - max(pan, 0.0))
    level_r = level * min(1.0, 1.0 + min(pan, 0.0))
    clipping = level >= 0.999
    _draw_meter(strip, level_l, level_r, clipping)

    # rodapé M/S
    mute_col = PALETTE["mute_on"] if ch.mute else PALETTE["mute_off"]
    solo_col = PALETTE["solo_on"] if ch.solo else PALETTE["solo_off"]
    _round_rect(strip.mute_x, strip.footer_y, strip.btn_w, strip.btn_h, mute_col, radius=4 * s)
    _txt("M", strip.mute_x, strip.footer_y + strip.btn_h / 2 - 4 * s, max(7.0, 9.5 * s),
         PALETTE["btn_txt"], center_w=strip.btn_w)
    _round_rect(strip.solo_x, strip.footer_y, strip.btn_w, strip.btn_h, solo_col, radius=4 * s)
    txt_col = PALETTE["btn_txt_on_dark"] if ch.solo else PALETTE["btn_txt"]
    _txt("S", strip.solo_x, strip.footer_y + strip.btn_h / 2 - 4 * s, max(7.0, 9.5 * s),
         txt_col, center_w=strip.btn_w)


# ------------------------------------------------------------------ #
#  Entry point chamado pelo draw_handler
# ------------------------------------------------------------------ #
def draw_mixer_strips():
    context = bpy.context
    if context.area is None or context.area.type != 'SEQUENCE_EDITOR':
        return
    scene = context.scene
    if scene is None or not hasattr(scene, "daw_channel_rack"):
        return
    rack = scene.daw_channel_rack
    if not getattr(rack, "show_mixer_strip_overlay", True):
        return

    region = context.region
    pos_x = getattr(rack, "overlay_pos_x", 16)
    pos_y = getattr(rack, "overlay_pos_y", 16)
    scale = getattr(rack, "overlay_scale", 1.0)
    geo = panel_geometry(region, rack.channels, pos_x, pos_y, scale)
    px, py, panel_w, panel_h = geo["px"], geo["py"], geo["panel_w"], geo["panel_h"]
    channels = geo["channels"]
    s = geo["scale"]

    gpu.state.blend_set('ALPHA')

    _round_rect(px - 1, py - 1, panel_w + 2, panel_h + 2, PALETTE["border"])
    _round_rect(px, py, panel_w, panel_h, PALETTE["panel_bg"])

    # barra de título -- arrastável (clique+arraste move o painel inteiro)
    title_y = geo["title_y"]
    _round_rect(px, title_y, panel_w, geo["title_h"], PALETTE["header_bg"], radius=6 * s)
    _txt("Mixer  ·  arraste para mover", px + 8 * s, title_y + geo["title_h"] / 2 - 4 * s,
         max(7.0, 9.5 * s), PALETTE["header_txt_dim"])

    # alça de redimensionar, canto inferior direito
    gx, gy, gs = geo["grip_x"], geo["grip_y"], geo["grip_size"]
    for i in range(3):
        off = i * gs / 3.2
        _line(gx + off, gy, gx + gs, gy + gs - off, PALETTE["header_txt_dim"], thickness=1.2 * s)

    if not channels:
        _txt("Nenhum canal", px + 8 * s, py + panel_h / 2, max(7.0, 10.5 * s), PALETTE["empty_txt"])
        gpu.state.blend_set('NONE')
        return

    for strip, ch in zip(geo["strips"], channels):
        is_selected_playing = getattr(ch, "meter_level", 0.0) > 0.02 and not ch.mute
        _draw_strip(strip, ch, strip.index, rack.active_channel_index, is_selected_playing, s)

    gpu.state.blend_set('NONE')