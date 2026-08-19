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

            # [FIX] O REC da barra de transporte, antes, só alternava esse
            # estado visual e dava play -- nunca chamava o módulo Recorder
            # de verdade (daw.recorder_start), que é quem captura áudio das
            # tracks armadas e cria a strip ao vivo no VSE. Resultado: o
            # usuário clicava em "Gravar" e literalmente nada acontecia
            # com o áudio, sem nenhum erro visível (o botão certo era
            # outro, escondido dentro do painel Recorder). Agora o REC
            # principal também dispara a gravação de áudio, se houver
            # pelo menos uma track armada.
            try:
                if bpy.ops.daw.recorder_start.poll():
                    bpy.ops.daw.recorder_start('EXEC_DEFAULT')
            except AttributeError:
                pass  # módulo recorder não registrado
            except Exception as e:
                print(f"[DAW Transport] Falha ao iniciar gravação de áudio: {e}")
        else:
            if screen.is_animation_playing:
                bpy.ops.screen.animation_play()
            transport.is_playing = False

            try:
                if bpy.ops.daw.recorder_stop.poll():
                    bpy.ops.daw.recorder_stop('EXEC_DEFAULT')
            except AttributeError:
                pass
            except Exception as e:
                print(f"[DAW Transport] Falha ao finalizar gravação de áudio: {e}")

        redraw_ui(context)
        return {"FINISHED"}


classes = (DAW_OT_transport_record,)