# modules/browser/utils.py
"""
Utilitários do browser — sem bpy, lógica pura de sistema de arquivos.
"""
from __future__ import annotations

import os
import hashlib
from typing import List, Tuple, Optional

# Extensões de áudio suportadas pela DAW
AUDIO_EXTENSIONS = {
    ".wav", ".flac", ".mp3", ".ogg", ".aiff",
    ".aif", ".m4a", ".opus", ".mid", ".midi",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}


def is_audio_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in AUDIO_EXTENSIONS


def is_midi_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in {".mid", ".midi"}


def list_audio_files(directory: str, recursive: bool = False) -> List[str]:
    """Lista todos os arquivos de áudio num diretório."""
    results: List[str] = []
    if not os.path.isdir(directory):
        return results
    if recursive:
        for root, _, files in os.walk(directory):
            for f in sorted(files):
                if is_audio_file(f):
                    results.append(os.path.join(root, f))
    else:
        for f in sorted(os.listdir(directory)):
            full = os.path.join(directory, f)
            if os.path.isfile(full) and is_audio_file(f):
                results.append(full)
    return results


def list_subdirs(directory: str) -> List[str]:
    """Lista subdiretórios imediatos."""
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, d)
        for d in os.listdir(directory)
        if os.path.isdir(os.path.join(directory, d))
        and not d.startswith(".")
    )


def file_size_str(path: str) -> str:
    """Retorna tamanho do arquivo como string legível (KB, MB)."""
    try:
        size = os.path.getsize(path)
        if size < 1024:
            return f"{size} B"
        elif size < 1024 ** 2:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / 1024 ** 2:.1f} MB"
    except OSError:
        return "?"


def file_hash(path: str) -> str:
    """Hash MD5 dos primeiros 64KB do arquivo — para cache de thumbnail."""
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            h.update(f.read(65536))
    except OSError:
        pass
    return h.hexdigest()


def friendly_name(path: str) -> str:
    """Nome do arquivo sem extensão."""
    return os.path.splitext(os.path.basename(path))[0]


def get_extension(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def path_breadcrumbs(path: str) -> List[Tuple[str, str]]:
    """
    Divide um caminho em pares (label, caminho_parcial) para a barra
    de navegação estilo breadcrumb.
    Ex: /home/user/samples → [('home', '/home'), ('user', '/home/user'), ...]
    """
    parts = []
    current = path
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            parts.append((os.path.basename(current) or current, current))
            break
        parts.append((os.path.basename(current), current))
        current = parent
    parts.reverse()
    return parts


def normalize_path(path: str) -> str:
    return os.path.normpath(os.path.expanduser(path))