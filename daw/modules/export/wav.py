# modules/export/wav.py
"""
Exportador WAV.

Responsabilidade:
    Renderizar as notas do Piano Roll (context.scene.piano_roll.notes) em
    áudio PCM e gravar um arquivo .wav real, usando apenas a biblioteca
    padrão do Python (`wave` + `array` + `math`) — funciona mesmo sem o
    motor de áudio C++ (daw_engine.dll) conectado.

    É um sintetizador simples (onda senoidal com envelope ADSR básico),
    suficiente para audição/preview e como base para os demais formatos
    (mp3.py, ogg.py, flac.py transcodificam a partir do WAV gerado aqui).
"""
from __future__ import annotations

import math
import wave
from array import array
from pathlib import Path
from typing import Iterable, List, Sequence, Union

WAVE_SHAPES = ("SINE", "SQUARE", "SAW", "TRIANGLE")


class ExportNote:
    """Representação simples de uma nota, independente de bpy (pitch MIDI, tempo em beats)."""

    __slots__ = ("pitch", "start", "length", "velocity")

    def __init__(self, pitch: int, start: float, length: float, velocity: int = 100):
        self.pitch = pitch
        self.start = start
        self.length = length
        self.velocity = velocity


def pitch_to_freq(pitch: int) -> float:
    """Converte um número de nota MIDI (0-127) para frequência em Hz (A4 = 69 = 440Hz)."""
    return 440.0 * (2.0 ** ((pitch - 69) / 12.0))


def _oscillator(shape: str, phase: float) -> float:
    """Retorna a amplitude (-1..1) de uma forma de onda na fase `phase` (0..1)."""
    if shape == "SQUARE":
        return 1.0 if (phase % 1.0) < 0.5 else -1.0
    if shape == "SAW":
        return 2.0 * (phase % 1.0) - 1.0
    if shape == "TRIANGLE":
        p = phase % 1.0
        return 4.0 * abs(p - 0.5) - 1.0
    # SINE (padrão)
    return math.sin(2.0 * math.pi * phase)


def _envelope(t: float, duration: float, attack: float = 0.01, release: float = 0.05) -> float:
    """Envelope linear simples de attack/release para evitar cliques nas bordas da nota."""
    if duration <= 0:
        return 0.0
    if t < attack:
        return t / attack
    if t > duration - release:
        return max(0.0, (duration - t) / release)
    return 1.0


def render_notes(
    notes: Iterable[ExportNote],
    bpm: float,
    sample_rate: int = 44100,
    wave_shape: str = "SINE",
    tail_seconds: float = 1.0,
    normalize: bool = True,
) -> array:
    """
    Renderiza uma lista de ExportNote em um buffer PCM mono int16 (`array('h', ...)`).

    `notes[i].start` / `.length` estão em beats (semínimas); são convertidos
    para segundos usando `bpm`.
    """
    notes = list(notes)
    seconds_per_beat = 60.0 / max(1.0, bpm)

    if not notes:
        total_duration = tail_seconds
    else:
        total_duration = max(n.start + n.length for n in notes) * seconds_per_beat + tail_seconds

    num_samples = max(1, int(total_duration * sample_rate))
    mix = [0.0] * num_samples

    for note in notes:
        start_sec = note.start * seconds_per_beat
        dur_sec = max(0.01, note.length * seconds_per_beat)
        freq = pitch_to_freq(note.pitch)
        amp = max(0.0, min(1.0, note.velocity / 127.0)) * 0.3  # 0.3 = headroom p/ evitar clipping ao somar vozes

        start_sample = int(start_sec * sample_rate)
        n_samples = int(dur_sec * sample_rate)

        for i in range(n_samples):
            idx = start_sample + i
            if idx >= num_samples:
                break
            t = i / sample_rate
            phase = t * freq
            sample = _oscillator(wave_shape, phase) * amp * _envelope(t, dur_sec)
            mix[idx] += sample

    if normalize:
        peak = max((abs(s) for s in mix), default=0.0)
        if peak > 1e-9:
            scale = min(1.0, 0.98 / peak)
            mix = [s * scale for s in mix]

    pcm = array('h', (max(-32768, min(32767, int(s * 32767))) for s in mix))
    return pcm


def write_wav_file(
    pcm: array,
    filepath: Union[str, Path],
    sample_rate: int = 44100,
    channels: int = 1,
    bit_depth: int = 16,
) -> Path:
    """
    Grava um buffer PCM int16 (`array('h', ...)`) como arquivo .wav real em disco.
    Atualmente só suporta bit_depth=16 (o mais compatível); outros valores
    caem de volta para 16 bits.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    sample_width = 2  # bytes — 16 bits

    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())

    return filepath


def export_notes_to_wav(
    notes: Iterable[ExportNote],
    bpm: float,
    filepath: Union[str, Path],
    sample_rate: int = 44100,
    wave_shape: str = "SINE",
    normalize: bool = True,
) -> Path:
    """Atalho: renderiza as notas e grava direto em `filepath`. Retorna o Path final."""
    pcm = render_notes(notes, bpm, sample_rate=sample_rate, wave_shape=wave_shape, normalize=normalize)
    return write_wav_file(pcm, filepath, sample_rate=sample_rate, channels=1)