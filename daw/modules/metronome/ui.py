# modules/metronome/ui.py
"""
Painel de UI do Blender para o metrônomo.

Segue o mesmo padrão dos outros painéis do projeto:
    - bl_space_type = 'SEQUENCE_EDITOR' (onde a DAW vive)
    - bl_category   = "DAW"
"""
from __future__ import annotations

from bpy.types import Panel


class DAW_PT_Metronome(Panel):
    bl_label = "Metrônomo"
    bl_idname = "DAW_PT_metronome"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 5

    def draw(self, context):
        layout = self.layout
        daw = context.scene.daw
        metro = context.scene.daw_metronome

        row = layout.row(align=True)
        row.scale_y = 1.3
        icon = 'SPEAKER' if daw.metronome else 'MUTE_IPO_ON'
        row.operator(
            "daw.metronome_toggle",
            text="Metrônomo Ativado" if daw.metronome else "Metrônomo Desativado",
            icon=icon, depress=daw.metronome,
        )

        box = layout.box()
        box.label(text=f"Compasso {daw.current_bar} — Beat {daw.current_beat}", icon='TIME')

        row = box.row(align=True)
        row.prop(daw, "bpm")

        row = box.row(align=True)
        row.operator("daw.metronome_tap_tempo", text="Tap Tempo", icon='RECORD_ON')
        row.operator("daw.metronome_tap_tempo_reset", text="", icon='X')

        box2 = layout.box()
        box2.prop(metro, "sound_style")
        box2.prop(metro, "volume")
        box2.prop(metro, "accent_first_beat")

        row = box2.row(align=True)
        row.prop(metro, "beats_per_bar", text="Beats")
        row.prop(metro, "beat_unit", text="Unidade")

        box2.prop(metro, "sync_with_playback")

        row = box2.row(align=True)
        op = row.operator("daw.metronome_test_click", text="Testar Normal")
        op.accent = False
        op = row.operator("daw.metronome_test_click", text="Testar Acento")
        op.accent = True

        box3 = layout.box()
        box3.prop(metro, "count_in_enabled")
        sub = box3.row()
        sub.enabled = metro.count_in_enabled
        sub.prop(metro, "count_in_bars")


classes = [
    DAW_PT_Metronome,
]