"""transport/play.py

Operador que inicia a reprodução. Usa o player de animação nativo do
Blender (`screen.animation_play`), que já respeita audio scrub/sync.
"""

import bpy
from bpy.types import Operator

from .utils import get_transport, redraw_ui


class DAW_OT_transport_play(Operator):
    """Inicia a reprodução a partir do frame atual"""
    bl_idname = "daw.transport_play"
    bl_label = "Play"
    bl_options = {"REGISTER"}

    def execute(self, context):
        transport = get_transport(context)
        screen = context.screen

        if not screen.is_animation_playing:
            bpy.ops.screen.animation_play()

        transport.is_playing = True
        transport.is_paused = False
        redraw_ui(context)
        return {"FINISHED"}


classes = (DAW_OT_transport_play,)