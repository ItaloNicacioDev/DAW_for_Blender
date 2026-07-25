# modules/render/operators.py
"""
Operadores do módulo Render.
"""
from __future__ import annotations

import os
import time

import bpy
from bpy.types import Operator

from .audio import render_mixdown, normalize_wav_file
from .stems import render_stems
from .video import render_video
from .animation import start_render_tracking, stop_render_tracking
from .utils import (
    ensure_render_dir,
    sanitize_filename,
    refresh_stem_list,
    find_ffmpeg,
    mux_audio_video,
    format_duration,
)


class DAW_OT_render_refresh_stems(Operator):
    bl_idname = "daw.render_refresh_stems"
    bl_label = "Atualizar Lista de Stems"
    bl_description = "Sincroniza a lista de stems com os canais de áudio do sequencer"
    bl_options = {'REGISTER'}

    def execute(self, context):
        refresh_stem_list(context)
        settings = context.scene.daw_render_settings
        self.report({'INFO'}, f"{len(settings.stems)} stem(s) encontrado(s)")
        return {'FINISHED'}


class DAW_OT_render_cancel(Operator):
    bl_idname = "daw.render_cancel"
    bl_label = "Cancelar Renderização"
    bl_description = "Sinaliza o cancelamento da renderização em andamento"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.scene.daw_render_settings.is_rendering

    def execute(self, context):
        settings = context.scene.daw_render_settings
        settings.render_cancelled = True
        settings.render_status_text = "Cancelando..."
        self.report({'INFO'}, "Cancelamento solicitado")
        return {'FINISHED'}


class DAW_OT_render_open_output_folder(Operator):
    bl_idname = "daw.render_open_output_folder"
    bl_label = "Abrir Pasta de Saída"
    bl_description = "Abre a pasta de saída da renderização no navegador de arquivos do sistema"
    bl_options = {'REGISTER'}

    def execute(self, context):
        out_dir = ensure_render_dir(context)
        try:
            bpy.ops.wm.path_open(filepath=out_dir)
        except Exception as e:
            self.report({'ERROR'}, f"Não foi possível abrir a pasta: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}


class DAW_OT_render_start(Operator):
    bl_idname = "daw.render_start"
    bl_label = "Renderizar"
    bl_description = "Renderiza mixdown, stems e/ou vídeo conforme as configurações"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.daw_render_settings
        return not settings.is_rendering and (
            settings.render_mixdown or settings.render_stems or settings.render_video
        )

    def execute(self, context):
        scene = context.scene
        settings = scene.daw_render_settings

        if not (settings.render_mixdown or settings.render_stems or settings.render_video):
            self.report({'WARNING'}, "Nenhum tipo de renderização selecionado")
            return {'CANCELLED'}

        settings.is_rendering = True
        settings.render_cancelled = False
        settings.render_progress = 0.0
        started_at = time.time()

        out_dir = ensure_render_dir(context)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base_name = sanitize_filename(scene.name or "daw_render")

        mixdown_path = None
        video_path = None

        try:
            # --- Mixdown master ------------------------------------------------
            if settings.render_mixdown and not settings.render_cancelled:
                settings.render_status_text = "Renderizando mixdown..."
                filename = f"{base_name}_mix_{timestamp}.{settings.audio_format.lower()}"
                mixdown_path = os.path.join(out_dir, filename)

                ok, info = render_mixdown(context, mixdown_path)
                if not ok:
                    self.report({'ERROR'}, f"Falha no mixdown: {info}")
                    mixdown_path = None
                else:
                    if settings.normalize_audio and settings.audio_format == 'WAV':
                        normalize_wav_file(mixdown_path, settings.normalize_target_db)
                    settings.render_progress = 0.34

            # --- Stems --------------------------------------------------------
            if settings.render_stems and not settings.render_cancelled:
                settings.render_status_text = "Renderizando stems..."
                stems_dir = os.path.join(out_dir, f"stems_{timestamp}")
                os.makedirs(stems_dir, exist_ok=True)
                generated = render_stems(context, stems_dir, report=self.report)
                self.report({'INFO'}, f"{len(generated)} stem(s) exportado(s)")
                settings.render_progress = 0.67

            # --- Vídeo ----------------------------------------------------------
            if settings.render_video and not settings.render_cancelled:
                settings.render_status_text = "Renderizando vídeo..."
                start_render_tracking()
                try:
                    video_noext = os.path.join(out_dir, f"{base_name}_video_{timestamp}")
                    ok, info = render_video(context, video_noext)
                finally:
                    stop_render_tracking()

                if not ok:
                    self.report({'ERROR'}, f"Falha ao renderizar vídeo: {info}")
                    video_path = None
                else:
                    video_path = info
                    settings.render_progress = 0.9

                    if settings.mux_audio_video and mixdown_path and video_path:
                        settings.render_status_text = "Combinando áudio e vídeo..."
                        ffmpeg_bin = find_ffmpeg(settings)
                        if not ffmpeg_bin:
                            self.report(
                                {'WARNING'},
                                "ffmpeg não encontrado; vídeo e áudio foram exportados separadamente",
                            )
                        else:
                            ext = os.path.splitext(video_path)[1]
                            final_path = os.path.join(out_dir, f"{base_name}_final_{timestamp}{ext}")
                            muxed_ok, log = mux_audio_video(
                                ffmpeg_bin, video_path, mixdown_path, final_path
                            )
                            if muxed_ok:
                                self.report({'INFO'}, f"Vídeo final: {final_path}")
                            else:
                                self.report({'WARNING'}, f"Falha ao combinar áudio/vídeo: {log[:200]}")

            settings.render_progress = 1.0
            elapsed = format_duration(time.time() - started_at)
            if settings.render_cancelled:
                settings.render_status_text = f"Renderização cancelada ({elapsed})"
            else:
                settings.render_status_text = f"Renderização concluída em {elapsed}"

        finally:
            settings.is_rendering = False

        return {'FINISHED'}


classes = [
    DAW_OT_render_refresh_stems,
    DAW_OT_render_cancel,
    DAW_OT_render_open_output_folder,
    DAW_OT_render_start,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)