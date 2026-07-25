# modules/sampler/timestretch.py
"""
Time-stretch simples (altera duração preservando o pitch aproximadamente)
via overlap-add (OLA) clássico.

Não é um phase vocoder completo, mas funciona razoavelmente bem para
estiramentos moderados (aprox. 0.5x - 2x) sem dependências externas.
"""
from __future__ import annotations

import numpy as np


def _hann_window(size: int) -> np.ndarray:
    return np.hanning(size).astype(np.float32)


def time_stretch(data: np.ndarray, ratio: float, frame_size: int = 2048, hop_size: int = 512) -> np.ndarray:
    """Estica/comprime `data` (mono, 1D) no tempo por `ratio`.

    `ratio` > 1 = resultado mais longo; `ratio` < 1 = resultado mais curto.
    O pitch é mantido aproximadamente constante via overlap-add com janela
    de Hann na análise e um hop de síntese escalado por `ratio`.
    """
    if ratio <= 0:
        raise ValueError("ratio deve ser positivo")
    if ratio == 1.0:
        return data.copy()

    window = _hann_window(frame_size)
    synthesis_hop = max(1, int(round(hop_size * ratio)))

    n_frames = max(1, (len(data) - frame_size) // hop_size + 1)
    out_length = synthesis_hop * n_frames + frame_size
    output = np.zeros(out_length, dtype=np.float32)
    norm = np.zeros(out_length, dtype=np.float32)

    for i in range(n_frames):
        analysis_pos = i * hop_size
        frame = data[analysis_pos:analysis_pos + frame_size]
        if len(frame) < frame_size:
            frame = np.pad(frame, (0, frame_size - len(frame)))

        windowed = frame * window
        synth_pos = i * synthesis_hop
        output[synth_pos:synth_pos + frame_size] += windowed
        norm[synth_pos:synth_pos + frame_size] += window

    norm[norm < 1e-6] = 1.0
    return (output / norm).astype(np.float32)


def time_stretch_multichannel(data: np.ndarray, ratio: float,
                               frame_size: int = 2048, hop_size: int = 512) -> np.ndarray:
    """Aplica `time_stretch` a cada canal de um array (frames, canais) ou mono (frames,)."""
    if data.ndim == 1:
        return time_stretch(data, ratio, frame_size, hop_size)

    channels = [time_stretch(data[:, c], ratio, frame_size, hop_size) for c in range(data.shape[1])]
    min_len = min(len(c) for c in channels)
    return np.stack([c[:min_len] for c in channels], axis=1)


classes = []


def register():
    pass


def unregister():
    pass