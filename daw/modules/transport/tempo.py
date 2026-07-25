"""transport/tempo.py

Lógica de tempo (BPM): aplicação do valor atual e operadores para
dobrar/reduzir o tempo pela metade, comuns em DAWs.
"""

import bpy
from bpy.types import Operator

from .utils import get_transport, redraw_ui


def apply_bpm(context, bpm):
    """Chamado sempre que `daw_transport.bpm` muda.

    Aqui é o ponto central para propagar o novo BPM para o resto do
    addon (ex.: reposicionar marcadores de batida, recalcular grid de
    quantização, avisar o motor de áudio). Mantido simples por padrão.
    """
    transport = get_transport(context)
    transport.bpm = max(20.0, min(999.0, bpm))
    redraw_ui(context)


class DAW_OT_transport_tempo_double(Operator):
    """Dobra o BPM atual"""
    bl_idname = "daw.transport_tempo_double"
    bl_label = "Double Tempo"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        transport = get_transport(context)
        apply_bpm(context, transport.bpm * 2.0)
        return {"FINISHED"}


class DAW_OT_transport_tempo_halve(Operator):
    """Reduz o BPM atual pela metade"""
    bl_idname = "daw.transport_tempo_halve"
    bl_label = "Halve Tempo"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        transport = get_transport(context)
        apply_bpm(context, transport.bpm / 2.0)
        return {"FINISHED"}


classes = (
    DAW_OT_transport_tempo_double,
    DAW_OT_transport_tempo_halve,
)