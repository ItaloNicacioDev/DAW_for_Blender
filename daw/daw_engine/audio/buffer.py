"""
Audio Buffer
"""

from __future__ import annotations

import numpy as np


class AudioBuffer:

    def __init__(

        self,

        frames,

        channels=2,

        dtype=np.float32,

    ):

        self.data = np.zeros(

            (frames, channels),

            dtype=dtype

        )

    # ----------------------------

    def clear(self):

        self.data.fill(0)

    # ----------------------------

    @property
    def left(self):

        return self.data[:,0]

    @property
    def right(self):

        return self.data[:,1]

    @property
    def frames(self):

        return self.data.shape[0]

    @property
    def channels(self):

        return self.data.shape[1]