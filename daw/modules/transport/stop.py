"""transport/stop.py

Operador que para a reprodução e retorna o playhead ao início (ou ao
início do loop, se o loop estiver ativo).
"""

import bpy
from bpy.types import Operator

from .utils import get_transport, redraw_ui


class DAW_OT_transport_stop(Operator):
    """Para a reprodução e retorna o playhead ao início"""
    bl_idname = "daw.transport_stop"
    bl_label = "Stop"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        transport = get_transport(context)
        scene = context.scene
        screen = context.screen

        if screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)

        return_frame = transport.loop_start if transport.loop_enabled else scene.frame_start
        scene.frame_set(return_frame)

        transport.is_playing = False
        transport.is_paused = False
        transport.is_recording = False
        redraw_ui(context)
        return {"FINISHED"}


classes = (DAW_OT_transport_stop,)