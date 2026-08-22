# modules/channel_rack/mixer_strip_geometry.py
"""
Geometria das channel strips do mixer -- um único lugar que calcula
onde cada elemento (barra de título, alça de redimensionar, header,
knob, trilho do fader, cap, medidor, botões M/S) fica na tela, usado
tanto por `mixer_strip_draw.py` (desenho) quanto por
`mixer_strip_operator.py` (hit-test), pra nunca ficarem
dessincronizados -- mesmo princípio do `_panel_geometry` que já existe
em `overlay.py` para o step grid.

Posição e tamanho são controlados pelo usuário (`rack.overlay_pos_x`,
`rack.overlay_pos_y`, `rack.overlay_scale` -- ver properties.py):
arraste a barra de título para mover, arraste a alça no canto inferior
direito para redimensionar. Tudo aqui recebe `pos_x/pos_y/scale` em vez
de usar uma margem fixa, então o painel pode ficar em qualquer canto
da área do Sequencer.
"""
from __future__ import annotations

from typing import List, NamedTuple, Optional, Sequence

# --- Valores BASE (em pixels, escala 1.0) -- tudo é multiplicado por
# `scale` em tempo de desenho/hit-test, então redimensionar é só isso:
# um fator aplicado a estas constantes. ---
STRIP_W = 74
STRIP_GAP = 3
MAX_VISIBLE_STRIPS = 10

TITLE_H = 20
GRIP_SIZE = 14

HEADER_H = 30
DOT_R = 3.0
DOT_GAP = 9
KNOB_D = 34
KNOB_MARGIN_TOP = 10
FADER_TOP_GAP = 70          # espaço "rack de inserts" vazio acima do fader
FADER_TRACK_H = 190
FADER_TRACK_W = 8
FADER_CAP_H = 14
METER_W = 14
FOOTER_GAP = 8
BTN_H = 18
FOOTER_H = BTN_H + 10

CORNER_R = 8

SCALE_MIN = 0.6
SCALE_MAX = 2.0


class StripRect(NamedTuple):
    index: int
    x: float
    strip_w: float
    header_y: float
    header_h: float
    dot_cx: float
    dot_cy: float
    dot_r: float
    knob_cx: float
    knob_cy: float
    knob_r: float
    fader_track_x: float
    fader_track_y: float
    fader_track_w: float
    fader_track_h: float
    fader_cap_h: float
    meter_x: float
    meter_y: float
    meter_w: float
    meter_h: float
    mute_x: float
    solo_x: float
    footer_y: float
    btn_w: float
    btn_h: float


def clamp_scale(scale: float) -> float:
    return max(SCALE_MIN, min(SCALE_MAX, scale))


def panel_geometry(region, channels: Sequence, pos_x: float = 16, pos_y: float = 16,
                    scale: float = 1.0) -> dict:
    """Calcula o retângulo do painel (na posição/escala do usuário) +
    o rect de cada strip visível, tudo em pixels de tela."""
    scale = clamp_scale(scale)
    s = scale

    visible = list(channels)[:MAX_VISIBLE_STRIPS]
    n = max(len(visible), 1)

    strip_w = STRIP_W * s
    strip_gap = STRIP_GAP * s
    title_h = TITLE_H * s
    header_h = HEADER_H * s
    dot_gap = DOT_GAP * s
    knob_d = KNOB_D * s
    knob_margin_top = KNOB_MARGIN_TOP * s
    fader_top_gap = FADER_TOP_GAP * s
    fader_track_h = FADER_TRACK_H * s
    fader_track_w = max(4.0, FADER_TRACK_W * s)
    fader_cap_h = FADER_CAP_H * s
    meter_w = max(6.0, METER_W * s)
    footer_gap = FOOTER_GAP * s
    btn_h = BTN_H * s
    footer_h = btn_h + 10 * s
    pad = 8 * s

    body_h = header_h + dot_gap + knob_margin_top + knob_d + fader_top_gap + fader_track_h + footer_gap + footer_h
    panel_w = (n * strip_w + (n - 1) * strip_gap + 2 * pad) if visible else 220 * s
    panel_h = body_h + 2 * pad + title_h

    px = pos_x
    py = pos_y

    strips: List[StripRect] = []
    sx = px + pad
    body_bottom = py + pad
    for i in range(len(visible)):
        header_y = py + panel_h - title_h - pad - header_h
        dot_cy = header_y - dot_gap
        dot_cx = sx + strip_w / 2
        knob_cy = dot_cy - knob_margin_top - knob_d / 2
        knob_cx = sx + strip_w / 2

        fader_track_y = knob_cy - knob_d / 2 - fader_top_gap - fader_track_h
        fader_track_x = sx + strip_w / 2 - fader_track_w / 2

        meter_x = sx + strip_w - meter_w - 6 * s
        meter_y = fader_track_y
        meter_h = fader_track_h

        footer_y = body_bottom
        btn_w = (strip_w - 16 * s - 4 * s) / 2
        mute_x = sx + 8 * s
        solo_x = mute_x + btn_w + 4 * s

        strips.append(StripRect(
            index=i, x=sx, strip_w=strip_w, header_y=header_y, header_h=header_h,
            dot_cx=dot_cx, dot_cy=dot_cy, dot_r=DOT_R * s,
            knob_cx=knob_cx, knob_cy=knob_cy, knob_r=knob_d / 2,
            fader_track_x=fader_track_x, fader_track_y=fader_track_y,
            fader_track_w=fader_track_w, fader_track_h=fader_track_h, fader_cap_h=fader_cap_h,
            meter_x=meter_x, meter_y=meter_y, meter_w=meter_w, meter_h=meter_h,
            mute_x=mute_x, solo_x=solo_x, footer_y=footer_y,
            btn_w=btn_w, btn_h=btn_h,
        ))
        sx += strip_w + strip_gap

    title_y = py + panel_h - title_h
    grip_size = GRIP_SIZE * s
    grip_x = px + panel_w - grip_size - 3 * s
    grip_y = py + 3 * s

    return {
        "channels": visible,
        "px": px, "py": py, "panel_w": panel_w, "panel_h": panel_h,
        "scale": s,
        "title_y": title_y, "title_h": title_h,
        "grip_x": grip_x, "grip_y": grip_y, "grip_size": grip_size,
        "strips": strips,
    }


def hit_test(mx: float, my: float, region, channels: Sequence, pos_x: float = 16,
             pos_y: float = 16, scale: float = 1.0) -> Optional[tuple]:
    """Retorna (kind, strip_index) para o elemento sob o cursor, ou
    None se estiver fora do painel.

    kind ∈ {'PANEL', 'TITLEBAR', 'GRIP', 'HEADER', 'KNOB', 'FADER', 'MUTE', 'SOLO'}
    """
    geo = panel_geometry(region, channels, pos_x, pos_y, scale)
    px, py = geo["px"], geo["py"]
    panel_w, panel_h = geo["panel_w"], geo["panel_h"]

    if not (px <= mx <= px + panel_w and py <= my <= py + panel_h):
        return None

    gx, gy, gs = geo["grip_x"], geo["grip_y"], geo["grip_size"]
    if gx <= mx <= gx + gs and gy <= my <= gy + gs:
        return ("GRIP", -1)

    if geo["title_y"] <= my <= geo["title_y"] + geo["title_h"]:
        return ("TITLEBAR", -1)

    for strip in geo["strips"]:
        x0, x1 = strip.x, strip.x + strip.strip_w - 8 * geo["scale"]
        if not (x0 <= mx <= x1):
            continue

        if strip.header_y <= my <= strip.header_y + strip.header_h:
            return ("HEADER", strip.index)

        dx = mx - strip.knob_cx
        dy = my - strip.knob_cy
        if dx * dx + dy * dy <= strip.knob_r * strip.knob_r:
            return ("KNOB", strip.index)

        pad = 10 * geo["scale"]
        fx0 = strip.fader_track_x - pad
        fx1 = strip.fader_track_x + strip.fader_track_w + pad
        if fx0 <= mx <= fx1 and strip.fader_track_y <= my <= strip.fader_track_y + strip.fader_track_h:
            return ("FADER", strip.index)

        if strip.footer_y <= my <= strip.footer_y + strip.btn_h:
            if strip.mute_x <= mx <= strip.mute_x + strip.btn_w:
                return ("MUTE", strip.index)
            if strip.solo_x <= mx <= strip.solo_x + strip.btn_w:
                return ("SOLO", strip.index)

        return ("PANEL", strip.index)

    return ("PANEL", -1)