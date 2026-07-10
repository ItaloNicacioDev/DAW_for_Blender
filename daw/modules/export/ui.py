# modules/export/ui.py
"""
Painel de UI do Blender para o módulo de Exportação.

Segue o mesmo padrão dos outros painéis do projeto:
    - bl_space_type = 'SEQUENCE_EDITOR' (onde a DAW vive)
    - bl_category   = "DAW"
"""
from __future__ import annotations

import bpy
from bpy.types import Panel

from .utils import check_ffmpeg_available

_FFMPEG_FORMATS = ("MP3", "OGG", "FLAC")


class DAW_PT_Export(Panel):
    bl_label = "Exportar"
    bl_idname = "DAW_PT_export"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 6

    def draw(self, context):
        layout = self.layout
        props = context.scene.daw_export

        layout.prop(props, "format")

        box = layout.box()
        box.prop(props, "export_path")
        box.prop(props, "filename")

        if props.format in ("WAV", "MP3", "OGG", "FLAC"):
            box.prop(props, "sample_rate")
            box.prop(props, "wave_shape")
            box.prop(props, "normalize")

        if props.format == "MP3":
            box.prop(props, "mp3_bitrate")
        elif props.format == "OGG":
            box.prop(props, "ogg_quality")
        elif props.format == "FLAC":
            box.prop(props, "flac_compression")
        elif props.format == "MIDI":
            box.prop(props, "midi_ppq")

        if props.format in _FFMPEG_FORMATS and not check_ffmpeg_available():
            warn = layout.box()
            warn.alert = True
            warn.label(text="ffmpeg não encontrado no sistema", icon='ERROR')
            warn.label(text="Instale o ffmpeg para exportar neste formato")

        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 1.4
        row.operator("daw.export_project", icon='EXPORT')

        row = layout.row(align=True)
        row.operator("daw.open_export_folder", icon='FILE_FOLDER')

        if props.last_export_status:
            status_box = layout.box()
            status_box.alert = not props.last_export_ok
            icon = 'CHECKMARK' if props.last_export_ok else 'ERROR'
            status_box.label(text=props.last_export_status, icon=icon)


classes = [
    DAW_PT_Export,
]