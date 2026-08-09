# modules/render/audio.py
"""
Engine de renderização de áudio (mixdown master do sequencer).
"""
from __future__ import annotations

import os
import struct
import wave

import bpy
import numpy as np


# Mapeia o formato de áudio escolhido pelo usuário para os enums usados
# por bpy.ops.sound.mixdown (container/codec do VSE).
_CONTAINER_CODEC = {
    'WAV': ('WAV', 'PCM'),
    'FLAC': ('FLAC', 'FLAC'),
    'MP3': ('MP3', 'MP3'),
    'OGG': ('OGG', 'VORBIS'),
}

_BITDEPTH_FORMAT = {
    '16': 'S16',
    '24': 'S24',
    '32': 'F32',
}


def _mixdown_kwargs(settings) -> dict:
    container, codec = _CONTAINER_CODEC.get(settings.audio_format, ('WAV', 'PCM'))
    fmt = _BITDEPTH_FORMAT.get(settings.bit_depth, 'S16')
    return {
        "container": container,
        "codec": codec,
        "format": fmt,
        "bitrate": 320 if codec in ('MP3', 'VORBIS') else 192,
        # A API do bpy.ops.sound.mixdown usa "mixrate" (não "samplerate")
        # para a taxa de amostragem -- nome mudou em algum momento das
        # versões do Blender; "samplerate" nunca existiu como parâmetro.
        "mixrate": int(settings.sample_rate),
    }


def render_mixdown(context, filepath: str) -> tuple[bool, str]:
    """Renderiza o mixdown master do sequencer para `filepath`.

    Usa o operador nativo `bpy.ops.sound.mixdown`, que combina todas as
    strips de áudio visíveis (não mutadas) do sequence editor em um único
    arquivo. Retorna (sucesso, caminho_ou_mensagem_de_erro).
    """
    settings = context.scene.daw_render_settings
    kwargs = _mixdown_kwargs(settings)

    try:
        result = bpy.ops.sound.mixdown(
            filepath=filepath,
            check_existing=False,
            relative_path=False,
            accuracy=1024,
            split_channels=False,
            **kwargs,
        )
    except TypeError as e:
        # Parâmetro não reconhecido nesta versão do Blender (a API do
        # bpy.ops.sound.mixdown já mudou nome de parâmetro antes --
        # "samplerate" virou "mixrate"). Em vez de travar o mixdown
        # inteiro por causa de 1 kwarg desatualizado, tenta de novo sem
        # ele (usa a taxa padrão do Blender) e avisa no retorno.
        stray_kwargs = {k: v for k, v in kwargs.items() if k in str(e)}
        if stray_kwargs:
            fallback_kwargs = {k: v for k, v in kwargs.items() if k not in stray_kwargs}
            try:
                result = bpy.ops.sound.mixdown(
                    filepath=filepath,
                    check_existing=False,
                    relative_path=False,
                    accuracy=1024,
                    split_channels=False,
                    **fallback_kwargs,
                )
            except Exception as e2:
                return False, str(e2)
        else:
            return False, str(e)
    except Exception as e:
        return False, str(e)

    if 'FINISHED' not in result:
        return False, "bpy.ops.sound.mixdown não finalizou corretamente"

    return os.path.isfile(filepath), filepath


def _read_wav_as_float(filepath: str) -> tuple[np.ndarray, int, int]:
    """Lê um WAV PCM (16/24-bit inteiro ou 32-bit float) como array float32 em [-1, 1]."""
    with wave.open(filepath, 'rb') as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        samplerate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    if sampwidth == 2:
        data = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    elif sampwidth == 3:
        count = len(raw) // 3
        ints = np.zeros(count, dtype=np.int32)
        for i in range(count):
            chunk = raw[i * 3:i * 3 + 3]
            sign_ext = b'\xff' if chunk[2] & 0x80 else b'\x00'
            ints[i] = struct.unpack('<i', chunk + sign_ext)[0]
        data = ints.astype(np.float32) / 8388608.0
    elif sampwidth == 4:
        data = np.frombuffer(raw, dtype='<f4').astype(np.float32)
    else:
        raise ValueError(f"Sample width não suportado: {sampwidth}")

    if channels > 1:
        data = data.reshape(-1, channels)

    return data, samplerate, channels


def normalize_wav_file(filepath: str, target_db: float = -1.0) -> bool:
    """Normaliza um arquivo WAV in-place ao nível de pico alvo (dB).

    A regravação é feita em PCM 16-bit por simplicidade. Retorna False se o
    arquivo não puder ser lido/normalizado (ex.: silêncio total ou formato
    incompatível).
    """
    try:
        data, samplerate, channels = _read_wav_as_float(filepath)
    except Exception:
        return False

    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak <= 0.0:
        return False

    target_linear = 10 ** (target_db / 20.0)
    gain = target_linear / peak
    normalized = np.clip(data * gain, -1.0, 1.0)
    ints16 = (normalized * 32767.0).astype('<i2')

    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(ints16.tobytes())

    return True


classes = []


def register():
    pass


def unregister():
    pass