"""
DAW Engine - Resampler
"""

from __future__ import annotations

import numpy as np

from scipy.signal import resample


class AudioResampler:

    @staticmethod
    def resample(

        audio: np.ndarray,

        input_rate: int,

        output_rate: int,

    ) -> np.ndarray:

        if input_rate == output_rate:

            return audio

        samples = int(

            len(audio)

            *

            output_rate

            /

            input_rate

        )

        return resample(

            audio,

            samples,

            axis=0,

        )