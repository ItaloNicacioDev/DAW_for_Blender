# modules/channel_rack/mixer_strip_operator.py
"""
Interação (clique/arraste) das channel strips do mixer.

IMPORTANTE -- histórico da correção: a primeira versão deste arquivo
tentava manter um único operador modal "eterno", iniciado sozinho via
`bpy.app.timers` + `bpy.context.temp_override(...)` logo no register()
do addon. Isso desenhava a tela certinho (o draw_handler não depende
de operador nenhum), mas os cliques/arrastes nunca funcionavam: um
operador invocado a partir de um timer, com o contexto "forjado" por
temp_override, não fica de fato "dono" do event loop da janela da
forma como o Blender espera -- é o mesmo tipo de contexto restrito que
já aparecia no log do seu addon para o VST ("_RestrictData' object has
no attribute 'scenes'").

A forma robusta e padrão do Blender pra isso é: registrar um atalho de
teclado/mouse (keymap item) pro LEFTMOUSE no editor do Sequencer. O
Blender então invoca o operador com um evento e um contexto DE
VERDADE a cada clique. No `invoke()`:
  - fizemos o hit-test primeiro;
  - se o clique foi fora do card -> devolvemos {'PASS_THROUGH'}
    IMEDIATAMENTE, sem nem registrar handler modal -- o clique cai
    pro comportamento normal do Sequencer (selecionar strip, etc.);
  - se acertou um botão de ação única (header/M/S) -> aplicamos e
    terminamos ({'FINISHED'}), sem precisar de modal;
  - se acertou algo arrastável (fader/knob/título/alça) -> aí sim
    chamamos `modal_handler_add` e seguimos em {'RUNNING_MODAL'} só
    até o LEFTMOUSE ser solto.

Isso é o mesmo padrão do operador de exemplo "Simple Modal Operator"
da própria documentação do Blender (invoke registra o handler modal e
o keymap dispara o invoke), então funciona de forma confiável.
"""
from __future__ import annotations

import math

import bpy

from .mixer_strip_draw import draw_mixer_strips
from .mixer_strip_geometry import hit_test, clamp_scale, FADER_TRACK_H


def _tag_redraw_sequencers():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'SEQUENCE_EDITOR':
                    area.tag_redraw()
    except Exception:
        pass


def _get_rack(context):
    scene = context.scene
    if scene is None or not hasattr(scene, "daw_channel_rack"):
        return None
    return scene.daw_channel_rack


def _get_overlay_pos_scale(rack):
    return (
        getattr(rack, "overlay_pos_x", 16),
        getattr(rack, "overlay_pos_y", 16),
        getattr(rack, "overlay_scale", 1.0),
    )


class DAW_OT_MixerStripOverlay(bpy.types.Operator):
    """Clique/arraste sobre o card do mixer (channel strips): fader,
    knob de pan, M/S, mover o card (barra de título) e redimensionar
    (alça no canto inferior direito)."""
    bl_idname = "daw.mixer_strip_overlay"
    bl_label = "Mixer (channel strips)"
    bl_options = {'REGISTER', 'INTERNAL'}

    # 'FADER' | 'KNOB' | 'MOVE' | 'RESIZE' | None
    _drag_kind = None
    _drag_attr = None            # 'volume' | 'pan'
    _drag_group = ()             # índices dos canais que se movem juntos
    _drag_start_values = {}      # {índice: valor inicial}
    _drag_start_mouse = (0, 0)
    _drag_start_value = 0.0
    _drag_start_pos = (0, 0)
    _drag_anchor = (0, 0)        # canto (px,py) do painel, p/ redimensionar

    @staticmethod
    def _select_only(channels, idx):
        for c in channels:
            c.selected = False
        channels[idx].selected = True

    def _prepare_drag_group(self, rack, channels, idx, attr):
        """Decide quais canais se movem juntos: se o canal clicado já faz
        parte da seleção atual, arrasta o grupo inteiro (comportamento
        clássico de DAW); senão, vira uma seleção nova só dele."""
        ch = channels[idx]
        if not getattr(ch, "selected", False):
            self._select_only(channels, idx)
        rack.active_channel_index = idx

        group = [i for i, c in enumerate(channels) if getattr(c, "selected", False)]
        if idx not in group:
            group.append(idx)

        self._drag_kind = 'FADER' if attr == 'volume' else 'KNOB'
        self._drag_attr = attr
        self._drag_group = tuple(group)
        self._drag_start_values = {i: getattr(channels[i], attr) for i in group}

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'SEQUENCE_EDITOR':
            return {'PASS_THROUGH'}
        rack = _get_rack(context)
        if rack is None or not getattr(rack, "show_mixer_strip_overlay", True):
            return {'PASS_THROUGH'}

        region = context.region
        mx, my = event.mouse_region_x, event.mouse_region_y
        channels = list(rack.channels)
        pos_x, pos_y, scale = _get_overlay_pos_scale(rack)

        hit = hit_test(mx, my, region, channels, pos_x, pos_y, scale)
        if hit is None:
            return {'PASS_THROUGH'}

        kind, idx = hit[0], hit[1]

        if kind == 'TITLEBAR':
            self._drag_kind = 'MOVE'
            self._drag_start_mouse = (mx, my)
            self._drag_start_pos = (pos_x, pos_y)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        if kind == 'GRIP':
            self._drag_kind = 'RESIZE'
            self._drag_start_mouse = (mx, my)
            self._drag_start_value = scale
            self._drag_anchor = (pos_x, pos_y)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        if idx < 0 or idx >= len(channels):
            # dentro do card mas em área vazia (kind == 'PANEL', idx == -1):
            # engole o clique pra não cair na seleção de strips do VSE.
            return {'FINISHED'}

        ch = channels[idx]

        if kind == 'HEADER':
            # clique normal = seleciona só essa; Shift+clique = soma/
            # remove da seleção (multi-seleção, como em outras DAWs)
            if event.shift:
                ch.selected = not ch.selected
            else:
                self._select_only(channels, idx)
            rack.active_channel_index = idx
            context.area.tag_redraw()
            return {'FINISHED'}

        if kind == 'MUTE':
            ch.mute = not ch.mute
            context.area.tag_redraw()
            return {'FINISHED'}

        if kind == 'SOLO':
            ch.solo = not ch.solo
            context.area.tag_redraw()
            return {'FINISHED'}

        if kind == 'FADER':
            self._prepare_drag_group(rack, channels, idx, 'volume')
            self._drag_start_mouse = (mx, my)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        if kind == 'KNOB':
            self._prepare_drag_group(rack, channels, idx, 'pan')
            self._drag_start_mouse = (mx, my)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}

    def modal(self, context, event):
        rack = _get_rack(context)
        if rack is None:
            return {'CANCELLED'}

        if event.type == 'MOUSEMOVE':
            mx, my = event.mouse_region_x, event.mouse_region_y
            sx, sy = self._drag_start_mouse
            channels = list(rack.channels)
            _, _, scale = _get_overlay_pos_scale(rack)

            if self._drag_kind == 'MOVE':
                start_px, start_py = self._drag_start_pos
                rack.overlay_pos_x = max(0, start_px + (mx - sx))
                rack.overlay_pos_y = max(0, start_py + (my - sy))

            elif self._drag_kind == 'RESIZE':
                # redimensiona por distância ao canto fixo do painel
                # (bottom-left) -- arrastar a alça pra "longe" do
                # painel aumenta, pra "perto" diminui, em qualquer
                # direção (mais intuitivo que só dx ou só dy).
                ax, ay = self._drag_anchor
                start_dist = math.hypot(sx - ax, sy - ay) or 1.0
                cur_dist = math.hypot(mx - ax, my - ay)
                ratio = cur_dist / start_dist
                rack.overlay_scale = clamp_scale(self._drag_start_value * ratio)

            elif self._drag_kind in ('FADER', 'KNOB') and self._drag_group:
                if self._drag_kind == 'FADER':
                    delta = (my - sy) / (FADER_TRACK_H * scale)
                    lo, hi = 0.0, 1.0
                else:
                    # arraste horizontal: curso proporcional à escala
                    # atual, convenção comum de knob em DAWs.
                    delta = (mx - sx) / (140.0 * scale)
                    lo, hi = -1.0, 1.0

                # mesmo delta pra todo mundo selecionado -- é assim que
                # DAWs normais movem faders/knobs em grupo (cada um
                # clampado no seu próprio limite, sem "esticar" a
                # proporção dos outros)
                for i in self._drag_group:
                    if i >= len(channels):
                        continue
                    start = self._drag_start_values.get(i, 0.0)
                    value = max(lo, min(hi, start + delta))
                    setattr(channels[i], self._drag_attr, value)

            if context.area:
                context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._drag_kind = None
            self._drag_attr = None
            self._drag_group = ()
            self._drag_start_values = {}
            if context.area:
                context.area.tag_redraw()
            return {'FINISHED'}

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self._drag_kind = None
            self._drag_attr = None
            self._drag_group = ()
            self._drag_start_values = {}
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


class DAW_OT_ResetMixerOverlayTransform(bpy.types.Operator):
    """Restaura a posição e o tamanho padrão do card do mixer."""
    bl_idname = "daw.reset_mixer_overlay_transform"
    bl_label = "Redefinir Posição/Tamanho do Mixer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rack = context.scene.daw_channel_rack
        rack.overlay_pos_x = 16
        rack.overlay_pos_y = 16
        rack.overlay_scale = 1.0
        _tag_redraw_sequencers()
        return {'FINISHED'}


# ------------------------------------------------------------------ #
#  Registro: draw handler (sempre ligado) + keymap (dispara o
#  operador acima a cada LEFTMOUSE no Sequencer) + timer leve pro
#  medidor/glow animarem sozinhos.
# ------------------------------------------------------------------ #
_draw_handle = None
_keymaps: list = []
_redraw_timer_running = [False]


def _redraw_tick():
    if not _redraw_timer_running[0]:
        return None
    _tag_redraw_sequencers()
    return 1.0 / 15.0


def register() -> None:
    global _draw_handle
    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceSequenceEditor.draw_handler_add(
            draw_mixer_strips, (), 'WINDOW', 'POST_PIXEL')

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        # 'Sequencer' cobre a timeline; 'SequencerPreview' cobre a
        # janela de preview -- registramos nos dois pra funcionar
        # independente de qual modo de visualização o usuário estiver
        # usando na área do Sequencer.
        for km_name in ("Sequencer", "SequencerPreview"):
            km = kc.keymaps.new(name=km_name, space_type='SEQUENCE_EDITOR')
            kmi = km.keymap_items.new(DAW_OT_MixerStripOverlay.bl_idname, 'LEFTMOUSE', 'PRESS')
            _keymaps.append((km, kmi))

    if not _redraw_timer_running[0]:
        _redraw_timer_running[0] = True
        bpy.app.timers.register(_redraw_tick, first_interval=0.2)


def unregister() -> None:
    global _draw_handle
    _redraw_timer_running[0] = False

    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _keymaps.clear()

    if _draw_handle is not None:
        try:
            bpy.types.SpaceSequenceEditor.draw_handler_remove(_draw_handle, 'WINDOW')
        except Exception:
            pass
        _draw_handle = None

    _tag_redraw_sequencers()


# Compatibilidade com o nome antigo usado em register.py de versões
# anteriores deste módulo.
ensure_started = register
force_stop = unregister


classes = [
    DAW_OT_MixerStripOverlay,
    DAW_OT_ResetMixerOverlayTransform,
]