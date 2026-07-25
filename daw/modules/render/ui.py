# modules/render/ui.py
"""
Interface do usuário do módulo Render.
"""
from __future__ import annotations

import bpy
from bpy.types import Panel, UIList


class DAW_UL_render_stems(UIList):
    """Lista os canais de áudio disponíveis para exportação como stem."""

    bl_idname = "DAW_UL_render_stems"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "include", text="")
        row.label(text=item.name or f"Canal {item.channel_index}", icon='SOUND')


class DAW_PT_render_panel(Panel):
    """Painel principal: intervalo, tipos de renderização e progresso."""

    bl_idname = "DAW_PT_render_panel"
    bl_label = "Render"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_render_settings

        layout.prop(settings, "output_path")

        row = layout.row(align=True)
        row.prop(settings, "render_range_mode", text="")
        if settings.render_range_mode == 'CUSTOM':
            row2 = layout.row(align=True)
            row2.prop(settings, "range_start")
            row2.prop(settings, "range_end")

        layout.separator()

        col = layout.column(align=True)
        col.prop(settings, "render_mixdown")
        col.prop(settings, "render_stems")
        col.prop(settings, "render_video")

        layout.separator()

        if settings.is_rendering:
            box = layout.box()
            box.label(text=settings.render_status_text, icon='RENDER_ANIMATION')
            box.progress(factor=settings.render_progress, text=f"{settings.render_progress * 100:.0f}%")
            box.operator("daw.render_cancel", text="Cancelar", icon='CANCEL')
        else:
            row = layout.row()
            row.scale_y = 1.4
            row.operator("daw.render_start", text="Renderizar", icon='RENDER_ANIMATION')
            if settings.render_status_text:
                layout.label(text=settings.render_status_text)

        layout.operator("daw.render_open_output_folder", text="Abrir Pasta de Saída", icon='FILE_FOLDER')


class DAW_PT_render_audio(Panel):
    """Sub-painel: formato, bit depth, sample rate e normalização do mixdown."""

    bl_idname = "DAW_PT_render_audio"
    bl_label = "Áudio"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_render_panel"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_render_settings

        layout.prop(settings, "audio_format")
        layout.prop(settings, "bit_depth")
        layout.prop(settings, "sample_rate")

        row = layout.row(align=True)
        row.prop(settings, "normalize_audio", toggle=True)
        if settings.normalize_audio:
            row.prop(settings, "normalize_target_db", text="Alvo")


class DAW_PT_render_stems(Panel):
    """Sub-painel: lista de stems a exportar, um por canal de áudio."""

    bl_idname = "DAW_PT_render_stems"
    bl_label = "Stems"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_render_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.daw_render_settings.render_stems

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_render_settings

        layout.template_list(
            "DAW_UL_render_stems", "",
            settings, "stems",
            settings, "active_stem_index",
            rows=4,
        )
        layout.operator("daw.render_refresh_stems", text="Atualizar Lista", icon='FILE_REFRESH')


class DAW_PT_render_video(Panel):
    """Sub-painel: resolução, fps, codec/container e mux com o mixdown."""

    bl_idname = "DAW_PT_render_video"
    bl_label = "Vídeo"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_render_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.daw_render_settings.render_video

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_render_settings

        row = layout.row(align=True)
        row.prop(settings, "video_resolution_x", text="X")
        row.prop(settings, "video_resolution_y", text="Y")

        layout.prop(settings, "video_fps")
        layout.prop(settings, "video_container")
        layout.prop(settings, "video_codec")

        layout.separator()
        layout.prop(settings, "mux_audio_video")
        if settings.mux_audio_video:
            layout.prop(settings, "ffmpeg_path")
            if not settings.render_mixdown:
                layout.label(text="Ative o Mixdown para combinar áudio", icon='ERROR')


classes = [
    DAW_UL_render_stems,
    DAW_PT_render_panel,
    DAW_PT_render_audio,
    DAW_PT_render_stems,
    DAW_PT_render_video,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)