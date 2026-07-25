"""transport/ui.py

Painel de transporte, exibido na N-panel da 3D Viewport (aba "DAW").
Ajuste `bl_space_type`/`bl_category` se o addon já tiver um espaço
próprio (ex.: um editor customizado ou o Sequencer).
"""

import bpy
from bpy.types import Panel

from .utils import get_transport


class DAW_PT_transport(Panel):
    """Painel principal de transporte da DAW"""
    bl_idname = "DAW_PT_transport"
    bl_label = "Transport"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAW"

    def draw(self, context):
        layout = self.layout
        transport = get_transport(context)

        # --- Botões principais de transporte ---
        row = layout.row(align=True)
        row.scale_y = 1.5

        play_icon = "PAUSE" if transport.is_playing else "PLAY"
        play_op = "daw.transport_pause" if transport.is_playing else "daw.transport_play"
        row.operator(play_op, text="", icon=play_icon)

        row.operator("daw.transport_stop", text="", icon="SNAP_FACE")

        rec = row.operator(
            "daw.transport_record",
            text="",
            icon="REC",
            depress=transport.is_recording,
        )

        loop_row = layout.row(align=True)
        loop_row.prop(
            transport,
            "loop_enabled",
            text="Loop",
            icon="CON_FOLLOWPATH",
            toggle=True,
        )
        loop_row.prop(transport, "metronome_enabled", text="Metronome", icon="SPEAKER", toggle=True)

        # --- Região de loop ---
        if transport.loop_enabled:
            box = layout.box()
            col = box.column(align=True)
            row = col.row(align=True)
            row.prop(transport, "loop_start", text="Start")
            row.operator("daw.transport_set_loop_start", text="", icon="TRACKING_FORWARDS_SINGLE")
            row = col.row(align=True)
            row.prop(transport, "loop_end", text="End")
            row.operator("daw.transport_set_loop_end", text="", icon="TRACKING_BACKWARDS_SINGLE")

        # --- Tempo / BPM ---
        layout.separator()
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(transport, "bpm")
        row.operator("daw.transport_tap_tempo", text="", icon="TIME")
        row = col.row(align=True)
        row.prop(transport, "beats_per_bar", text="Beats/Bar")
        row = col.row(align=True)
        row.operator("daw.transport_tempo_halve", text="½x")
        row.operator("daw.transport_tempo_double", text="2x")

        # --- Frame atual ---
        layout.separator()
        layout.prop(context.scene, "frame_current", text="Frame")


classes = (DAW_PT_transport,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)