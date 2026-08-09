# modules/render/video.py
"""
Engine de renderização de vídeo.
"""
from __future__ import annotations

import os

import bpy

from .utils import get_render_range


_CONTAINER_FFMPEG_FORMAT = {
    'MP4': 'MPEG4',
    'MOV': 'QUICKTIME',
    'MKV': 'MKV',
}

_CODEC_FFMPEG = {
    'H264': 'H264',
    'H265': 'H265',
}

_EXTENSION = {
    'MP4': '.mp4',
    'MOV': '.mov',
    'MKV': '.mkv',
}


def _ffmpeg_available(context) -> bool:
    """
    Verifica se este build do Blender tem suporte a FFmpeg compilado.

    Builds da Steam do Blender historicamente NÃO incluem FFmpeg (motivo:
    licenciamento de codec) -- nesse caso 'FFMPEG' nem aparece nos itens
    válidos de render.image_settings.file_format, e tentar setar isso
    direto derruba com TypeError em vez de um erro claro.
    """
    try:
        prop = context.scene.render.image_settings.bl_rna.properties["file_format"]
        valid_ids = {item.identifier for item in prop.enum_items}
    except (AttributeError, KeyError):
        return False
    return "FFMPEG" in valid_ids


def _configure_render_settings(context, filepath_noext: str):
    """Aplica as configurações do módulo Render às configurações de render da cena."""
    scene = context.scene
    settings = scene.daw_render_settings
    render = scene.render

    render.filepath = filepath_noext
    render.resolution_x = settings.video_resolution_x
    render.resolution_y = settings.video_resolution_y
    render.resolution_percentage = 100
    render.fps = settings.video_fps

    start, end = get_render_range(context)
    scene.frame_start = start
    scene.frame_end = end

    render.image_settings.file_format = 'FFMPEG'
    render.ffmpeg.format = _CONTAINER_FFMPEG_FORMAT.get(settings.video_container, 'MPEG4')
    render.ffmpeg.codec = _CODEC_FFMPEG.get(settings.video_codec, 'H264')
    render.ffmpeg.constant_rate_factor = 'HIGH'
    # O áudio do vídeo renderizado é desabilitado aqui; quando necessário, o
    # mix master é combinado depois via ffmpeg externo (ver utils.mux_audio_video),
    # o que permite normalização e formatos de áudio independentes do vídeo.
    render.ffmpeg.audio_codec = 'NONE'


def render_video(context, filepath_noext: str) -> tuple[bool, str]:
    """Renderiza a animação da cena/sequencer como vídeo (sem áudio embutido).

    Retorna (sucesso, caminho_final_ou_mensagem_de_erro). As configurações de
    render da cena são restauradas ao final (filepath e formato de imagem).
    """
    settings = context.scene.daw_render_settings

    if not _ffmpeg_available(context):
        return False, (
            "Este Blender não tem suporte a FFmpeg compilado (comum na "
            "versão da Steam, por causa de licenciamento de codec). "
            "Renderização de vídeo com áudio/codec H264 não é possível "
            "nesta instalação -- baixe o Blender direto de blender.org "
            "se precisar dessa funcionalidade."
        )

    prev_filepath = context.scene.render.filepath
    prev_format = context.scene.render.image_settings.file_format

    _configure_render_settings(context, filepath_noext)

    try:
        result = bpy.ops.render.render(animation=True)
    except Exception as e:
        return False, str(e)
    finally:
        context.scene.render.filepath = prev_filepath
        context.scene.render.image_settings.file_format = prev_format

    if 'CANCELLED' in result:
        return False, "Renderização de vídeo cancelada"

    ext = _EXTENSION.get(settings.video_container, '.mp4')
    final_path = filepath_noext + ext

    return os.path.isfile(final_path), final_path


classes = []


def register():
    pass


def unregister():
    pass