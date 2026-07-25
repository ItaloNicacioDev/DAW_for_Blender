# modules/sampler/looping.py
"""
Utilitários de loop de sample: modos de reprodução, crossfade e zero-crossing.
"""
from __future__ import annotations

import numpy as np

from .envelopes import apply_crossfade

LOOP_MODE_OFF = 'OFF'
LOOP_MODE_FORWARD = 'FORWARD'
LOOP_MODE_PING_PONG = 'PING_PONG'


def find_nearest_zero_crossing(data: np.ndarray, position: int, search_radius: int = 512) -> int:
    """Procura a passagem por zero mais próxima de `position` (usa o primeiro
    canal em samples multi-canal). Usado para evitar cliques ao posicionar
    pontos de loop manualmente."""
    mono = data if data.ndim == 1 else data[:, 0]
    n = len(mono)
    if n == 0:
        return 0
    position = min(max(position, 0), n - 1)

    lo = max(position - search_radius, 1)
    hi = min(position + search_radius, n - 1)

    best_idx = position
    best_dist = search_radius + 1

    for i in range(lo, hi):
        if (mono[i - 1] <= 0.0 <= mono[i]) or (mono[i - 1] >= 0.0 >= mono[i]):
            dist = abs(i - position)
            if dist < best_dist:
                best_dist = dist
                best_idx = i

    return best_idx


def build_seamless_loop(data: np.ndarray, loop_start: int, loop_end: int,
                         crossfade_samples: int = 256) -> np.ndarray:
    """Retorna uma cópia do array com um crossfade aplicado na junção do loop
    (do final de `loop_end` de volta para `loop_start`), reduzindo cliques."""
    n = len(data)
    loop_start = min(max(loop_start, 0), n - 1)
    loop_end = min(max(loop_end, loop_start + 1), n)
    crossfade_samples = min(crossfade_samples, loop_end - loop_start, loop_start)

    if crossfade_samples <= 0:
        return data.copy()

    result = data.copy()
    tail = data[loop_end - crossfade_samples:loop_end]
    head = data[loop_start:loop_start + crossfade_samples]
    result[loop_end - crossfade_samples:loop_end] = apply_crossfade(tail, head, curve='EQUAL_POWER')
    return result


class LoopCursor:
    """Mantém a posição de reprodução de um sample considerando o modo de loop."""

    def __init__(self, loop_mode: str = LOOP_MODE_OFF, loop_start: int = 0, loop_end: int = 0):
        self.loop_mode = loop_mode
        self.loop_start = loop_start
        self.loop_end = max(loop_end, loop_start + 1)
        self.direction = 1

    def advance(self, position: float, step: float, total_frames: int) -> tuple[float, bool]:
        """Avança a posição de reprodução em `step` frames (fracionário devido
        ao pitch). Retorna (nova_posição, sample_terminou)."""
        if self.loop_mode == LOOP_MODE_OFF:
            new_pos = position + step
            return new_pos, new_pos >= total_frames

        if self.loop_mode == LOOP_MODE_FORWARD:
            new_pos = position + step
            if new_pos >= self.loop_end:
                overflow = new_pos - self.loop_end
                new_pos = self.loop_start + overflow
            return new_pos, False

        if self.loop_mode == LOOP_MODE_PING_PONG:
            new_pos = position + (step * self.direction)
            if new_pos >= self.loop_end:
                overflow = new_pos - self.loop_end
                new_pos = self.loop_end - overflow
                self.direction = -1
            elif new_pos <= self.loop_start:
                overflow = self.loop_start - new_pos
                new_pos = self.loop_start + overflow
                self.direction = 1
            return new_pos, False

        return position + step, True


classes = []


def register():
    pass


def unregister():
    pass