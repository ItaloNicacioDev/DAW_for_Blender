# modules/sampler/slicing.py
"""
Fatiamento (slicing) de samples: divisão automática por número de fatias
ou detecção simples de transientes por variação de energia.
"""
from __future__ import annotations

import numpy as np


def slice_equal(num_frames: int, num_slices: int) -> list[tuple[int, int]]:
    """Divide um sample de `num_frames` em `num_slices` fatias de tamanho igual."""
    num_slices = max(1, num_slices)
    size = max(num_frames // num_slices, 1)

    slices = []
    for i in range(num_slices):
        start = i * size
        end = num_frames if i == num_slices - 1 else start + size
        slices.append((start, end))
    return slices


def detect_transients(data: np.ndarray, samplerate: int, sensitivity: float = 0.35,
                       min_gap_seconds: float = 0.08) -> list[int]:
    """Detecta pontos de transiente (ataques) por variação de energia RMS
    em janelas curtas (~10ms).

    `sensitivity` (0-1): quanto maior, mais sensível (mais transientes
    detectados). Retorna uma lista ordenada de posições (em frames) onde
    novas fatias devem começar; sempre inclui a posição 0.
    """
    mono = data if data.ndim == 1 else data.mean(axis=1)

    window = max(int(samplerate * 0.01), 64)
    hop = max(window // 2, 1)
    min_gap = int(samplerate * min_gap_seconds)

    n = len(mono)
    energies = []
    positions = []
    pos = 0
    while pos + window <= n:
        frame = mono[pos:pos + window]
        energies.append(float(np.sqrt(np.mean(frame ** 2))))
        positions.append(pos)
        pos += hop

    if len(energies) < 2:
        return [0]

    energies_arr = np.array(energies, dtype=np.float32)
    diffs = np.diff(energies_arr, prepend=energies_arr[0])
    max_diff = float(np.max(diffs))
    threshold = max_diff * (1.0 - sensitivity) if max_diff > 0 else 0.0

    onsets = [0]
    last_onset = -min_gap
    for i, d in enumerate(diffs):
        if d > threshold and positions[i] - last_onset >= min_gap:
            onsets.append(positions[i])
            last_onset = positions[i]

    return sorted(set(onsets))


def slice_by_transients(data: np.ndarray, samplerate: int, sensitivity: float = 0.35) -> list[tuple[int, int]]:
    """Gera fatias (start, end) a partir de pontos de transiente detectados."""
    num_frames = len(data)
    onsets = detect_transients(data, samplerate, sensitivity=sensitivity)

    slices = []
    for i, start in enumerate(onsets):
        end = onsets[i + 1] if i + 1 < len(onsets) else num_frames
        slices.append((start, end))
    return slices


classes = []


def register():
    pass


def unregister():
    pass