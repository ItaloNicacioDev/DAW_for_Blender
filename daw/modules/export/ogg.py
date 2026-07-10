# modules/export/ogg.py
"""
Exportador OGG Vorbis.

Responsabilidade:
    Transcodificar um .wav (gerado por wav.py) para .ogg (codec Vorbis)
    usando o `ffmpeg` do sistema. Ver mp3.py para a nota completa sobre
    por que a transcodificação via ffmpeg é usada em vez de um encoder
    puro-Python.
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple, Union

from .utils import run_ffmpeg, ensure_extension

# Qualidade do Vorbis: -1 (pior) a 10 (melhor); ~5-6 é um bom padrão para música
DEFAULT_QUALITY = 6
MIN_QUALITY = -1
MAX_QUALITY = 10


def export_wav_to_ogg(
    wav_path: Union[str, Path],
    ogg_path: Union[str, Path],
    quality: float = DEFAULT_QUALITY,
) -> Tuple[bool, str]:
    """
    Transcodifica `wav_path` para `ogg_path` via ffmpeg.
    Retorna (sucesso, mensagem).
    """
    wav_path = Path(wav_path)
    if not wav_path.exists():
        return False, f"Arquivo WAV de origem não encontrado: {wav_path}"

    ogg_path = ensure_extension(ogg_path, "ogg")
    ogg_path.parent.mkdir(parents=True, exist_ok=True)

    quality = max(MIN_QUALITY, min(MAX_QUALITY, quality))

    args = [
        "-i", str(wav_path),
        "-codec:a", "libvorbis",
        "-qscale:a", str(quality),
        str(ogg_path),
    ]

    ok, message = run_ffmpeg(args)
    if ok:
        return True, f"OGG exportado: {ogg_path}"
    return False, message