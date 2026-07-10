# modules/export/utils.py
"""
Utilitários do módulo de Exportação.

Responsabilidade:
    Funções auxiliares compartilhadas pelos exportadores: checagem do
    ffmpeg (usado por mp3.py/ogg.py/flac.py para transcodificar o WAV
    gerado por wav.py), extração das notas da cena, caminhos temporários
    e normalização de extensão de arquivo.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .wav import ExportNote


def check_ffmpeg_available() -> bool:
    """Retorna True se o executável `ffmpeg` estiver disponível no PATH do sistema."""
    return shutil.which("ffmpeg") is not None


def ensure_extension(filepath: Union[str, Path], extension: str) -> Path:
    """Garante que `filepath` termine com `.extension` (adiciona se faltar)."""
    filepath = Path(filepath)
    extension = extension.lower().lstrip(".")
    if filepath.suffix.lower() != f".{extension}":
        filepath = filepath.with_suffix(f".{extension}")
    return filepath


def make_temp_wav_path(prefix: str = "daw_export_") -> Path:
    """Cria um caminho temporário único para um .wav intermediário (usado antes da transcodificação)."""
    handle = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".wav", delete=False)
    handle.close()
    return Path(handle.name)


def run_ffmpeg(args: List[str]) -> Tuple[bool, str]:
    """
    Executa o ffmpeg com os argumentos dados (sem o nome do executável).
    Retorna (sucesso, mensagem). Nunca levanta exceção — erros viram (False, msg).
    """
    if not check_ffmpeg_available():
        return False, "ffmpeg não encontrado no PATH do sistema. Instale o ffmpeg para exportar neste formato."

    cmd = ["ffmpeg", "-y", *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return False, "ffmpeg excedeu o tempo limite (300s)."
    except OSError as e:
        return False, f"Falha ao executar ffmpeg: {e}"

    if result.returncode != 0:
        # Últimas linhas do stderr costumam ter o motivo real do erro
        tail = "\n".join(result.stderr.strip().splitlines()[-5:])
        return False, f"ffmpeg retornou erro ({result.returncode}):\n{tail}"

    return True, "OK"


def get_notes_from_scene(context) -> Tuple[List[ExportNote], float]:
    """
    Extrai as notas do Piano Roll (context.scene.piano_roll.notes) e o BPM
    do projeto (context.scene.daw.bpm), convertendo para o formato
    independente de bpy usado pelos exportadores (wav.py / midi.py).
    """
    notes: List[ExportNote] = []

    piano_roll = getattr(context.scene, "piano_roll", None)
    if piano_roll is not None:
        for n in piano_roll.notes:
            notes.append(ExportNote(
                pitch=n.pitch,
                start=n.start,
                length=n.length,
                velocity=n.velocity,
            ))

    daw_props = getattr(context.scene, "daw", None)
    bpm = daw_props.bpm if daw_props is not None else 120.0

    return notes, bpm


def cleanup_temp_file(filepath: Optional[Union[str, Path]]) -> None:
    """Remove um arquivo temporário silenciosamente (usado após transcodificar)."""
    if not filepath:
        return
    try:
        Path(filepath).unlink(missing_ok=True)
    except OSError:
        pass