# modules/recorder/ui.py
"""
Interface do usuário do módulo Recorder.
"""
from __future__ import annotations

import bpy
from bpy.types import Panel, UIList

from .utils import frames_to_timecode, peak_to_db


class DAW_UL_recorder_armed_tracks(UIList):
    """Lista as tracks atualmente armadas para gravação."""

    bl_idname = "DAW_UL_recorder_armed_tracks"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.name or f"Track {item.track_index}", icon='REC')
        op = row.operator("daw.recorder_disarm_track", text="", icon='X', emboss=False)
        op.track_index = item.track_index


class DAW_PT_recorder_panel(Panel):
    """Painel principal: transporte de gravação."""

    bl_idname = "DAW_PT_recorder_panel"
    bl_label = "Recorder"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_recorder_settings

        if settings.is_recording:
            label = "Retomar" if settings.is_paused else "Pausar"
            icon = 'PLAY' if settings.is_paused else 'PAUSE'

            row = layout.row(align=True)
            row.scale_y = 1.4
            row.operator("daw.recorder_pause", text=label, icon=icon)
            row.operator("daw.recorder_stop", text="Parar", icon='SNAP_FACE')

            timecode = frames_to_timecode(
                context.scene.frame_current - settings.record_start_frame,
                context.scene.render.fps,
            )
            box = layout.box()
            row = box.row()
            row.label(text=timecode, icon='TIME')
            if settings.is_paused:
                row.label(text="PAUSADO", icon='PAUSE')
        else:
            row = layout.row()
            row.scale_y = 1.4
            row.operator("daw.recorder_start", text="Gravar", icon='REC')

            armed_count = len(settings.armed_tracks)
            if armed_count == 0:
                layout.label(text="Nenhuma track armada", icon='ERROR')


class DAW_PT_recorder_input(Panel):
    """Sub-painel: dispositivo de entrada, ganho e medidores de nível."""

    bl_idname = "DAW_PT_recorder_input"
    bl_label = "Entrada"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_recorder_panel"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_recorder_settings

        row = layout.row(align=True)
        row.prop(settings, "input_device", text="")
        row.operator("daw.recorder_refresh_devices", text="", icon='FILE_REFRESH')

        layout.prop(settings, "input_gain_db")
        layout.prop(
            settings, "monitor_input",
            toggle=True,
            icon='HIDE_OFF' if settings.monitor_input else 'HIDE_ON',
        )

        col = layout.column(align=True)
        col.label(text="Nível de Entrada")

        peak_db = peak_to_db(settings.current_peak)
        rms_db = peak_to_db(settings.current_rms)

        row = col.row()
        row.progress(factor=min(settings.current_peak, 1.0), text=f"Peak  {peak_db:6.1f} dB")

        row = col.row()
        row.progress(factor=min(settings.current_rms, 1.0), text=f"RMS   {rms_db:6.1f} dB")


class DAW_PT_recorder_format(Panel):
    """Sub-painel: formato de arquivo e caminho de exportação."""

    bl_idname = "DAW_PT_recorder_format"
    bl_label = "Formato"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_recorder_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_recorder_settings

        layout.prop(settings, "record_format")
        layout.prop(settings, "bit_depth")
        layout.prop(settings, "sample_rate")
        layout.prop(settings, "export_path")


class DAW_PT_recorder_timing(Panel):
    """Sub-painel: pre-roll, contagem regressiva e punch in/out."""

    bl_idname = "DAW_PT_recorder_timing"
    bl_label = "Punch / Pre-roll"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_recorder_panel"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_recorder_settings

        layout.prop(settings, "count_in_enabled")
        layout.prop(settings, "pre_roll_beats")

        layout.separator()

        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(settings, "punch_in", toggle=True)
        row.prop(settings, "punch_out", toggle=True)

        if settings.punch_in:
            col.prop(settings, "punch_in_frame")
        if settings.punch_out:
            col.prop(settings, "punch_out_frame")


class DAW_PT_recorder_tracks(Panel):
    """Sub-painel: gerenciamento de tracks armadas para gravação."""

    bl_idname = "DAW_PT_recorder_tracks"
    bl_label = "Tracks Armadas"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_recorder_panel"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_recorder_settings

        layout.template_list(
            "DAW_UL_recorder_armed_tracks", "",
            settings, "armed_tracks",
            settings, "active_arm_index",
            rows=3,
        )

        row = layout.row(align=True)
        row.operator("daw.recorder_arm_track", text="Armar Strip Ativa", icon='ADD')
        row.operator("daw.recorder_disarm_all", text="", icon='TRASH')


classes = [
    DAW_UL_recorder_armed_tracks,
    DAW_PT_recorder_panel,
    DAW_PT_recorder_input,
    DAW_PT_recorder_format,
    DAW_PT_recorder_timing,
    DAW_PT_recorder_tracks,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)