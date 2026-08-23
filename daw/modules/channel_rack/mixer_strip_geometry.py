# modules/channel_rack/mixer_strip_geometry.py
"""
Geometria das channel strips do mixer -- um único lugar que calcula
onde cada elemento (barra de título, botão de minimizar, alça de
redimensionar, header, knob, trilho do fader, cap, medidor, botões
M/S) fica na tela, usado tanto por `mixer_strip_draw.py` (desenho)
quanto por `mixer_strip_operator.py` (hit-test), pra nunca ficarem
dessincronizados -- mesmo princípio do `_panel_geometry` que já existe
em `overlay.py` para o step grid.

Posição e tamanho são controlados pelo usuário (ver properties.py):
  - `rack.overlay_pos_x` / `overlay_pos_y`: arraste a barra de título.
  - `rack.overlay_scale_x` / `overlay_scale_y`: **independentes** --
    arraste a alça no canto inferior direito na horizontal pra mudar
    só a largura, na vertical pra mudar só a altura (ou na diagonal
    pra mudar as duas, como uma janela normal).
  - `rack.overlay_collapsed`: clique no botão "–" da barra de título
    pra minimizar (só a barra de título fica visível).
"""
from __future__ import annotations

from typing import List, NamedTuple, Optional, Sequence

# --- Valores BASE (em pixels, escala 1.0) -- larguras usam scale_x,
# alturas usam scale_y, então redimensionar horizontal e vertical são
# independentes um do outro. ---
STRIP_W = 74
STRIP_GAP = 3
MAX_VISIBLE_STRIPS = 10

TITLE_H = 20
COLLAPSE_BTN_W = 18
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
SCALE_MAX = 2.5


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
                    scale_x: float = 1.0, scale_y: float = 1.0,
                    collapsed: bool = False) -> dict:
    """Calcula o retângulo do painel (na posição/escala do usuário) +
    o rect de cada strip visível, tudo em pixels de tela."""
    sx_scale = clamp_scale(scale_x)
    sy_scale = clamp_scale(scale_y)
    # usado só pra coisas que não faz sentido esticar de forma não
    # uniforme (raio de canto, espessura de linha, fonte): a menor das
    # duas escalas, pra nunca "vazar" pra fora do card.
    s = min(sx_scale, sy_scale)

    visible = list(channels)[:MAX_VISIBLE_STRIPS]
    n = max(len(visible), 1)

    strip_w = STRIP_W * sx_scale
    strip_gap = STRIP_GAP * sx_scale
    title_h = TITLE_H * sy_scale
    header_h = HEADER_H * sy_scale
    dot_gap = DOT_GAP * sy_scale
    knob_d = KNOB_D * s
    knob_margin_top = KNOB_MARGIN_TOP * sy_scale
    fader_top_gap = FADER_TOP_GAP * sy_scale
    fader_track_h = FADER_TRACK_H * sy_scale
    fader_track_w = max(4.0, FADER_TRACK_W * sx_scale)
    fader_cap_h = FADER_CAP_H * sy_scale
    meter_w = max(6.0, METER_W * sx_scale)
    footer_gap = FOOTER_GAP * sy_scale
    btn_h = BTN_H * sy_scale
    footer_h = btn_h + 10 * sy_scale
    pad_x = 8 * sx_scale
    pad_y = 8 * sy_scale

    body_h = header_h + dot_gap + knob_margin_top + knob_d + fader_top_gap + fader_track_h + footer_gap + footer_h
    panel_w = (n * strip_w + (n - 1) * strip_gap + 2 * pad_x) if visible else 220 * sx_scale
    panel_h = title_h if collapsed else (body_h + 2 * pad_y + title_h)

    px = pos_x
    py = pos_y

    strips: List[StripRect] = []
    if not collapsed:
        sxp = px + pad_x
        body_bottom = py + pad_y
        for i in range(len(visible)):
            header_y = py + panel_h - title_h - pad_y - header_h
            dot_cy = header_y - dot_gap
            dot_cx = sxp + strip_w / 2
            knob_cy = dot_cy - knob_margin_top - knob_d / 2
            knob_cx = sxp + strip_w / 2

            fader_track_y = knob_cy - knob_d / 2 - fader_top_gap - fader_track_h
            fader_track_x = sxp + strip_w / 2 - fader_track_w / 2

            meter_x = sxp + strip_w - meter_w - 6 * sx_scale
            meter_y = fader_track_y
            meter_h = fader_track_h

            footer_y = body_bottom
            btn_w = (strip_w - 16 * sx_scale - 4 * sx_scale) / 2
            mute_x = sxp + 8 * sx_scale
            solo_x = mute_x + btn_w + 4 * sx_scale

            strips.append(StripRect(
                index=i, x=sxp, strip_w=strip_w, header_y=header_y, header_h=header_h,
                dot_cx=dot_cx, dot_cy=dot_cy, dot_r=DOT_R * s,
                knob_cx=knob_cx, knob_cy=knob_cy, knob_r=knob_d / 2,
                fader_track_x=fader_track_x, fader_track_y=fader_track_y,
                fader_track_w=fader_track_w, fader_track_h=fader_track_h, fader_cap_h=fader_cap_h,
                meter_x=meter_x, meter_y=meter_y, meter_w=meter_w, meter_h=meter_h,
                mute_x=mute_x, solo_x=solo_x, footer_y=footer_y,
                btn_w=btn_w, btn_h=btn_h,
            ))
            sxp += strip_w + strip_gap

    title_y = py + panel_h - title_h
    collapse_btn_w = COLLAPSE_BTN_W * s
    collapse_x = px + panel_w - collapse_btn_w - 4 * sx_scale
    grip_size = GRIP_SIZE * s
    grip_x = px + panel_w - grip_size - 3 * sx_scale
    grip_y = py + 3 * sy_scale

    return {
        "channels": visible,
        "px": px, "py": py, "panel_w": panel_w, "panel_h": panel_h,
        "scale": s, "scale_x": sx_scale, "scale_y": sy_scale,
        "collapsed": collapsed,
        "title_y": title_y, "title_h": title_h,
        "collapse_x": collapse_x, "collapse_btn_w": collapse_btn_w,
        "grip_x": grip_x, "grip_y": grip_y, "grip_size": grip_size,
        "strips": strips,
    }


def hit_test(mx: float, my: float, region, channels: Sequence, pos_x: float = 16,
             pos_y: float = 16, scale_x: float = 1.0, scale_y: float = 1.0,
             collapsed: bool = False) -> Optional[tuple]:
    """Retorna (kind, strip_index) para o elemento sob o cursor, ou
    None se estiver fora do painel.

    kind ∈ {'PANEL', 'TITLEBAR', 'COLLAPSE', 'GRIP', 'HEADER', 'KNOB',
             'FADER', 'MUTE', 'SOLO'}
    """
    geo = panel_geometry(region, channels, pos_x, pos_y, scale_x, scale_y, collapsed)
    px, py = geo["px"], geo["py"]
    panel_w, panel_h = geo["panel_w"], geo["panel_h"]

    if not (px <= mx <= px + panel_w and py <= my <= py + panel_h):
        return None

    cx0, cw = geo["collapse_x"], geo["collapse_btn_w"]
    if geo["title_y"] <= my <= geo["title_y"] + geo["title_h"] and cx0 <= mx <= cx0 + cw:
        return ("COLLAPSE", -1)

    if not collapsed:
        gx, gy, gs = geo["grip_x"], geo["grip_y"], geo["grip_size"]
        if gx <= mx <= gx + gs and gy <= my <= gy + gs:
            return ("GRIP", -1)

    if geo["title_y"] <= my <= geo["title_y"] + geo["title_h"]:
        return ("TITLEBAR", -1)

    if collapsed:
        return ("PANEL", -1)

    for strip in geo["strips"]:
        x0, x1 = strip.x, strip.x + strip.strip_w - 8 * geo["scale_x"]
        if not (x0 <= mx <= x1):
            continue

        if strip.header_y <= my <= strip.header_y + strip.header_h:
            return ("HEADER", strip.index)

        dx = mx - strip.knob_cx
        dy = my - strip.knob_cy
        if dx * dx + dy * dy <= strip.knob_r * strip.knob_r:
            return ("KNOB", strip.index)

        pad = 10 * geo["scale_x"]
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