"""transport/record.py

Operador que arma a gravação. Por padrão apenas sinaliza o estado
`is_recording` e dispara a reprodução; o restante do addon (captura de
MIDI/áudio, inserção de keyframes, etc.) deve escutar esse flag via
`utils.get_transport(context).is_recording`.
"""

import bpy
from bpy.types import Operator

from .utils import get_transport, redraw_ui


class DAW_OT_transport_record(Operator):
    """Arma/desarma a gravação. Se armado, também inicia a reprodução"""
    bl_idname = "daw.transport_record"
    bl_label = "Record"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        transport = get_transport(context)
        screen = context.screen

        transport.is_recording = not transport.is_recording

        if transport.is_recording:
            if not screen.is_animation_playing:
                bpy.ops.screen.animation_play()
            transport.is_playing = True
            transport.is_paused = False
        else:
            if screen.is_animation_playing:
                bpy.ops.screen.animation_play()
            transport.is_playing = False

        redraw_ui(context)
        return {"FINISHED"}


classes = (DAW_OT_transport_record,)