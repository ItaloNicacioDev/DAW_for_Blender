"""
DAW Engine - Audio Meter

Calcula Peak, RMS e Clipping.

A interface apenas lê estes valores.
"""

from __future__ import annotations

import numpy as np


class AudioMeter:

    def __init__(self):

        self._peak_left = 0.0
        self._peak_right = 0.0

        self._rms_left = 0.0
        self._rms_right = 0.0

        self._clipping = False

    # ---------------------------------------------------------

    def process(self, buffer: np.ndarray):

        """
        buffer shape:

        (frames, channels)
        """

        if buffer.size == 0:
            return

        left = buffer[:, 0]
        right = buffer[:, 1]

        self._peak_left = float(np.max(np.abs(left)))
        self._peak_right = float(np.max(np.abs(right)))

        self._rms_left = float(np.sqrt(np.mean(left * left)))
        self._rms_right = float(np.sqrt(np.mean(right * right)))

        self._clipping = (
            self._peak_left >= 1.0
            or
            self._peak_right >= 1.0
        )

    # ---------------------------------------------------------

    @property
    def peak(self):
        return (
            self._peak_left,
            self._peak_right,
        )

    @property
    def rms(self):
        return (
            self._rms_left,
            self._rms_right,
        )

    @property
    def clipping(self):
        return self._clipping

    # ---------------------------------------------------------

    def reset(self):

        self._peak_left = 0.0
        self._peak_right = 0.0

        self._rms_left = 0.0
        self._rms_right = 0.0

        self._clipping = False