# modules/channel_rack/mixer_strip_draw.py
"""
Desenho (GPU + blf) das channel strips do mixer.

[REFINO VISUAL] Reescrito pra dar mais profundidade e polish:
  - sombra suave sob o card inteiro + realce de 1px no topo das strips
    (simula luz vinda de cima, como qualquer UI de DAW/plugin de verdade)
  - fader com cap em "gradiente" (duas bandas: realce em cima, sombra
    embaixo) em vez de um retângulo chapado
  - knob com sombra própria + anel mais grosso e com leve realce
  - medidor de nível estilo LED segmentado (hardware de verdade) em vez
    de uma barra sólida contínua -- mais fácil de ler o nível de
    relance e visualmente mais rico
  - brilho de seleção/tocando em múltiplos anéis com alpha decrescente
    (glow suave) em vez de uma borda sólida única
  - tipografia com mais contraste onde importa (nome do canal, valores)
    e menos onde não importa (rótulos secundários)

Autocontido -- não importa nada de `overlay.py`.
"""
from __future__ import annotations

import math

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

from .colors import darken, lighten
from .mixer_strip_theme import PALETTE, meter_color, METER_SEGMENTS, METER_SEGMENT_GAP
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


def _round_rect_top(x, y, w, h, col, radius=CORNER_R):
    """Retângulo com cantos arredondados só em cima (embaixo reto) --
    usado pra "encaixar" visualmente um elemento no que vem antes dele."""
    r = min(radius, w / 2, h / 2)
    if r <= 0:
        _rect(x, y, w, h, col)
        return
    _rect(x, y, w, h - r, col)
    _rect(x + r, y + h - r, w - 2 * r, r, col)
    corners = [
        (x + w - r, y + h - r, 0, 90),
        (x + r, y + h - r, 90, 180),
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


def _circle_outline(cx, cy, r, col, thickness=1.6, segments=28):
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


def _circle_fill(cx, cy, r, col, segments=28):
    coords = [(cx, cy)]
    for i in range(segments + 1):
        a = math.radians(360 * i / segments)
        coords.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    tris = []
    for i in range(1, len(coords) - 1):
        tris.extend([coords[0], coords[i], coords[i + 1]])
    _tris(tris, col)


def _arc_band(cx, cy, r_out, r_in, a0_deg, a1_deg, col, segments=20):
    """Faixa de anel entre dois raios, de a0_deg a a1_deg (graus, sentido
    matemático padrão) -- usada pro anel/trilho do knob."""
    if segments < 2:
        segments = 2
    a0 = math.radians(a0_deg)
    a1 = math.radians(a1_deg)
    coords = []
    for i in range(segments):
        t0 = a0 + (a1 - a0) * i / segments
        t1 = a0 + (a1 - a0) * (i + 1) / segments
        p0o = (cx + math.cos(t0) * r_out, cy + math.sin(t0) * r_out)
        p1o = (cx + math.cos(t1) * r_out, cy + math.sin(t1) * r_out)
        p0i = (cx + math.cos(t0) * r_in, cy + math.sin(t0) * r_in)
        p1i = (cx + math.cos(t1) * r_in, cy + math.sin(t1) * r_in)
        coords.extend([p0o, p1o, p1i, p0o, p1i, p0i])
    _tris(coords, col)


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
    # [FIX MEDIDOR SEMPRE BRANCO] `blf.draw()` desliga o blend de alpha
    # internamente e não restaura -- qualquer `_rect`/`_round_rect` com
    # cor semitransparente desenhado logo depois de QUALQUER `_txt()`
    # saía 100% opaco em vez de translúcido (foi assim que o medidor
    # LED "apagado", que devia ser um branco quase invisível a 3.5% de
    # opacidade, virava um branco sólido). Restaurar aqui, na função
    # de texto em si, cobre todo mundo que chama `_txt()` neste
    # arquivo, sem precisar caçar cada ponto de chamada.
    gpu.state.blend_set('ALPHA')


def _soft_glow(x0, y0, w, h, col, s, rings=3, radius=CORNER_R):
    """Brilho suave em múltiplos anéis com alpha decrescente, em vez de
    uma borda sólida única -- usado pro estado selecionado/tocando."""
    base_a = col[3] if len(col) > 3 else 1.0
    for i in range(rings, 0, -1):
        pad = i * 1.6 * s
        a = base_a * (0.30 if i == rings else (0.55 if i == 2 else 1.0)) / rings * 1.6
        c = (col[0], col[1], col[2], min(1.0, a))
        _round_rect(x0 - pad, y0 - pad, w + 2 * pad, h + 2 * pad, c, radius=radius + pad * 0.5)


# ------------------------------------------------------------------ #
#  Sub-desenhos de cada elemento da strip
# ------------------------------------------------------------------ #
def _draw_knob(strip, pan_value: float, accent, s: float):
    cx, cy, r = strip.knob_cx, strip.knob_cy, strip.knob_r

    # sombra sutil embaixo do knob (dá volume)
    _circle_fill(cx, cy - 1.2 * s, r * 0.66, PALETTE["knob_shadow"])
    _circle_fill(cx, cy, r * 0.64, PALETTE["knob_fill"])
    # realce no topo do miolo (luz vinda de cima)
    _circle_fill(cx, cy + r * 0.18, r * 0.40, PALETTE["knob_fill_hi"])

    # trilho do knob: anel de 270°, sempre visível como referência de fundo
    ring_out, ring_in = r, r * 0.74
    TRACK_A0, TRACK_A1 = -45.0, 225.0
    _arc_band(cx, cy, ring_out, ring_in, TRACK_A0, TRACK_A1, PALETTE["knob_ring"])

    # arco de valor: preenche do centro (12h = pan 0) até a posição atual
    center_angle = 90.0
    value_angle = 90.0 - max(-1.0, min(1.0, pan_value)) * 135.0
    if abs(pan_value) > 0.01:
        a0, a1 = (value_angle, center_angle) if pan_value >= 0 else (center_angle, value_angle)
        _arc_band(cx, cy, ring_out, ring_in, a0, a1, accent)

    # ponteirinho fino na ponta do arco
    angle = math.radians(value_angle)
    tip_r = ring_in - 1.0 * s
    ix = cx + math.cos(angle) * tip_r
    iy = cy + math.sin(angle) * tip_r
    _line(cx, cy, ix, iy, accent, thickness=1.5 * s)
    _circle_fill(cx, cy, 1.8 * s, accent)

    label = f"{pan_value * 100:+.0f}" if abs(pan_value) > 0.005 else "C"
    _txt(label, cx - strip.strip_w / 2, cy - r - 14 * s, max(7.0, 9.5 * s),
         PALETTE["knob_txt"], center_w=strip.strip_w)


def _draw_fader(strip, volume: float, selected: bool, playing: bool, s: float):
    tx, ty = strip.fader_track_x, strip.fader_track_y
    tw, th = strip.fader_track_w, strip.fader_track_h

    # trilho com leve sombra interna no topo (profundidade)
    _round_rect(tx, ty, tw, th, PALETTE["fader_track"], radius=3 * s)
    _rect(tx, ty + th - 2 * s, tw, 2 * s, PALETTE["fader_track_edge"])

    fill_h = th * max(0.0, min(1.0, volume))
    _round_rect(tx, ty, tw, fill_h, PALETTE["fader_fill"], radius=3 * s)

    cap_h = strip.fader_cap_h
    cap_y = ty + fill_h - cap_h / 2
    cap_w = strip.strip_w - 24 * s
    cap_x0 = strip.knob_cx - cap_w / 2

    if selected:
        cap_col, cap_hi, cap_lo = (PALETTE["fader_cap_selected"], PALETTE["fader_cap_selected_hi"],
                                    PALETTE["fader_cap_selected_lo"])
    else:
        cap_col, cap_hi, cap_lo = PALETTE["fader_cap"], PALETTE["fader_cap_hi"], PALETTE["fader_cap_lo"]

    # linha caindo do cap até a base do trilho -- só quando a strip
    # selecionada está de fato emitindo áudio
    if selected and playing:
        _line(strip.knob_cx, cap_y, strip.knob_cx, ty, PALETTE["fader_cap_selected"], thickness=1.4 * s)

    # cap em "gradiente" -- duas bandas (realce em cima, sombra embaixo)
    # em vez de um bloco chapado, mais parecido com um fader físico
    _round_rect(cap_x0, cap_y, cap_w, cap_h, cap_col, radius=4 * s)
    _round_rect_top(cap_x0, cap_y + cap_h * 0.42, cap_w, cap_h * 0.58, cap_hi, radius=4 * s)
    _rect(cap_x0, cap_y, cap_w, cap_h * 0.22, cap_lo)
    # ranhura central (detalhe de "pegador" de fader físico)
    _rect(cap_x0 + cap_w * 0.18, cap_y + cap_h / 2 - 0.7 * s, cap_w * 0.64, 1.4 * s,
          darken(cap_col[:3], 0.35) + (0.8,))

    db = (volume - 1.0) * 60.0 if volume < 1.0 else 0.0
    label = "0.0" if volume >= 0.999 else f"{db:.1f}"
    _txt(label, cap_x0, cap_y + cap_h + 3 * s, max(7.0, 8.5 * s), PALETTE["header_txt_dim"], center_w=cap_w)


def _draw_insert_area(strip, top_y: float, bottom_y: float, s: float):
    """Área vazia entre o knob e o fader ("rack de inserts" vazio),
    puramente decorativa -- linhas finas igualmente espaçadas."""
    x0 = strip.knob_cx - (strip.strip_w - 24 * s) / 2
    x1 = strip.knob_cx + (strip.strip_w - 24 * s) / 2
    gap = top_y - bottom_y
    if gap <= 4 * s:
        return
    n = 4
    for i in range(1, n + 1):
        y = top_y - gap * i / (n + 1)
        _rect(x0, y, x1 - x0, 1.0, (1.0, 1.0, 1.0, 0.045))


def _draw_meter(strip, level_l: float, level_r: float, clipping: bool, s: float):
    """Medidor estilo LED segmentado -- cada canal (L/R) é uma coluna
    de blocos discretos com um vão fino entre eles, em vez de uma barra
    sólida contínua. Blocos "apagados" ficam num cinza quase invisível
    (referência de escala); blocos "acesos" pegam a cor do limiar
    correspondente (verde/amarelo/vermelho)."""
    # [FIX MEDIDOR SEMPRE BRANCO] Até aqui, `_draw_strip` já tinha
    # chamado `_txt()` (blf.draw) várias vezes antes de chegar aqui
    # (número do canal, nome, "C" do pan) -- e `blf.draw()` desliga o
    # blend de alpha internamente sem restaurar. Sem isso, o branco
    # quase invisível de `PALETTE["meter_led_off"]` (alpha 0.035) era
    # desenhado 100% opaco -- por isso os segmentos "apagados" sempre
    # apareciam como um branco sólido, nunca em cinza escuro, não
    # importa o nível real. `gpu.state.blend_set` é barato de chamar
    # de novo (é só um estado, não recompila shader), então religar
    # aqui é a forma mais segura de garantir isso sem depender da
    # ordem de desenho no resto do arquivo.
    gpu.state.blend_set('ALPHA')

    mx, my, mw, mh = strip.meter_x, strip.meter_y, strip.meter_w, strip.meter_h
    _round_rect(mx - 1.5 * s, my - 1.5 * s, mw + 3 * s, mh + 3 * s, PALETTE["border"], radius=3 * s)
    _rect(mx, my, mw, mh, PALETTE["meter_bg"])

    half = mw / 2 - 1 * s
    seg_h = mh / METER_SEGMENTS
    gap_h = seg_h * METER_SEGMENT_GAP
    block_h = seg_h - gap_h

    from .mixer_strip_theme import LEVEL_GREEN_MAX, LEVEL_YELLOW_MAX

    for offset, level in ((0.0, level_l), (half + 1 * s, level_r)):
        seg_x = mx + offset
        level = max(0.0, min(1.0, level))
        lit_segments = level * METER_SEGMENTS

        for i in range(METER_SEGMENTS):
            seg_level = (i + 1) / METER_SEGMENTS  # nível que este degrau representa
            seg_y = my + i * seg_h + gap_h / 2
            is_lit = i < lit_segments
            # último segmento parcialmente aceso (transição suave em
            # vez de tudo-ou-nada no degrau exato)
            partial = lit_segments - i if (0 < lit_segments - i < 1) else None

            if is_lit or partial:
                col = meter_color(seg_level, clipping and seg_level > LEVEL_YELLOW_MAX)
                if partial is not None:
                    col = meter_color(seg_level, dim=True)
                _rect(seg_x, seg_y, half, block_h, col)
            else:
                _rect(seg_x, seg_y, half, block_h, PALETTE["meter_led_off"])

    # linhas de referência dos limiares
    for thr in (LEVEL_GREEN_MAX, LEVEL_YELLOW_MAX):
        ly = my + mh * thr
        _rect(mx, ly, mw, 1.0, (0.0, 0.0, 0.0, 0.4))

    if clipping:
        _rect(mx, my + mh - 2 * s, mw, 2 * s, PALETTE["meter_clip"])


def _draw_strip(strip, ch, index: int, active_index: int, is_playing_selected: bool, s: float):
    is_selected = getattr(ch, "selected", False)
    alt = index % 2 == 1
    x0, x1 = strip.x, strip.x + strip.strip_w - 8 * s

    from .mixer_strip_theme import strip_bg_for
    bg = strip_bg_for(ch.mute, alt)
    body_top = strip.header_y + strip.header_h
    body_bottom = strip.footer_y - 6 * s

    # sombra suave da própria strip (profundidade contra o painel)
    _round_rect(x0, body_bottom - 1.5 * s, x1 - x0, (body_top - body_bottom) + 1.5 * s,
                PALETTE["panel_shadow"], radius=7 * s)

    if is_selected and is_playing_selected:
        _soft_glow(x0, body_bottom, x1 - x0, body_top - body_bottom,
                   PALETTE["strip_selected_glow"], s, rings=3, radius=7 * s)
    elif is_selected:
        pad = 1.4 * s
        _round_rect(x0 - pad, body_bottom - pad, (x1 - x0) + 2 * pad,
                    (body_top - body_bottom) + 2 * pad, PALETTE["selection_outline"], radius=7 * s)

    _round_rect(x0, body_bottom, x1 - x0, body_top - body_bottom, bg, radius=6 * s)
    # realce de 1px no topo (luz vinda de cima, dá "elevação")
    _rect(x0 + 6 * s, body_top - 1.2 * s, (x1 - x0) - 12 * s, 1.2 * s, PALETTE["strip_top_highlight"])

    # header: fundo mais claro quando selecionado, chip de cor + número + nome
    header_col = PALETTE["header_bg_light"] if is_selected else PALETTE["header_bg"]
    _round_rect(x0, strip.header_y, x1 - x0, strip.header_h, header_col, radius=6 * s)
    chip_col = tuple(ch.color) + (1.0,)
    _round_rect(x0 + 7 * s, strip.header_y + strip.header_h / 2 - 4 * s, 8 * s, 8 * s, chip_col, radius=2.5 * s)
    number = str(getattr(ch, "vse_channel", index + 1))
    _txt(number, x0 + 19 * s, strip.header_y + strip.header_h / 2 - 4 * s, max(7.0, 10 * s), PALETTE["header_txt"])
    name = ch.name if len(ch.name) <= 10 else ch.name[:9] + "…"
    _txt(name, x0, strip.header_y - 13 * s, max(6.0, 9 * s), PALETTE["header_txt_dim"], center_w=(x1 - x0))

    # ponto indicador (verde = audível, apagado = mudo) logo abaixo do header
    dot_col = (0.34, 0.88, 0.40, 1.0) if not ch.mute else (0.32, 0.33, 0.38, 1.0)
    _circle_fill(strip.dot_cx, strip.dot_cy, strip.dot_r, dot_col)

    accent = chip_col if not ch.mute else darken(tuple(ch.color), 0.4) + (1.0,)
    _draw_knob(strip, getattr(ch, "pan", 0.0), accent, s)
    _draw_insert_area(strip, strip.knob_cy - strip.knob_r - 14 * s, strip.fader_track_y + strip.fader_track_h, s)
    _draw_fader(strip, getattr(ch, "volume", 0.78), is_selected, is_playing_selected, s)

    level = max(0.0, min(1.0, getattr(ch, "meter_level", 0.0))) if not ch.mute else 0.0
    pan = getattr(ch, "pan", 0.0)
    level_l = level * min(1.0, 1.0 - max(pan, 0.0))
    level_r = level * min(1.0, 1.0 + min(pan, 0.0))
    clipping = level >= 0.999
    _draw_meter(strip, level_l, level_r, clipping, s)

    # rodapé M/S -- com leve realce no topo do botão pra dar volume
    mute_col, mute_hi = (PALETTE["mute_on"], PALETTE["mute_on_hi"]) if ch.mute else (PALETTE["mute_off"], None)
    solo_col, solo_hi = (PALETTE["solo_on"], PALETTE["solo_on_hi"]) if ch.solo else (PALETTE["solo_off"], None)

    _round_rect(strip.mute_x, strip.footer_y, strip.btn_w, strip.btn_h, mute_col, radius=4 * s)
    if mute_hi:
        _round_rect_top(strip.mute_x, strip.footer_y + strip.btn_h * 0.5, strip.btn_w, strip.btn_h * 0.5, mute_hi, radius=4 * s)
    _txt("M", strip.mute_x, strip.footer_y + strip.btn_h / 2 - 4 * s, max(7.0, 9.5 * s),
         PALETTE["btn_txt"] if not ch.mute else PALETTE["btn_txt_on_dark"], center_w=strip.btn_w)

    _round_rect(strip.solo_x, strip.footer_y, strip.btn_w, strip.btn_h, solo_col, radius=4 * s)
    if solo_hi:
        _round_rect_top(strip.solo_x, strip.footer_y + strip.btn_h * 0.5, strip.btn_w, strip.btn_h * 0.5, solo_hi, radius=4 * s)
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
    scale_x = getattr(rack, "overlay_scale_x", 1.0)
    scale_y = getattr(rack, "overlay_scale_y", 1.0)
    collapsed = getattr(rack, "overlay_collapsed", False)
    geo = panel_geometry(region, rack.channels, pos_x, pos_y, scale_x, scale_y, collapsed)
    px, py, panel_w, panel_h = geo["px"], geo["py"], geo["panel_w"], geo["panel_h"]
    channels = geo["channels"]
    s = geo["scale"]

    gpu.state.blend_set('ALPHA')

    # sombra do card inteiro (profundidade contra o fundo do Sequencer)
    _round_rect(px - 3, py - 4, panel_w + 6, panel_h + 6, PALETTE["panel_shadow"], radius=8 * s)
    _round_rect(px - 1, py - 1, panel_w + 2, panel_h + 2, PALETTE["border"])
    _round_rect(px, py, panel_w, panel_h, PALETTE["panel_bg"])

    # barra de título -- arrastável, com leve realce no topo
    title_y = geo["title_y"]
    _round_rect(px, title_y, panel_w, geo["title_h"], PALETTE["header_bg"], radius=6 * s)
    _rect(px + 4 * s, title_y + geo["title_h"] - 1 * s, panel_w - 8 * s, 1 * s, PALETTE["strip_top_highlight"])
    label = "Mixer" if collapsed else "Mixer  ·  arraste para mover"
    _txt(label, px + 9 * s, title_y + geo["title_h"] / 2 - 4 * s,
         max(7.0, 9.5 * s), PALETTE["header_txt_dim"])

    # botão de minimizar/restaurar
    cx0, cw = geo["collapse_x"], geo["collapse_btn_w"]
    cy0 = title_y + 3 * s
    ch_ = geo["title_h"] - 6 * s
    _round_rect(cx0, cy0, cw, ch_, PALETTE["knob_fill"], radius=3 * s)
    glyph = "+" if collapsed else "–"
    _txt(glyph, cx0, cy0 + ch_ / 2 - 5 * s, max(8.0, 11 * s), PALETTE["header_txt"], center_w=cw)

    if collapsed:
        gpu.state.blend_set('NONE')
        return

    # alça de redimensionar, canto inferior direito
    gx, gy, gs = geo["grip_x"], geo["grip_y"], geo["grip_size"]
    for i in range(3):
        off = i * gs / 3.0
        _line(gx + off, gy, gx + gs, gy + gs - off, PALETTE["header_txt_soft"], thickness=1.3 * s)

    if not channels:
        _txt("Nenhum canal", px + 9 * s, py + panel_h / 2, max(7.0, 10.5 * s), PALETTE["empty_txt"])
        gpu.state.blend_set('NONE')
        return

    for strip, ch in zip(geo["strips"], channels):
        is_selected_playing = getattr(ch, "meter_level", 0.0) > 0.02 and not ch.mute
        _draw_strip(strip, ch, strip.index, rack.active_channel_index, is_selected_playing, s)

    gpu.state.blend_set('NONE')