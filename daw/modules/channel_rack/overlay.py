# modules/channel_rack/overlay.py
"""
Overlay do Channel Rack desenhado direto na área do Sequencer (gpu/blf),
ancorado fixo no canto inferior direito -- reproduz o card escuro com
chips de cor, botões M/S e grade de steps da imagem de referência, sem
depender dos widgets nativos limitados do `bpy.types.Panel`.

Diferença para `ui/beat_grid.py` (o protótipo antigo que inspirou este
visual): aquele módulo abre uma **janela nova** e usa um PropertyGroup
próprio (`scene.beat_grid`) desconectado do resto da DAW. Este overlay:

  - desenha DENTRO da área SEQUENCE_EDITOR que já existe no addon (não
    abre janela nenhuma);
  - lê/escreve os dados reais do rack (`scene.daw_channel_rack`), os
    mesmos que o painel em `ui.py` edita -- um único dado, duas
    visualizações;
  - fica sempre ancorado no canto inferior direito da área, recalculado
    a cada redraw a partir de `region.width/height`, então acompanha
    redimensionamento da janela;
  - só consome eventos de mouse que caem dentro do próprio retângulo
    (`PASS_THROUGH` para todo o resto), então não bloqueia a edição
    normal do Sequencer por baixo.

Arquitetura:
    Um único `Operator` modal (`DAW_OT_ChannelRackOverlay`) cuida do
    draw_handler + hit-test + eventos. `ensure_started()` /
    `force_stop()` são chamados por `register.py` para ligar/desligar
    o overlay junto com o addon, sem exigir clique manual do usuário.
"""
from __future__ import annotations

import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader

from .colors import lighten, darken

# ═══════════════════════════════════════════════════════════════
#  LAYOUT (proporções aproximadas da imagem de referência)
# ═══════════════════════════════════════════════════════════════

MARGIN = 16          # distância do canto da área
PANEL_W = 460
HEADER_H = 34
ROW_H = 32
ROW_GAP = 3
FOOTER_H = 10
CHIP_W = 14          # chip de cor sólida
NAME_W = 108
BTN_SIDE = 22
BTN_GAP = 4
STEP_GAP = 3
MAX_VISIBLE_STEPS = 16
MAX_VISIBLE_ROWS = 8   # como no mockup -- rola implicitamente se houver mais

CORNER_R = 8          # raio dos cantos arredondados do card
CORNER_SEG = 6        # segmentos por canto (suave o bastante em 8px)

PALETTE = {
    'panel_bg':    (0.070, 0.073, 0.098, 0.97),
    'header_bg':   (0.100, 0.104, 0.145, 1.0),
    'header_txt':  (0.860, 0.865, 0.920, 1.0),
    'border':      (0.020, 0.021, 0.030, 1.0),
    'row_even':    (0.093, 0.097, 0.130, 1.0),
    'row_odd':     (0.083, 0.087, 0.118, 1.0),
    'row_muted':   (0.055, 0.057, 0.078, 1.0),
    'name_txt':    (0.820, 0.825, 0.880, 1.0),
    'name_muted':  (0.400, 0.404, 0.450, 1.0),
    'mute_on':     (0.860, 0.300, 0.300, 1.0),
    'mute_off':    (0.150, 0.153, 0.200, 1.0),
    'solo_on':     (0.920, 0.780, 0.150, 1.0),
    'solo_off':    (0.150, 0.153, 0.200, 1.0),
    'btn_txt':     (0.900, 0.900, 0.920, 1.0),
    'step_off':    (0.135, 0.138, 0.180, 1.0),
    'step_off_alt':(0.118, 0.121, 0.160, 1.0),
    'step_cur':    (1.000, 0.830, 0.220, 1.0),
    'group_line':  (0.030, 0.031, 0.045, 0.9),
    'empty_txt':   (0.480, 0.485, 0.540, 1.0),
}

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
    _tris([(x, y), (x + w, y), (x + w, y + h), (x, y), (x + w, y + h), (x, y + h)], col)


def _rect_outline(x, y, w, h, col, thickness=1.0):
    _rect(x, y, w, thickness, col)
    _rect(x, y + h - thickness, w, thickness, col)
    _rect(x, y, thickness, h, col)
    _rect(x + w - thickness, y, thickness, h, col)


def _round_rect(x, y, w, h, col, radius=CORNER_R):
    """Retângulo com cantos arredondados, aproximado por um leque de
    triângulos em cada canto -- gpu do Blender não tem primitiva nativa
    de rounded-rect, então isto é montado à mão a partir de retângulos
    (miolo) + quartos de círculo (cantos)."""
    import math
    r = min(radius, w / 2, h / 2)
    if r <= 0:
        _rect(x, y, w, h, col)
        return

    # Miolo em cruz (evita reconstruir tudo com triangulação genérica)
    _rect(x + r, y, w - 2 * r, h, col)
    _rect(x, y + r, r, h - 2 * r, col)
    _rect(x + w - r, y + r, r, h - 2 * r, col)

    corners = [
        (x + w - r, y + h - r, 0, 90),    # topo-direita
        (x + r, y + h - r, 90, 180),      # topo-esquerda
        (x + r, y + r, 180, 270),         # baixo-esquerda
        (x + w - r, y + r, 270, 360),     # baixo-direita
    ]
    for cx, cy, a0, a1 in corners:
        coords = [(cx, cy)]
        steps = CORNER_SEG
        for i in range(steps + 1):
            ang = math.radians(a0 + (a1 - a0) * i / steps)
            coords.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
        tris = []
        for i in range(1, len(coords) - 1):
            tris.extend([coords[0], coords[i], coords[i + 1]])
        if tris:
            _tris(tris, col)


def _txt(text, x, y, size, col, font_id=0):
    blf.size(font_id, size)
    blf.color(font_id, *col)
    blf.position(font_id, x, y, 0)
    blf.draw(font_id, text)


def _txt_dims(text, size, font_id=0):
    blf.size(font_id, size)
    return blf.dimensions(font_id, text)


# ═══════════════════════════════════════════════════════════════
#  GEOMETRIA DO PAINEL (compartilhada entre draw e hit-test)
# ═══════════════════════════════════════════════════════════════

def _panel_geometry(region, rack):
    """Calcula o retângulo do painel ancorado no canto inferior direito
    e devolve tudo que draw()/hit_test() precisam, num único lugar --
    evita os dois ficarem dessincronizados."""
    channels = list(rack.channels)[:MAX_VISIBLE_ROWS]
    n_rows = max(len(channels), 1)
    n_steps = min(rack.step_count, MAX_VISIBLE_STEPS)

    body_h = n_rows * (ROW_H + ROW_GAP) - ROW_GAP if channels else ROW_H
    panel_h = HEADER_H + body_h + FOOTER_H
    panel_w = PANEL_W

    px = region.width - MARGIN - panel_w
    py = MARGIN

    step_area_x = px + CHIP_W + 6 + NAME_W + (BTN_SIDE + BTN_GAP) * 2 + 6
    step_area_w = (px + panel_w - 8) - step_area_x
    step_w = step_area_w / n_steps if n_steps else 0

    return {
        'channels': channels,
        'n_steps': n_steps,
        'px': px, 'py': py, 'panel_w': panel_w, 'panel_h': panel_h,
        'step_area_x': step_area_x, 'step_w': step_w,
    }


# ═══════════════════════════════════════════════════════════════
#  DESENHO
# ═══════════════════════════════════════════════════════════════

def _draw_channel_rack_overlay():
    context = bpy.context
    if context.area is None or context.area.type != 'SEQUENCE_EDITOR':
        return
    scene = context.scene
    if scene is None or not hasattr(scene, "daw_channel_rack"):
        return
    rack = scene.daw_channel_rack
    if not getattr(rack, "show_corner_overlay", True):
        return

    region = context.region
    geo = _panel_geometry(region, rack)
    px, py = geo['px'], geo['py']
    panel_w, panel_h = geo['panel_w'], geo['panel_h']
    channels = geo['channels']
    n_steps = geo['n_steps']
    step_area_x, step_w = geo['step_area_x'], geo['step_w']

    is_playing = bool(getattr(context.screen, "is_animation_playing", False))
    cur_step = rack.current_step % max(rack.step_count, 1) if rack.step_count else 0

    gpu.state.blend_set('ALPHA')

    # ── Card de fundo + borda, cantos arredondados ─────────────
    _round_rect(px - 1, py - 1, panel_w + 2, panel_h + 2, PALETTE['border'])
    _round_rect(px, py, panel_w, panel_h, PALETTE['panel_bg'])

    # ── Cabeçalho ────────────────────────────────────────────
    hy = py + panel_h - HEADER_H
    _rect(px, hy, panel_w, HEADER_H, PALETTE['header_bg'])
    _line = lambda x1, y1, x2, y2, col: _tris(
        [(x1, y1 - 0.5), (x2, y1 - 0.5), (x2, y1 + 0.5),
         (x1, y1 - 0.5), (x2, y1 + 0.5), (x1, y1 + 0.5)], col)
    _line(px, hy, px + panel_w, hy, PALETTE['border'])

    title = "Channel Rack"
    _txt(title, px + 14, hy + HEADER_H / 2 - 6, 13, PALETTE['header_txt'])

    play_dot = PALETTE['step_cur'] if is_playing else (0.40, 0.42, 0.46, 1.0)
    _round_rect(px + panel_w - 24, hy + HEADER_H / 2 - 4, 8, 8, play_dot, radius=4)

    # ── Corpo vazio (sem canais ainda) ──────────────────────────
    if not channels:
        _txt("Nenhum canal -- use 'Track' no painel Tracks",
             px + 14, py + panel_h / 2 - 6, 11, PALETTE['empty_txt'])
        gpu.state.blend_set('NONE')
        return

    # ── Linhas de canal ──────────────────────────────────────────
    ry = py + panel_h - HEADER_H - ROW_H
    for i, ch in enumerate(channels):
        row_col = PALETTE['row_muted'] if ch.mute else (
            PALETTE['row_even'] if i % 2 == 0 else PALETTE['row_odd'])
        _rect(px + 2, ry, panel_w - 4, ROW_H, row_col)

        # Chip de cor sólida
        chip_col = tuple(ch.color) + (1.0,)
        if ch.mute:
            chip_col = tuple(darken(tuple(ch.color), 0.35)) + (1.0,)
        _round_rect(px + 8, ry + (ROW_H - CHIP_W) / 2, CHIP_W, CHIP_W, chip_col, radius=3)

        # Nome do canal
        name_col = PALETTE['name_muted'] if ch.mute else PALETTE['name_txt']
        name = ch.name if len(ch.name) <= 16 else ch.name[:15] + "…"
        _txt(name, px + 8 + CHIP_W + 8, ry + ROW_H / 2 - 5, 11.5, name_col)

        # Botão Mute (M)
        mx0 = px + CHIP_W + 8 + NAME_W
        my0 = ry + (ROW_H - BTN_SIDE) / 2
        _round_rect(mx0, my0, BTN_SIDE, BTN_SIDE,
                    PALETTE['mute_on'] if ch.mute else PALETTE['mute_off'], radius=4)
        tw, _th = _txt_dims("M", 10)
        _txt("M", mx0 + BTN_SIDE / 2 - tw / 2, my0 + BTN_SIDE / 2 - 4, 10, PALETTE['btn_txt'])

        # Botão Solo (S)
        sx0 = mx0 + BTN_SIDE + BTN_GAP
        _round_rect(sx0, my0, BTN_SIDE, BTN_SIDE,
                    PALETTE['solo_on'] if ch.solo else PALETTE['solo_off'], radius=4)
        tw, _th = _txt_dims("S", 10)
        _txt("S", sx0 + BTN_SIDE / 2 - tw / 2, my0 + BTN_SIDE / 2 - 4, 10,
             (0.1, 0.1, 0.1, 1.0) if ch.solo else PALETTE['btn_txt'])

        # Grade de steps
        for s in range(n_steps):
            sx = step_area_x + s * step_w + STEP_GAP / 2
            sw = step_w - STEP_GAP
            active = bool(ch.steps[s])
            is_cur = (s == cur_step) and is_playing

            if is_cur:
                col = PALETTE['step_cur']
            elif active:
                col = chip_col if not ch.mute else tuple(darken(tuple(ch.color), 0.25)) + (1.0,)
            else:
                col = PALETTE['step_off'] if (s // 4) % 2 == 0 else PALETTE['step_off_alt']

            _round_rect(sx, ry + 4, sw, ROW_H - 8, col, radius=3)

            if s % 4 == 0 and s > 0:
                _rect(sx - STEP_GAP, ry + 2, 1, ROW_H - 4, PALETTE['group_line'])

        ry -= (ROW_H + ROW_GAP)

    gpu.state.blend_set('NONE')


# ═══════════════════════════════════════════════════════════════
#  HIT-TEST
# ═══════════════════════════════════════════════════════════════

def _hit_test(mx, my, region, rack):
    geo = _panel_geometry(region, rack)
    px, py = geo['px'], geo['py']
    panel_w, panel_h = geo['panel_w'], geo['panel_h']

    if not (px <= mx <= px + panel_w and py <= my <= py + panel_h):
        return None  # fora do painel -- deixa o evento passar

    channels = geo['channels']
    if not channels:
        return ('PANEL', -1, -1)

    hy = py + panel_h - HEADER_H
    if my >= hy:
        return ('HEADER', -1, -1)

    step_area_x, step_w = geo['step_area_x'], geo['step_w']
    n_steps = geo['n_steps']

    ry = py + panel_h - HEADER_H - ROW_H
    for i in range(len(channels)):
        if ry <= my <= ry + ROW_H:
            mx0 = px + CHIP_W + 8 + NAME_W
            my0 = ry + (ROW_H - BTN_SIDE) / 2
            if mx0 <= mx <= mx0 + BTN_SIDE and my0 <= my <= my0 + BTN_SIDE:
                return ('MUTE', i, -1)
            sx0 = mx0 + BTN_SIDE + BTN_GAP
            if sx0 <= mx <= sx0 + BTN_SIDE and my0 <= my <= my0 + BTN_SIDE:
                return ('SOLO', i, -1)
            if mx >= step_area_x:
                si = int((mx - step_area_x) / step_w) if step_w else -1
                if 0 <= si < n_steps:
                    return ('STEP', i, si)
            return ('ROW', i, -1)
        ry -= (ROW_H + ROW_GAP)

    return ('PANEL', -1, -1)


def _tag_redraw_sequencers():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'SEQUENCE_EDITOR':
                    area.tag_redraw()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
#  MODAL OPERATOR — mantém o overlay vivo e clicável
# ═══════════════════════════════════════════════════════════════

_handle = None          # draw_handler ativo (só um por vez)
_running = [False]       # flag mutável -- checada pelo modal e pelo timer de redraw


class DAW_OT_ChannelRackOverlay(bpy.types.Operator):
    """Liga o overlay do Channel Rack no canto inferior direito do
    Sequencer. Roda em segundo plano (modal 'invisível') sem bloquear
    a interação normal com a timeline -- só intercepta cliques que
    caem dentro do próprio card."""
    bl_idname = "daw.channel_rack_overlay"
    bl_label = "Channel Rack (overlay)"
    bl_options = {'REGISTER', 'INTERNAL'}

    _drag_value = None
    _drag_row = -1

    def invoke(self, context, event):
        global _handle
        if _running[0]:
            # já tem uma instância rodando -- não duplica o handler
            return {'CANCELLED'}

        _handle = bpy.types.SpaceSequenceEditor.draw_handler_add(
            _draw_channel_rack_overlay, (), 'WINDOW', 'POST_PIXEL')
        _running[0] = True
        context.window_manager.modal_handler_add(self)
        _tag_redraw_sequencers()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not _running[0]:
            self._cleanup()
            return {'FINISHED'}

        # Só reage a eventos enquanto o mouse está sobre um Sequencer;
        # em qualquer outra área, passa tudo direto sem tocar em nada.
        if context.area is None or context.area.type != 'SEQUENCE_EDITOR':
            return {'PASS_THROUGH'}

        scene = context.scene
        if scene is None or not hasattr(scene, "daw_channel_rack"):
            return {'PASS_THROUGH'}
        rack = scene.daw_channel_rack
        if not getattr(rack, "show_corner_overlay", True):
            return {'PASS_THROUGH'}

        region = context.region
        mx, my = event.mouse_region_x, event.mouse_region_y

        if event.type == 'LEFTMOUSE':
            hit = _hit_test(mx, my, region, rack)

            if event.value == 'PRESS':
                if hit is None:
                    return {'PASS_THROUGH'}

                kind, ri, si = hit
                channels = list(rack.channels)[:MAX_VISIBLE_ROWS]

                if kind == 'MUTE' and 0 <= ri < len(channels):
                    ch = channels[ri]
                    ch.mute = not ch.mute
                elif kind == 'SOLO' and 0 <= ri < len(channels):
                    ch = channels[ri]
                    ch.solo = not ch.solo
                elif kind == 'STEP' and 0 <= ri < len(channels) and si >= 0:
                    ch = channels[ri]
                    new_val = not bool(ch.steps[si])
                    ch.steps[si] = new_val
                    self._drag_value = new_val
                    self._drag_row = ri

                context.area.tag_redraw()
                return {'RUNNING_MODAL'}

            elif event.value == 'RELEASE':
                consumed = self._drag_value is not None
                self._drag_value = None
                self._drag_row = -1
                if consumed:
                    context.area.tag_redraw()
                    return {'RUNNING_MODAL'}
                return {'PASS_THROUGH'}

        if event.type == 'MOUSEMOVE' and self._drag_value is not None:
            # Arrastar sobre os steps pinta vários de uma vez, como
            # no beat_grid legado e na maioria dos step sequencers.
            hit = _hit_test(mx, my, region, rack)
            if hit and hit[0] == 'STEP' and hit[1] == self._drag_row:
                channels = list(rack.channels)[:MAX_VISIBLE_ROWS]
                ch = channels[self._drag_row]
                si = hit[2]
                if bool(ch.steps[si]) != self._drag_value:
                    ch.steps[si] = self._drag_value
                    context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}

    def _cleanup(self):
        global _handle
        if _handle is not None:
            try:
                bpy.types.SpaceSequenceEditor.draw_handler_remove(_handle, 'WINDOW')
            except Exception:
                pass
            _handle = None
        _tag_redraw_sequencers()


def _redraw_tick():
    """Timer leve (~15fps) só pra manter o playhead do overlay
    (`step_cur`) animado durante a reprodução -- redraw normal do
    Blender já cobre hover/clique, isto é só para o caso 'nada mais
    está mudando na tela mas o step atual avançou'."""
    if not _running[0]:
        return None
    _tag_redraw_sequencers()
    return 1.0 / 15.0


def ensure_started():
    """Liga o overlay automaticamente (chamado por register.py), sem
    depender do usuário clicar em nada -- 'fixo no canto' de verdade.
    Operators não podem ser invocados diretamente durante o próprio
    register() do addon (ainda não há contexto de janela válido), por
    isso o start real acontece num timer com pequeno atraso."""
    if _running[0]:
        return

    def _start():
        try:
            wm = bpy.context.window_manager
            for window in wm.windows:
                for area in window.screen.areas:
                    if area.type == 'SEQUENCE_EDITOR':
                        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                        if region is None:
                            continue
                        with bpy.context.temp_override(window=window, area=area, region=region):
                            bpy.ops.daw.channel_rack_overlay('INVOKE_DEFAULT')
                        bpy.app.timers.register(_redraw_tick, first_interval=0.1)
                        return None
        except Exception as e:
            print(f"[ChannelRack] Overlay não pôde iniciar ainda: {e}")
        # Ainda não há um Sequencer aberto (ex.: addon acabou de ser
        # ativado antes do workspace da DAW carregar) -- tenta de novo
        # em breve em vez de desistir.
        return 0.5

    bpy.app.timers.register(_start, first_interval=0.3)


def force_stop():
    """Desliga o overlay -- chamado por register.py::unregister()."""
    _running[0] = False
    global _handle
    if _handle is not None:
        try:
            bpy.types.SpaceSequenceEditor.draw_handler_remove(_handle, 'WINDOW')
        except Exception:
            pass
        _handle = None
    _tag_redraw_sequencers()


classes = [
    DAW_OT_ChannelRackOverlay,
]