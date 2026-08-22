# modules/channel_rack/mixer_strip_operator.py
"""
Operador modal que mantém vivo o overlay das channel strips do mixer
(`mixer_strip_draw.draw_mixer_strips`) e trata os cliques/arrastes:

  - clique no header        -> seleciona o canal (active_channel_index)
  - arrastar o fader         -> ajusta `channel.volume` (0.0-1.0)
  - arrastar o knob (eixo X) -> ajusta `channel.pan` (-1.0-1.0)
  - clique em M / S          -> alterna mute / solo
  - arrastar a barra de título -> move o painel inteiro (`rack.overlay_pos_x/y`)
  - arrastar a alça (canto inferior direito) -> redimensiona (`rack.overlay_scale`)

Mesma arquitetura de `overlay.py` (draw_handler_add em
SpaceSequenceEditor/'WINDOW', hit-test compartilhado via
`mixer_strip_geometry`, `ensure_started()`/`force_stop()` chamados por
`register.py`) -- projetado para conviver com o overlay do step grid
sem conflito (paineis em cantos diferentes, cada um com seu próprio
operador/handler).
"""
from __future__ import annotations

import bpy

from .mixer_strip_draw import draw_mixer_strips
from .mixer_strip_geometry import hit_test, clamp_scale


def _tag_redraw_sequencers():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'SEQUENCE_EDITOR':
                    area.tag_redraw()
    except Exception:
        pass


def _get_overlay_pos_scale(rack):
    return (
        getattr(rack, "overlay_pos_x", 16),
        getattr(rack, "overlay_pos_y", 16),
        getattr(rack, "overlay_scale", 1.0),
    )


_handle = None
_running = [False]


class DAW_OT_MixerStripOverlay(bpy.types.Operator):
    """Liga o overlay das channel strips do mixer e escuta
    clique/arraste sobre ele (fader, knob, M/S, mover, redimensionar)."""
    bl_idname = "daw.mixer_strip_overlay"
    bl_label = "Mixer (channel strips)"
    bl_options = {'REGISTER', 'INTERNAL'}

    # 'FADER' | 'KNOB' | 'MOVE' | 'RESIZE' | None
    _drag_kind = None
    _drag_index = -1
    _drag_attr = None            # 'volume' | 'pan'
    _drag_group = ()             # índices dos canais que se movem juntos
    _drag_start_values = {}      # {índice: valor inicial}
    _drag_start_mouse = (0, 0)
    _drag_start_value = 0.0
    _drag_start_pos = (0, 0)

    def invoke(self, context, event):
        global _handle
        if _running[0]:
            return {'CANCELLED'}

        _handle = bpy.types.SpaceSequenceEditor.draw_handler_add(
            draw_mixer_strips, (), 'WINDOW', 'POST_PIXEL')
        _running[0] = True
        context.window_manager.modal_handler_add(self)
        _tag_redraw_sequencers()
        return {'RUNNING_MODAL'}

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
        self._drag_index = idx

    def modal(self, context, event):
        if not _running[0]:
            self._cleanup()
            return {'FINISHED'}

        if context.area is None or context.area.type != 'SEQUENCE_EDITOR':
            return {'PASS_THROUGH'}

        scene = context.scene
        if scene is None or not hasattr(scene, "daw_channel_rack"):
            return {'PASS_THROUGH'}
        rack = scene.daw_channel_rack
        if not getattr(rack, "show_mixer_strip_overlay", True):
            return {'PASS_THROUGH'}

        region = context.region
        mx, my = event.mouse_region_x, event.mouse_region_y
        channels = list(rack.channels)
        pos_x, pos_y, scale = _get_overlay_pos_scale(rack)

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                hit = hit_test(mx, my, region, channels, pos_x, pos_y, scale)
                if hit is None:
                    return {'PASS_THROUGH'}

                kind, idx = hit[0], hit[1]

                if kind == 'TITLEBAR':
                    self._drag_kind = 'MOVE'
                    self._drag_start_mouse = (mx, my)
                    self._drag_start_pos = (pos_x, pos_y)
                    return {'RUNNING_MODAL'}

                if kind == 'GRIP':
                    self._drag_kind = 'RESIZE'
                    self._drag_start_mouse = (mx, my)
                    self._drag_start_value = scale
                    return {'RUNNING_MODAL'}

                if idx < 0 or idx >= len(channels):
                    return {'RUNNING_MODAL'} if kind != 'PANEL' else {'PASS_THROUGH'}

                ch = channels[idx]

                if kind == 'HEADER':
                    # clique normal = seleciona só essa; Shift+clique =
                    # soma/remove da seleção (multi-seleção, como em
                    # outras DAWs)
                    if event.shift:
                        ch.selected = not ch.selected
                    else:
                        self._select_only(channels, idx)
                    rack.active_channel_index = idx
                elif kind == 'MUTE':
                    ch.mute = not ch.mute
                elif kind == 'SOLO':
                    ch.solo = not ch.solo
                elif kind == 'FADER':
                    self._prepare_drag_group(rack, channels, idx, 'volume')
                    self._drag_start_mouse = (mx, my)
                elif kind == 'KNOB':
                    self._prepare_drag_group(rack, channels, idx, 'pan')
                    self._drag_start_mouse = (mx, my)

                context.area.tag_redraw()
                return {'RUNNING_MODAL'}

            elif event.value == 'RELEASE':
                dragging = self._drag_kind is not None
                self._drag_kind = None
                self._drag_attr = None
                self._drag_group = ()
                self._drag_start_values = {}
                self._drag_index = -1
                if dragging:
                    context.area.tag_redraw()
                    return {'RUNNING_MODAL'}
                return {'PASS_THROUGH'}

        if event.type == 'MOUSEMOVE' and self._drag_kind is not None:
            sx, sy = self._drag_start_mouse

            if self._drag_kind == 'MOVE':
                start_px, start_py = self._drag_start_pos
                rack.overlay_pos_x = max(0, start_px + (mx - sx))
                rack.overlay_pos_y = max(0, start_py + (my - sy))
                context.area.tag_redraw()

            elif self._drag_kind == 'RESIZE':
                # arraste na diagonal (canto inferior direito): mover
                # pra direita/baixo aumenta, pra esquerda/cima diminui.
                delta = ((mx - sx) - (my - sy)) / 220.0
                rack.overlay_scale = clamp_scale(self._drag_start_value + delta)
                context.area.tag_redraw()

            elif self._drag_kind in ('FADER', 'KNOB') and self._drag_group:
                if self._drag_kind == 'FADER':
                    from .mixer_strip_geometry import FADER_TRACK_H
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


def _redraw_tick():
    """Timer leve (~15fps) só para o medidor/glow acompanharem o
    `meter_level` sendo atualizado por register.py::_meter_update_tick
    mesmo quando nada mais na tela está mudando."""
    if not _running[0]:
        return None
    _tag_redraw_sequencers()
    return 1.0 / 15.0


def ensure_started() -> None:
    """Liga o overlay automaticamente ao registrar o addon (mesmo
    padrão de `overlay.ensure_started`)."""
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
                            bpy.ops.daw.mixer_strip_overlay('INVOKE_DEFAULT')
                        bpy.app.timers.register(_redraw_tick, first_interval=0.1)
                        return None
        except Exception as e:
            print(f"[ChannelRack] Mixer overlay não pôde iniciar ainda: {e}")
        return 0.5

    bpy.app.timers.register(_start, first_interval=0.3)


def force_stop() -> None:
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
    DAW_OT_MixerStripOverlay,
    DAW_OT_ResetMixerOverlayTransform,
]