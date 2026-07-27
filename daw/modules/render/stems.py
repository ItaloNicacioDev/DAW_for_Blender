# modules/render/stems.py
"""
Exportação de stems (tracks/canais individuais) do sequencer.
"""
from __future__ import annotations

import os

from .audio import render_mixdown, normalize_wav_file
from .utils import sanitize_filename, refresh_stem_list, get_all_strips


def _get_sound_strips(context):
    seq = context.scene.sequence_editor
    if seq is None:
        return []
    return [s for s in get_all_strips(seq) if s.type == 'SOUND']


def _solo_channel(strips, channel_index: int) -> dict:
    """Muta todas as strips de som exceto as do canal indicado.

    Retorna um mapa {nome_da_strip: mute_original} para restauração posterior.
    """
    original_mute = {}
    for strip in strips:
        original_mute[strip.name] = strip.mute
        strip.mute = strip.channel != channel_index
    return original_mute


def _restore_mute(strips, original_mute: dict):
    for strip in strips:
        if strip.name in original_mute:
            strip.mute = original_mute[strip.name]


def render_stems(context, out_dir: str, report=None) -> list[str]:
    """Renderiza um arquivo de áudio para cada stem marcado em settings.stems.

    Cada stem é isolado silenciando temporariamente todas as demais strips de
    som e chamando o mesmo mixdown usado para o mix master. O estado original
    de mute das strips é sempre restaurado, mesmo em caso de erro.
    """
    settings = context.scene.daw_render_settings
    strips = _get_sound_strips(context)
    if not strips:
        if report:
            report({'WARNING'}, "Nenhuma strip de áudio encontrada no sequencer")
        return []

    if len(settings.stems) == 0:
        refresh_stem_list(context)

    generated: list[str] = []
    ext = settings.audio_format.lower()

    for item in settings.stems:
        if not item.include:
            continue

        original_mute = _solo_channel(strips, item.channel_index)
        try:
            filename = sanitize_filename(f"{item.name}_ch{item.channel_index}") + f".{ext}"
            filepath = os.path.join(out_dir, filename)

            ok, info = render_mixdown(context, filepath)
            if ok:
                if settings.normalize_audio and settings.audio_format == 'WAV':
                    normalize_wav_file(filepath, settings.normalize_target_db)
                generated.append(filepath)
            elif report:
                report({'WARNING'}, f"Falha ao renderizar stem '{item.name}': {info}")
        finally:
            _restore_mute(strips, original_mute)

    return generated


classes = []


def register():
    pass


def unregister():
    pass