# modules/render/utils.py
"""
Utilitários do módulo Render.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import bpy


def get_all_strips(seq):
    """Retorna todas as strips do sequencer (recursivo), compatível com
    qualquer versão do Blender.

    A partir do Blender 4.4, a API do VSE foi renomeada:
    `SequenceEditor.sequences_all` -> `SequenceEditor.strips_all`.
    Esta função tenta primeiro o nome novo e cai para o antigo se
    necessário, para funcionar tanto em 4.5+ quanto em versões mais
    antigas.
    """
    if seq is None:
        return []
    strips = getattr(seq, 'strips_all', None)
    if strips is not None:
        return strips
    return getattr(seq, 'sequences_all', [])


def ensure_render_dir(context) -> str:
    """Garante que o diretório de saída de render exista e retorna o caminho absoluto."""
    settings = context.scene.daw_render_settings
    path = bpy.path.abspath(settings.output_path)
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def get_render_range(context) -> tuple[int, int]:
    """Retorna (frame_inicial, frame_final) conforme o modo de intervalo configurado."""
    settings = context.scene.daw_render_settings
    if settings.render_range_mode == 'CUSTOM':
        return settings.range_start, settings.range_end
    return context.scene.frame_start, context.scene.frame_end


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos de um nome de arquivo."""
    name = (name or "").strip() or "untitled"
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def get_sequencer_channels(context) -> list[tuple[int, str]]:
    """Retorna (índice_do_canal, nome) de todos os canais com strips de áudio no sequencer."""
    scene = context.scene
    seq = scene.sequence_editor
    if seq is None:
        return []

    channels: dict[int, str] = {}
    for strip in get_all_strips(seq):
        if strip.type == 'SOUND':
            channels.setdefault(strip.channel, strip.name)

    return sorted(channels.items())


def refresh_stem_list(context):
    """Sincroniza a lista de stems com os canais de áudio presentes no sequencer.

    Preserva o estado de `include` de canais já conhecidos.
    """
    settings = context.scene.daw_render_settings
    channels = get_sequencer_channels(context)
    existing = {item.channel_index: item.include for item in settings.stems}

    settings.stems.clear()
    for idx, name in channels:
        item = settings.stems.add()
        item.channel_index = idx
        item.name = name
        item.include = existing.get(idx, True)


def find_ffmpeg(settings=None) -> str | None:
    """Localiza o executável ffmpeg: caminho customizado nas settings, PATH do sistema, ou None."""
    if settings and settings.ffmpeg_path:
        custom = bpy.path.abspath(settings.ffmpeg_path)
        if os.path.isfile(custom):
            return custom

    return shutil.which("ffmpeg")


def mux_audio_video(ffmpeg_bin: str, video_path: str, audio_path: str, output_path: str) -> tuple[bool, str]:
    """Combina uma trilha de vídeo (sem áudio) com um arquivo de áudio via ffmpeg.

    Retorna (sucesso, log). O vídeo é copiado sem recodificar (`-c:v copy`);
    o áudio é recodificado para AAC para garantir compatibilidade com o container.
    """
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "320k",
        "-shortest",
        output_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        ok = result.returncode == 0 and os.path.isfile(output_path)
        log = result.stdout.decode("utf-8", errors="ignore") if result.stdout else ""
        return ok, log
    except Exception as e:
        return False, str(e)


def frames_to_seconds(frame: int, fps: float) -> float:
    return frame / fps if fps else 0.0


def format_duration(seconds: float) -> str:
    """Formata segundos como HH:MM:SS."""
    m, s = divmod(int(max(seconds, 0)), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


classes = []


def register():
    pass


def unregister():
    pass