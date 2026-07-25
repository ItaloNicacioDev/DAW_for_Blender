# modules/render/properties.py
"""
Propriedades e estados do módulo Render.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
    CollectionProperty,
)
from bpy.types import PropertyGroup


class DAW_RenderStemItem(PropertyGroup):
    """Representa uma track/canal de áudio disponível para exportação como stem."""

    channel_index: IntProperty()
    name: StringProperty()
    include: BoolProperty(
        name="Incluir",
        description="Inclui este canal na exportação de stems",
        default=True,
    )


class DAW_RenderSettings(PropertyGroup):
    bl_idname = "DAW_RenderSettings"

    # --- Geral -----------------------------------------------------------
    output_path: StringProperty(
        name="Pasta de Saída",
        description="Diretório onde os arquivos renderizados serão salvos",
        subtype='DIR_PATH',
        default="//render/",
    )

    render_range_mode: EnumProperty(
        name="Intervalo",
        items=[
            ('SCENE', "Cena Completa", "Usa o intervalo de frames da cena"),
            ('CUSTOM', "Personalizado", "Define um intervalo customizado"),
        ],
        default='SCENE',
    )

    range_start: IntProperty(name="Início", default=0, min=0)
    range_end: IntProperty(name="Fim", default=250, min=0)

    # --- Áudio -------------------------------------------------------------
    render_mixdown: BoolProperty(
        name="Renderizar Mixdown",
        description="Exporta o mix master (todas as tracks de áudio combinadas)",
        default=True,
    )

    render_stems: BoolProperty(
        name="Renderizar Stems",
        description="Exporta cada canal de áudio separadamente",
        default=False,
    )

    audio_format: EnumProperty(
        name="Formato de Áudio",
        items=[
            ('WAV', "WAV", "Waveform Audio File Format"),
            ('FLAC', "FLAC", "Free Lossless Audio Codec"),
            ('MP3', "MP3", "MPEG Audio Layer III"),
            ('OGG', "OGG Vorbis", "Ogg Vorbis"),
        ],
        default='WAV',
    )

    bit_depth: EnumProperty(
        name="Bits",
        items=[
            ('16', "16-bit", "CD Quality"),
            ('24', "24-bit", "Studio Quality"),
            ('32', "32-bit Float", "Professional"),
        ],
        default='24',
    )

    sample_rate: EnumProperty(
        name="Sample Rate",
        items=[
            ('44100', "44.1 kHz", "CD Standard"),
            ('48000', "48 kHz", "Video Standard"),
            ('96000', "96 kHz", "High Resolution"),
        ],
        default='48000',
    )

    normalize_audio: BoolProperty(
        name="Normalizar",
        description="Normaliza o áudio renderizado ao pico alvo antes de finalizar",
        default=False,
    )

    normalize_target_db: FloatProperty(
        name="Alvo (dB)",
        default=-1.0,
        min=-24.0,
        max=0.0,
    )

    stems: CollectionProperty(type=DAW_RenderStemItem)
    active_stem_index: IntProperty(default=0)

    # --- Vídeo ---------------------------------------------------------------
    render_video: BoolProperty(
        name="Renderizar Vídeo",
        description="Renderiza a animação da cena/sequencer como vídeo",
        default=False,
    )

    video_container: EnumProperty(
        name="Container",
        items=[
            ('MP4', "MP4", "MPEG-4"),
            ('MOV', "MOV", "QuickTime"),
            ('MKV', "MKV", "Matroska"),
        ],
        default='MP4',
    )

    video_codec: EnumProperty(
        name="Codec",
        items=[
            ('H264', "H.264", "AVC"),
            ('H265', "H.265", "HEVC"),
        ],
        default='H264',
    )

    video_resolution_x: IntProperty(name="Largura", default=1920, min=4)
    video_resolution_y: IntProperty(name="Altura", default=1080, min=4)
    video_fps: IntProperty(name="FPS", default=24, min=1, max=240)

    mux_audio_video: BoolProperty(
        name="Combinar Áudio e Vídeo",
        description="Usa ffmpeg para combinar o mixdown de áudio com o vídeo renderizado",
        default=True,
    )

    ffmpeg_path: StringProperty(
        name="Caminho do ffmpeg",
        description="Caminho para o executável ffmpeg (deixe vazio para procurar no PATH do sistema)",
        subtype='FILE_PATH',
        default="",
    )

    # --- Estado / Progresso ------------------------------------------------
    is_rendering: BoolProperty(default=False)
    render_cancelled: BoolProperty(default=False)
    render_progress: FloatProperty(default=0.0, min=0.0, max=1.0)
    render_status_text: StringProperty(default="")


classes = [
    DAW_RenderStemItem,
    DAW_RenderSettings,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_render_settings = PointerProperty(type=DAW_RenderSettings)


def unregister():
    del bpy.types.Scene.daw_render_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)