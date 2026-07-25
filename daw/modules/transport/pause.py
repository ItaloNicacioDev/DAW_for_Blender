"""transport/pause.py

Operador que pausa a reprodução preservando o frame atual (diferente
de stop, que retorna ao início/loop_start).
"""

import bpy
from bpy.types import Operator

from .utils import get_transport, redraw_ui


class DAW_OT_transport_pause(Operator):
    """Pausa a reprodução, mantendo a posição do playhead"""
    bl_idname = "daw.transport_pause"
    bl_label = "Pause"
    bl_options = {"REGISTER"}

    def execute(self, context):
        transport = get_transport(context)
        screen = context.screen

        if screen.is_animation_playing:
            # `animation_play` funciona como toggle: chamá-lo de novo
            # enquanto toca simplesmente para no frame atual, sem
            # voltar o playhead.
            bpy.ops.screen.animation_play()

        transport.is_playing = False
        transport.is_paused = True
        redraw_ui(context)
        return {"FINISHED"}


classes = (DAW_OT_transport_pause,)