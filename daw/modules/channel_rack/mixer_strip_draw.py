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
from .mixer_strip_geometry import (
    panel_geometry, STRIP_W, HEADER_H, CORNER_R,
)

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
def _draw_knob(strip, pan_value: float, accent):
    cx, cy, r = strip.knob_cx, strip.knob_cy, strip.knob_r
    _circle_fill(cx, cy, r, PALETTE["knob_fill"])
    _circle_outline(cx, cy, r, PALETTE["knob_ring"])

    # ponteiro: -1..1 mapeado para -135°..+135° (0 = topo = "12 horas")
    angle = math.radians(90 - pan_value * 135)
    ix = cx + math.cos(angle) * (r - 6)
    iy = cy + math.sin(angle) * (r - 6)
    _line(cx, cy, ix, iy, accent, thickness=2.2)
    _circle_fill(cx, cy, 2.2, accent)

    label = f"{pan_value * 100:+.0f}" if abs(pan_value) > 0.005 else "C"
    _txt(label, cx - STRIP_W / 2, cy - r - 13, 9.5, PALETTE["knob_txt"], center_w=STRIP_W)


def _draw_fader(strip, volume: float, selected: bool):
    tx, ty = strip.fader_track_x, strip.fader_track_y
    tw, th = strip.fader_track_w, strip.fader_track_h
    _round_rect(tx, ty, tw, th, PALETTE["fader_track"], radius=3)

    fill_h = th * max(0.0, min(1.0, volume))
    _round_rect(tx, ty, tw, fill_h, PALETTE["fader_fill"], radius=3)

    cap_y = ty + fill_h - 7
    cap_x = strip.fader_track_x + tw / 2 - (strip.fader_track_w if False else 0)
    cap_w = STRIP_W - 24
    cap_x0 = strip.knob_cx - cap_w / 2
    cap_col = PALETTE["fader_cap_selected"] if selected else PALETTE["fader_cap"]
    _round_rect(cap_x0, cap_y, cap_w, 14, cap_col, radius=4)
    _rect(cap_x0 + 4, cap_y + 6, cap_w - 8, 1.4, darken(cap_col[:3], 0.25) + (1.0,))

    db = (volume - 1.0) * 60.0 if volume < 1.0 else 0.0
    label = "0.0" if volume >= 0.999 else f"{db:.1f}"
    _txt(label, cap_x0, cap_y + 17, 8.5, PALETTE["header_txt_dim"], center_w=cap_w)


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


def _draw_strip(strip, ch, index: int, active_index: int, is_playing_selected: bool):
    selected = index == active_index
    alt = index % 2 == 1
    x0, x1 = strip.x, strip.x + STRIP_W - 8

    from .mixer_strip_theme import strip_bg_for
    bg = strip_bg_for(ch.mute, alt)
    body_top = strip.header_y + HEADER_H
    body_bottom = strip.footer_y - 6
    _round_rect(x0, body_bottom, x1 - x0, body_top - body_bottom, bg, radius=6)

    if selected and is_playing_selected:
        glow = PALETTE["strip_selected_glow"]
        pad = 2
        _round_rect(x0 - pad, body_bottom - pad, (x1 - x0) + 2 * pad,
                     (body_top - body_bottom) + 2 * pad, glow, radius=7)
        _round_rect(x0, body_bottom, x1 - x0, body_top - body_bottom, bg, radius=6)

    # header: chip de cor + número + nome
    header_col = PALETTE["header_bg"]
    _round_rect(x0, strip.header_y, x1 - x0, HEADER_H, header_col, radius=6)
    chip_col = tuple(ch.color) + (1.0,)
    _round_rect(x0 + 6, strip.header_y + HEADER_H / 2 - 4, 8, 8, chip_col, radius=2)
    number = str(getattr(ch, "vse_channel", index + 1))
    _txt(number, x0 + 18, strip.header_y + HEADER_H / 2 - 4, 10, PALETTE["header_txt"])
    name = ch.name if len(ch.name) <= 9 else ch.name[:8] + "…"
    _txt(name, x0, strip.header_y - 12, 9, PALETTE["header_txt_dim"], center_w=(x1 - x0))

    accent = chip_col if not ch.mute else darken(tuple(ch.color), 0.4) + (1.0,)
    _draw_knob(strip, getattr(ch, "pan", 0.0), accent)
    _draw_fader(strip, getattr(ch, "volume", 0.78), selected)

    level = max(0.0, min(1.0, getattr(ch, "meter_level", 0.0))) if not ch.mute else 0.0
    pan = getattr(ch, "pan", 0.0)
    level_l = level * min(1.0, 1.0 - max(pan, 0.0))
    level_r = level * min(1.0, 1.0 + min(pan, 0.0))
    clipping = level >= 0.999
    _draw_meter(strip, level_l, level_r, clipping)

    # rodapé M/S
    mute_col = PALETTE["mute_on"] if ch.mute else PALETTE["mute_off"]
    solo_col = PALETTE["solo_on"] if ch.solo else PALETTE["solo_off"]
    _round_rect(strip.mute_x, strip.footer_y, strip.btn_w, strip.btn_h, mute_col, radius=4)
    _txt("M", strip.mute_x, strip.footer_y + strip.btn_h / 2 - 4, 9.5, PALETTE["btn_txt"], center_w=strip.btn_w)
    _round_rect(strip.solo_x, strip.footer_y, strip.btn_w, strip.btn_h, solo_col, radius=4)
    txt_col = PALETTE["btn_txt_on_dark"] if ch.solo else PALETTE["btn_txt"]
    _txt("S", strip.solo_x, strip.footer_y + strip.btn_h / 2 - 4, 9.5, txt_col, center_w=strip.btn_w)


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
    geo = panel_geometry(region, rack.channels)
    px, py, panel_w, panel_h = geo["px"], geo["py"], geo["panel_w"], geo["panel_h"]
    channels = geo["channels"]

    gpu.state.blend_set('ALPHA')

    _round_rect(px - 1, py - 1, panel_w + 2, panel_h + 2, PALETTE["border"])
    _round_rect(px, py, panel_w, panel_h, PALETTE["panel_bg"])
    _txt("Mixer", px + 8, py + panel_h - 8 - 10, 10.5, PALETTE["header_txt"])

    if not channels:
        _txt("Nenhum canal", px + 8, py + panel_h / 2, 10.5, PALETTE["empty_txt"])
        gpu.state.blend_set('NONE')
        return

    for strip, ch in zip(geo["strips"], channels):
        is_selected_playing = getattr(ch, "meter_level", 0.0) > 0.02 and not ch.mute
        _draw_strip(strip, ch, strip.index, rack.active_channel_index, is_selected_playing)

    gpu.state.blend_set('NONE')