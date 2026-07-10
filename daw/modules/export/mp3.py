# modules/export/mp3.py
"""
Exportador MP3.

Responsabilidade:
    Transcodificar um .wav (gerado por wav.py) para .mp3 usando o `ffmpeg`
    do sistema (codec libmp3lame). O Python não tem um encoder MP3 nativo
    na biblioteca padrão, então esta é a abordagem padrão usada por
    addons do Blender para exportação de áudio.
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple, Union

from .utils import run_ffmpeg, ensure_extension

VALID_BITRATES = (96, 128, 160, 192, 224, 256, 320)
DEFAULT_BITRATE = 192


def export_wav_to_mp3(
    wav_path: Union[str, Path],
    mp3_path: Union[str, Path],
    bitrate_kbps: int = DEFAULT_BITRATE,
) -> Tuple[bool, str]:
    """
    Transcodifica `wav_path` para `mp3_path` via ffmpeg.
    Retorna (sucesso, mensagem).
    """
    wav_path = Path(wav_path)
    if not wav_path.exists():
        return False, f"Arquivo WAV de origem não encontrado: {wav_path}"

    mp3_path = ensure_extension(mp3_path, "mp3")
    mp3_path.parent.mkdir(parents=True, exist_ok=True)

    bitrate = bitrate_kbps if bitrate_kbps in VALID_BITRATES else DEFAULT_BITRATE

    args = [
        "-i", str(wav_path),
        "-codec:a", "libmp3lame",
        "-b:a", f"{bitrate}k",
        str(mp3_path),
    ]

    ok, message = run_ffmpeg(args)
    if ok:
        return True, f"MP3 exportado: {mp3_path}"
    return False, message