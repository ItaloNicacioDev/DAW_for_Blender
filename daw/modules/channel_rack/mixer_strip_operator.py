# modules/channel_rack/mixer_strip_operator.py
"""
Operador modal que mantém vivo o overlay das channel strips do mixer
(`mixer_strip_draw.draw_mixer_strips`) e trata os cliques/arrastes:

  - clique no header       -> seleciona o canal (active_channel_index)
  - arrastar o fader        -> ajusta `channel.volume` (0.0-1.0)
  - arrastar o knob (eixo X)-> ajusta `channel.pan` (-1.0-1.0)
  - clique em M / S         -> alterna mute / solo

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
from .mixer_strip_geometry import hit_test


def _tag_redraw_sequencers():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'SEQUENCE_EDITOR':
                    area.tag_redraw()
    except Exception:
        pass


_handle = None
_running = [False]


class DAW_OT_MixerStripOverlay(bpy.types.Operator):
    """Liga o overlay das channel strips do mixer (canto inferior
    esquerdo do Sequencer) e escuta clique/arraste sobre ele."""
    bl_idname = "daw.mixer_strip_overlay"
    bl_label = "Mixer (channel strips)"
    bl_options = {'REGISTER', 'INTERNAL'}

    _drag_kind = None    # 'FADER' | 'KNOB' | None
    _drag_index = -1
    _drag_start_mouse = (0, 0)
    _drag_start_value = 0.0

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

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                hit = hit_test(mx, my, region, channels)
                if hit is None:
                    return {'PASS_THROUGH'}

                kind, idx = hit[0], hit[1]
                if idx < 0 or idx >= len(channels):
                    return {'RUNNING_MODAL'} if kind != 'PANEL' else {'PASS_THROUGH'}

                ch = channels[idx]

                if kind == 'HEADER':
                    rack.active_channel_index = idx
                elif kind == 'MUTE':
                    ch.mute = not ch.mute
                elif kind == 'SOLO':
                    ch.solo = not ch.solo
                elif kind == 'FADER':
                    rack.active_channel_index = idx
                    self._drag_kind = 'FADER'
                    self._drag_index = idx
                    self._drag_start_mouse = (mx, my)
                    self._drag_start_value = ch.volume
                elif kind == 'KNOB':
                    rack.active_channel_index = idx
                    self._drag_kind = 'KNOB'
                    self._drag_index = idx
                    self._drag_start_mouse = (mx, my)
                    self._drag_start_value = ch.pan

                context.area.tag_redraw()
                return {'RUNNING_MODAL'}

            elif event.value == 'RELEASE':
                dragging = self._drag_kind is not None
                self._drag_kind = None
                self._drag_index = -1
                if dragging:
                    context.area.tag_redraw()
                    return {'RUNNING_MODAL'}
                return {'PASS_THROUGH'}

        if event.type == 'MOUSEMOVE' and self._drag_kind is not None:
            if 0 <= self._drag_index < len(channels):
                ch = channels[self._drag_index]
                sx, sy = self._drag_start_mouse

                if self._drag_kind == 'FADER':
                    from .mixer_strip_geometry import FADER_TRACK_H
                    delta = (my - sy) / FADER_TRACK_H
                    ch.volume = max(0.0, min(1.0, self._drag_start_value + delta))
                elif self._drag_kind == 'KNOB':
                    # arraste horizontal: ~140px de curso para -1..1,
                    # convenção comum de knob em DAWs (sem precisar
                    # girar o mouse em círculo).
                    delta = (mx - sx) / 140.0
                    ch.pan = max(-1.0, min(1.0, self._drag_start_value + delta))

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
]