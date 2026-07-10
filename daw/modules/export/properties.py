# modules/export/properties.py
"""
Propriedades RNA do Blender para o módulo de Exportação.

Estas propriedades ficam em context.scene.daw_export e guardam as
configurações escolhidas pelo usuário (formato, caminho, qualidade) antes
de disparar o operador de exportação (operators.py).
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .mp3 import VALID_BITRATES, DEFAULT_BITRATE
from .ogg import DEFAULT_QUALITY as OGG_DEFAULT_QUALITY, MIN_QUALITY as OGG_MIN_Q, MAX_QUALITY as OGG_MAX_Q
from .flac import DEFAULT_COMPRESSION_LEVEL
from .midi import DEFAULT_PPQ
from .wav import WAVE_SHAPES

FORMAT_ITEMS = (
    ("WAV", "WAV", "Áudio sem perdas — gerado localmente, sem dependências externas"),
    ("MP3", "MP3", "Áudio comprimido com perdas — requer ffmpeg instalado"),
    ("OGG", "OGG Vorbis", "Áudio comprimido com perdas — requer ffmpeg instalado"),
    ("FLAC", "FLAC", "Áudio comprimido sem perdas — requer ffmpeg instalado"),
    ("MIDI", "MIDI", "Notas do Piano Roll — gerado localmente, sem dependências externas"),
)

SAMPLE_RATE_ITEMS = (
    ("44100", "44.1 kHz", "Padrão de CD"),
    ("48000", "48 kHz", "Padrão de vídeo/streaming"),
    ("96000", "96 kHz", "Alta resolução"),
)

WAVE_SHAPE_ITEMS = tuple((s, s.title(), "") for s in WAVE_SHAPES)


class ExportProperties(PropertyGroup):
    """Configurações de exportação — anexadas a context.scene.daw_export."""

    format: EnumProperty(
        name="Formato",
        description="Formato do arquivo a exportar",
        items=FORMAT_ITEMS,
        default="WAV",
    )

    export_path: StringProperty(
        name="Pasta",
        description="Pasta de destino da exportação",
        default="//",
        subtype='DIR_PATH',
    )

    filename: StringProperty(
        name="Nome do Arquivo",
        description="Nome do arquivo exportado (sem extensão)",
        default="export",
    )

    sample_rate: EnumProperty(
        name="Sample Rate",
        description="Taxa de amostragem do áudio renderizado",
        items=SAMPLE_RATE_ITEMS,
        default="44100",
    )

    wave_shape: EnumProperty(
        name="Forma de Onda",
        description="Forma de onda usada pelo sintetizador interno ao renderizar o WAV base",
        items=WAVE_SHAPE_ITEMS,
        default="SINE",
    )

    normalize: BoolProperty(
        name="Normalizar",
        description="Normaliza o volume do áudio renderizado para evitar clipping",
        default=True,
    )

    # --- MP3 ---
    mp3_bitrate: EnumProperty(
        name="Bitrate",
        description="Taxa de bits do MP3 (kbps)",
        items=[(str(b), f"{b} kbps", "") for b in VALID_BITRATES],
        default=str(DEFAULT_BITRATE),
    )

    # --- OGG ---
    ogg_quality: FloatProperty(
        name="Qualidade",
        description="Qualidade do Vorbis (-1 pior — 10 melhor)",
        default=OGG_DEFAULT_QUALITY,
        min=OGG_MIN_Q,
        max=OGG_MAX_Q,
    )

    # --- FLAC ---
    flac_compression: IntProperty(
        name="Compressão",
        description="Nível de compressão do FLAC (0 rápido/maior — 8 lento/menor, sempre sem perdas)",
        default=DEFAULT_COMPRESSION_LEVEL,
        min=0,
        max=8,
    )

    # --- MIDI ---
    midi_ppq: IntProperty(
        name="PPQ",
        description="Pulsos por semínima (resolução temporal do MIDI exportado)",
        default=DEFAULT_PPQ,
        min=24,
        max=1920,
    )

    # --- Estado / feedback da UI ---
    last_export_status: StringProperty(
        name="Status",
        description="Resultado da última exportação",
        default="",
    )

    last_export_ok: BoolProperty(default=True)


def register() -> None:
    bpy.utils.register_class(ExportProperties)
    bpy.types.Scene.daw_export = bpy.props.PointerProperty(type=ExportProperties)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "daw_export"):
        del bpy.types.Scene.daw_export
    bpy.utils.unregister_class(ExportProperties)