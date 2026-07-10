# modules/export/flac.py
"""
Exportador FLAC.

Responsabilidade:
    Transcodificar um .wav (gerado por wav.py) para .flac (sem perdas)
    usando o `ffmpeg` do sistema. Ver mp3.py para a nota completa sobre
    por que a transcodificação via ffmpeg é usada em vez de um encoder
    puro-Python.
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple, Union

from .utils import run_ffmpeg, ensure_extension

DEFAULT_COMPRESSION_LEVEL = 5  # 0 (rápido/maior) - 8 (lento/menor), sempre sem perdas


def export_wav_to_flac(
    wav_path: Union[str, Path],
    flac_path: Union[str, Path],
    compression_level: int = DEFAULT_COMPRESSION_LEVEL,
) -> Tuple[bool, str]:
    """
    Transcodifica `wav_path` para `flac_path` via ffmpeg.
    Retorna (sucesso, mensagem).
    """
    wav_path = Path(wav_path)
    if not wav_path.exists():
        return False, f"Arquivo WAV de origem não encontrado: {wav_path}"

    flac_path = ensure_extension(flac_path, "flac")
    flac_path.parent.mkdir(parents=True, exist_ok=True)

    compression_level = max(0, min(8, compression_level))

    args = [
        "-i", str(wav_path),
        "-codec:a", "flac",
        "-compression_level", str(compression_level),
        str(flac_path),
    ]

    ok, message = run_ffmpeg(args)
    if ok:
        return True, f"FLAC exportado: {flac_path}"
    return False, message