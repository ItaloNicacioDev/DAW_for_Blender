# modules/sampler/utils.py
"""
Utilitários do módulo Sampler.
"""
from __future__ import annotations

import math
import os
import struct

import numpy as np

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def midi_note_to_name(note: int) -> str:
    """Converte um número de nota MIDI (0-127) em nome (ex.: 'C4')."""
    note = int(min(max(note, 0), 127))
    name = NOTE_NAMES[note % 12]
    octave = note // 12 - 1
    return f"{name}{octave}"


def midi_note_to_freq(note: int, a4_freq: float = 440.0) -> float:
    """Converte uma nota MIDI em frequência (Hz), assumindo afinação A4 = 440 Hz por padrão."""
    return a4_freq * (2.0 ** ((note - 69) / 12.0))


def db_to_linear(db: float) -> float:
    return 10.0 ** (db / 20.0)


def linear_to_db(linear: float) -> float:
    if linear <= 0.0:
        return -120.0
    return 20.0 * math.log10(linear)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def format_sample_time(frame: int, samplerate: int) -> str:
    """Formata uma posição em frames como MM:SS.mmm."""
    if samplerate <= 0:
        return "00:00.000"
    total_seconds = frame / samplerate
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:06.3f}"


def read_wav_float(filepath: str) -> tuple[np.ndarray, int, int]:
    """Lê um arquivo WAV (8/16/24/32-bit PCM ou 32-bit float) manualmente,
    sem depender de bibliotecas externas (soundfile/scipy), retornando:

        (dados float32 em [-1, 1] com shape (frames,) ou (frames, canais),
         samplerate,
         canais)

    O parser lê os chunks RIFF diretamente para identificar corretamente o
    `fmt_tag` (PCM vs. IEEE float), o que o módulo `wave` da stdlib não expõe.
    """
    with open(filepath, 'rb') as f:
        riff = f.read(4)
        if riff != b'RIFF':
            raise ValueError("Arquivo não é um WAV válido (RIFF ausente)")
        f.read(4)  # tamanho total do arquivo, ignorado
        wave_id = f.read(4)
        if wave_id != b'WAVE':
            raise ValueError("Arquivo não é um WAV válido (WAVE ausente)")

        fmt_tag = 1
        channels = 1
        samplerate = 44100
        bits_per_sample = 16
        data = b""

        while True:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break
            chunk_id, chunk_size = struct.unpack('<4sI', chunk_header)

            if chunk_id == b'fmt ':
                fmt_data = f.read(chunk_size)
                fmt_tag, channels, samplerate, _, _, bits_per_sample = struct.unpack(
                    '<HHIIHH', fmt_data[:16]
                )
            elif chunk_id == b'data':
                data = f.read(chunk_size)
            else:
                f.seek(chunk_size, os.SEEK_CUR)

            if chunk_size % 2 == 1:
                f.seek(1, os.SEEK_CUR)

    if not data:
        raise ValueError("Nenhum chunk 'data' encontrado no WAV")

    if fmt_tag == 3 and bits_per_sample == 32:
        samples = np.frombuffer(data, dtype='<f4').astype(np.float32)
    elif bits_per_sample == 8:
        samples = (np.frombuffer(data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif bits_per_sample == 16:
        samples = np.frombuffer(data, dtype='<i2').astype(np.float32) / 32768.0
    elif bits_per_sample == 24:
        count = len(data) // 3
        ints = np.zeros(count, dtype=np.int32)
        for i in range(count):
            chunk = data[i * 3:i * 3 + 3]
            sign_ext = b'\xff' if chunk[2] & 0x80 else b'\x00'
            ints[i] = struct.unpack('<i', chunk + sign_ext)[0]
        samples = ints.astype(np.float32) / 8388608.0
    elif bits_per_sample == 32:
        samples = np.frombuffer(data, dtype='<i4').astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Formato WAV não suportado: {bits_per_sample}-bit, fmt_tag={fmt_tag}")

    if channels > 1:
        samples = samples.reshape(-1, channels)

    return samples, samplerate, channels


classes = []


def register():
    pass


def unregister():
    pass