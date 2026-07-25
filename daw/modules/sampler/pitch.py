# modules/sampler/pitch.py
"""
Conversões de afinação e reamostragem para transposição de pitch.
"""
from __future__ import annotations

import numpy as np


def semitone_ratio(semitones: float) -> float:
    return 2.0 ** (semitones / 12.0)


def cents_ratio(cents: float) -> float:
    return 2.0 ** (cents / 1200.0)


def note_to_ratio(played_note: int, root_note: int,
                   tune_semitones: float = 0.0, tune_cents: float = 0.0) -> float:
    """Calcula a razão de velocidade de reprodução para tocar `played_note`
    a partir de um sample cuja nota raiz é `root_note`, incluindo afinação
    fina em semitons e cents."""
    semitone_diff = (played_note - root_note) + tune_semitones
    return semitone_ratio(semitone_diff) * cents_ratio(tune_cents)


def resample_linear(data: np.ndarray, ratio: float, out_length: int | None = None) -> np.ndarray:
    """Reamostra `data` (mono ou multi-canal, shape (frames,) ou (frames, canais))
    por interpolação linear.

    `ratio` > 1 toca mais rápido/agudo; `ratio` < 1 toca mais devagar/grave.
    Esta é uma reamostragem estática simples (altera pitch e duração juntos),
    adequada para pré-visualização ou bounce; a reprodução ao vivo usa a
    variante incremental em `player.Voice`.
    """
    n_in = data.shape[0]
    if out_length is None:
        out_length = max(int(n_in / ratio), 1)

    src_positions = np.arange(out_length, dtype=np.float64) * ratio
    src_positions = np.clip(src_positions, 0, n_in - 1)

    idx0 = np.floor(src_positions).astype(np.int64)
    idx1 = np.clip(idx0 + 1, 0, n_in - 1)
    frac = (src_positions - idx0).astype(np.float32)

    if data.ndim == 1:
        return data[idx0] * (1.0 - frac) + data[idx1] * frac

    frac = frac[:, None]
    return data[idx0] * (1.0 - frac) + data[idx1] * frac


classes = []


def register():
    pass


def unregister():
    pass