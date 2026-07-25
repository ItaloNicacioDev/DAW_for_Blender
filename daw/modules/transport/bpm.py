"""transport/bpm.py

Operador de "tap tempo": o usuário clica no ritmo desejado e o BPM é
calculado a partir do intervalo médio entre os cliques.
"""

import time

import bpy
from bpy.types import Operator

from .tempo import apply_bpm

# Timestamps dos últimos taps (module-level: um operador de tap tempo
# não guarda estado entre invocações, então mantemos aqui).
_tap_times = []

# Se o intervalo desde o último tap for maior que isso, reinicia a
# contagem (evita calcular BPM absurdo depois de uma pausa longa).
_TAP_TIMEOUT = 2.0
_MAX_TAPS = 8


class DAW_OT_transport_tap_tempo(Operator):
    """Define o BPM tocando no ritmo desejado repetidamente"""
    bl_idname = "daw.transport_tap_tempo"
    bl_label = "Tap Tempo"
    bl_options = {"REGISTER"}

    def execute(self, context):
        now = time.time()

        if _tap_times and (now - _tap_times[-1]) > _TAP_TIMEOUT:
            _tap_times.clear()

        _tap_times.append(now)
        if len(_tap_times) > _MAX_TAPS:
            del _tap_times[0]

        if len(_tap_times) < 2:
            self.report({"INFO"}, "Tap tempo: continue tocando...")
            return {"FINISHED"}

        intervals = [
            _tap_times[i + 1] - _tap_times[i]
            for i in range(len(_tap_times) - 1)
        ]
        avg_interval = sum(intervals) / len(intervals)
        bpm = 60.0 / avg_interval

        apply_bpm(context, bpm)
        self.report({"INFO"}, f"Tap tempo: {bpm:.1f} BPM")
        return {"FINISHED"}


classes = (DAW_OT_transport_tap_tempo,)