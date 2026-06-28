"""
Audio Stream

Responsável apenas pela criação
e controle do OutputStream.
"""

from __future__ import annotations

import sounddevice as sd

from .config import ENGINE_CONFIG


class OutputStream:

    def __init__(self, callback):

        self.callback = callback

        self.stream = None

    # ------------------------------------------

    def start(self):

        if self.stream is not None:

            return

        self.stream = sd.OutputStream(

            samplerate=ENGINE_CONFIG.sample_rate,

            channels=ENGINE_CONFIG.channels,

            blocksize=ENGINE_CONFIG.buffer_size,

            dtype=ENGINE_CONFIG.sample_format.value,

            callback=self.callback,

            latency=ENGINE_CONFIG.latency,
        )

        self.stream.start()

    # ------------------------------------------

    def stop(self):

        if self.stream is None:
            return

        self.stream.stop()

        self.stream.close()

        self.stream = None

    # ------------------------------------------

    @property
    def active(self):

        return (
            self.stream is not None
            and self.stream.active
        )