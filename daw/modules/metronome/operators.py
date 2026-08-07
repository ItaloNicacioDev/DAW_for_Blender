# modules/metronome/operators.py
"""
Operators do Blender para o metrônomo.

Responsabilidade:
    - DAW_OT_MetronomeRun: operator modal com timer que faz o metrônomo
      "bater" de verdade (baseado em wall-clock, independente do motor
      C++ estar carregado ou não — funciona também em "Modo Local").
    - DAW_OT_MetronomeToggle: liga/desliga (scene.daw.metronome) e
      inicia/para o timer.
    - DAW_OT_MetronomeTestClick: toca um clique avulso (botão de teste na UI).
    - DAW_OT_MetronomeTapTempo: calcula o BPM a partir de cliques do usuário.
"""
from __future__ import annotations

import time
from typing import List

import bpy
from bpy.props import BoolProperty
from bpy.types import Operator

from . import sounds
from .utils import (
    get_daw_props,
    get_metronome_props,
    seconds_per_beat,
    beat_index_to_bar_beat,
    is_accent_beat,
    should_click_now,
    clamp_bpm,
)

# Flag global — garante que só exista um timer de metrônomo rodando por vez
_metronome_running = False

# Timestamps do tap tempo (module-level; resetado após alguns segundos de inatividade)
_tap_times: List[float] = []
_TAP_TIMEOUT = 2.0
_TAP_MIN_SAMPLES = 2
_TAP_MAX_SAMPLES = 8


class DAW_OT_MetronomeRun(Operator):
    """Operator modal que mantém o metrônomo batendo enquanto scene.daw.metronome estiver ativo."""

    bl_idname = "daw.metronome_run"
    bl_label = "Metrônomo (executando)"
    bl_options = {'REGISTER'}

    _timer = None
    _start_time = 0.0
    _last_beat_index = -1

    def invoke(self, context, event):
        global _metronome_running
        if _metronome_running:
            # Já existe um timer rodando — não inicia outro
            return {'CANCELLED'}

        _metronome_running = True
        self._start_time = time.time()
        self._last_beat_index = -1

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.015, window=context.window)
        wm.modal_handler_add(self)

        context.scene.daw_metronome.is_running = True
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        scene = context.scene
        daw = get_daw_props(context)
        metro = get_metronome_props(context)

        # Se o usuário desligou o metrônomo, encerra o modal
        if not daw.metronome_enabled:
            self._finish(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            elapsed = time.time() - self._start_time
            spb = seconds_per_beat(daw.bpm)
            beat_index = int(elapsed / spb)

            if beat_index != self._last_beat_index:
                self._last_beat_index = beat_index

                bar, beat_in_bar = beat_index_to_bar_beat(beat_index, metro.beats_per_bar)
                daw.current_bar = bar
                daw.current_beat = beat_in_bar

                if should_click_now(context):
                    accent = is_accent_beat(beat_index, metro.beats_per_bar, metro.accent_first_beat)
                    sounds.play_click(metro.sound_style, accent, metro.volume)

        return {'PASS_THROUGH'}

    def _finish(self, context) -> None:
        global _metronome_running
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
        _metronome_running = False
        if context.scene and hasattr(context.scene, "daw_metronome"):
            context.scene.daw_metronome.is_running = False

    def cancel(self, context):
        self._finish(context)


class DAW_OT_MetronomeToggle(Operator):
    bl_idname = "daw.metronome_toggle"
    bl_label = "Metrônomo Liga/Desliga"
    bl_description = "Ativa ou desativa o metrônomo"
    bl_options = {'REGISTER'}

    def execute(self, context):
        daw = get_daw_props(context)
        daw.metronome_enabled = not daw.metronome_enabled

        if daw.metronome_enabled:
            bpy.ops.daw.metronome_run('INVOKE_DEFAULT')
            self.report({'INFO'}, "Metrônomo ativado")
        else:
            self.report({'INFO'}, "Metrônomo desativado")

        return {'FINISHED'}


class DAW_OT_MetronomeTestClick(Operator):
    bl_idname = "daw.metronome_test_click"
    bl_label = "Testar Clique"
    bl_description = "Toca um clique de teste com o som e volume configurados"
    bl_options = {'REGISTER'}

    accent: BoolProperty(default=False)

    def execute(self, context):
        metro = get_metronome_props(context)
        sounds.play_click(metro.sound_style, self.accent, metro.volume)
        return {'FINISHED'}


class DAW_OT_MetronomeTapTempo(Operator):
    """Cada clique nesse operador registra um timestamp; a média dos últimos intervalos vira o BPM."""

    bl_idname = "daw.metronome_tap_tempo"
    bl_label = "Tap Tempo"
    bl_description = "Clique no ritmo desejado repetidamente para calcular o BPM automaticamente"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global _tap_times
        now = time.time()

        if _tap_times and (now - _tap_times[-1]) > _TAP_TIMEOUT:
            _tap_times.clear()

        _tap_times.append(now)
        if len(_tap_times) > _TAP_MAX_SAMPLES:
            _tap_times.pop(0)

        if len(_tap_times) < _TAP_MIN_SAMPLES:
            self.report({'INFO'}, f"Tap {len(_tap_times)}/{_TAP_MIN_SAMPLES} — continue clicando")
            return {'FINISHED'}

        intervals = [t2 - t1 for t1, t2 in zip(_tap_times, _tap_times[1:])]
        avg_interval = sum(intervals) / len(intervals)
        if avg_interval <= 0:
            return {'CANCELLED'}

        bpm = clamp_bpm(60.0 / avg_interval)
        daw = get_daw_props(context)
        daw.bpm = bpm

        self.report({'INFO'}, f"BPM definido para {bpm:.1f}")
        return {'FINISHED'}


class DAW_OT_MetronomeTapTempoReset(Operator):
    bl_idname = "daw.metronome_tap_tempo_reset"
    bl_label = "Resetar Tap Tempo"
    bl_description = "Limpa a contagem atual do tap tempo"
    bl_options = {'REGISTER'}

    def execute(self, context):
        _tap_times.clear()
        self.report({'INFO'}, "Tap tempo resetado")
        return {'FINISHED'}


classes = [
    DAW_OT_MetronomeRun,
    DAW_OT_MetronomeToggle,
    DAW_OT_MetronomeTestClick,
    DAW_OT_MetronomeTapTempo,
    DAW_OT_MetronomeTapTempoReset,
]