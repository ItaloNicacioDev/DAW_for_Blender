# modules/channel_rack/mixer_strip_geometry.py
"""
Geometria das channel strips do mixer -- um único lugar que calcula
onde cada elemento (header, knob, trilho do fader, cap, medidor,
botões M/S) fica na tela, usado tanto por `mixer_strip_draw.py`
(desenho) quanto por `mixer_strip_operator.py` (hit-test), pra nunca
ficarem dessincronizados -- mesmo princípio do `_panel_geometry` que já
existe em `overlay.py` para o step grid.

Ancoragem: canto inferior ESQUERDO da área do Sequencer (o step grid
de `overlay.py` já ocupa o canto inferior direito -- ver seu docstring
-- então os dois podem conviver na mesma tela sem se sobrepor).
"""
from __future__ import annotations

from typing import List, NamedTuple, Optional, Sequence

MARGIN = 16
STRIP_W = 74
STRIP_GAP = 3
MAX_VISIBLE_STRIPS = 10

HEADER_H = 30
DOT_R = 3.0
DOT_GAP = 9
KNOB_D = 34
KNOB_MARGIN_TOP = 10
FADER_TOP_GAP = 70          # espaço "rack de inserts" vazio acima do fader, como na referência
FADER_TRACK_H = 190
FADER_TRACK_W = 8
FADER_CAP_H = 14
FADER_CAP_W = STRIP_W - 24
METER_W = 14
METER_GAP = 6
FOOTER_GAP = 8
BTN_H = 18
FOOTER_H = BTN_H + 10

CORNER_R = 8


class StripRect(NamedTuple):
    index: int
    x: float
    header_y: float
    dot_cx: float
    dot_cy: float
    knob_cx: float
    knob_cy: float
    knob_r: float
    fader_track_x: float
    fader_track_y: float
    fader_track_w: float
    fader_track_h: float
    meter_x: float
    meter_y: float
    meter_w: float
    meter_h: float
    mute_x: float
    solo_x: float
    footer_y: float
    btn_w: float
    btn_h: float


def panel_geometry(region, channels: Sequence) -> dict:
    """Calcula o retângulo do painel + o rect de cada strip visível."""
    visible = list(channels)[:MAX_VISIBLE_STRIPS]
    n = max(len(visible), 1)

    body_h = HEADER_H + DOT_GAP + KNOB_MARGIN_TOP + KNOB_D + FADER_TOP_GAP + FADER_TRACK_H + FOOTER_GAP + FOOTER_H
    panel_w = n * STRIP_W + (n - 1) * STRIP_GAP + 16 if visible else 220
    panel_h = body_h + 16

    px = MARGIN
    py = MARGIN

    strips: List[StripRect] = []
    sx = px + 8
    body_bottom = py + 8
    for i in range(len(visible)):
        header_y = py + panel_h - 8 - HEADER_H
        dot_cy = header_y - DOT_GAP
        dot_cx = sx + STRIP_W / 2
        knob_cy = dot_cy - KNOB_MARGIN_TOP - KNOB_D / 2
        knob_cx = sx + STRIP_W / 2

        fader_track_y = knob_cy - KNOB_D / 2 - FADER_TOP_GAP - FADER_TRACK_H
        fader_track_x = sx + STRIP_W / 2 - FADER_TRACK_W / 2

        meter_x = sx + STRIP_W - METER_W - 6
        meter_y = fader_track_y
        meter_h = FADER_TRACK_H

        footer_y = body_bottom
        btn_w = (STRIP_W - 16 - 4) / 2
        mute_x = sx + 8
        solo_x = mute_x + btn_w + 4

        strips.append(StripRect(
            index=i, x=sx, header_y=header_y,
            dot_cx=dot_cx, dot_cy=dot_cy,
            knob_cx=knob_cx, knob_cy=knob_cy, knob_r=KNOB_D / 2,
            fader_track_x=fader_track_x, fader_track_y=fader_track_y,
            fader_track_w=FADER_TRACK_W, fader_track_h=FADER_TRACK_H,
            meter_x=meter_x, meter_y=meter_y, meter_w=METER_W, meter_h=meter_h,
            mute_x=mute_x, solo_x=solo_x, footer_y=footer_y,
            btn_w=btn_w, btn_h=BTN_H,
        ))
        sx += STRIP_W + STRIP_GAP

    return {
        "channels": visible,
        "px": px, "py": py, "panel_w": panel_w, "panel_h": panel_h,
        "strips": strips,
    }


def hit_test(mx: float, my: float, region, channels: Sequence) -> Optional[tuple]:
    """Retorna (kind, strip_index) ou (kind, strip_index, extra) para o
    elemento sob o cursor, ou None se estiver fora do painel.

    kind ∈ {'PANEL', 'HEADER', 'KNOB', 'FADER', 'MUTE', 'SOLO'}
    """
    geo = panel_geometry(region, channels)
    px, py = geo["px"], geo["py"]
    panel_w, panel_h = geo["panel_w"], geo["panel_h"]

    if not (px <= mx <= px + panel_w and py <= my <= py + panel_h):
        return None

    for strip in geo["strips"]:
        x0, x1 = strip.x, strip.x + STRIP_W - 8
        if not (x0 <= mx <= x1):
            continue

        if strip.header_y <= my <= strip.header_y + HEADER_H:
            return ("HEADER", strip.index)

        dx = mx - strip.knob_cx
        dy = my - strip.knob_cy
        if dx * dx + dy * dy <= strip.knob_r * strip.knob_r:
            return ("KNOB", strip.index)

        fx0 = strip.fader_track_x - 10
        fx1 = strip.fader_track_x + strip.fader_track_w + 10
        if fx0 <= mx <= fx1 and strip.fader_track_y <= my <= strip.fader_track_y + strip.fader_track_h:
            return ("FADER", strip.index)

        if strip.footer_y <= my <= strip.footer_y + strip.btn_h:
            if strip.mute_x <= mx <= strip.mute_x + strip.btn_w:
                return ("MUTE", strip.index)
            if strip.solo_x <= mx <= strip.solo_x + strip.btn_w:
                return ("SOLO", strip.index)

        return ("PANEL", strip.index)

    return ("PANEL", -1)