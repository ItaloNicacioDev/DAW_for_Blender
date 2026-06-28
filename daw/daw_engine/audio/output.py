"""
Master Output
"""

from __future__ import annotations

from .callback import AudioCallback

from .stream import OutputStream


class AudioOutput:

    def __init__(self):

        self.callback = AudioCallback()

        self.stream = OutputStream(

            self.callback

        )

    # -------------------------------------

    def set_generator(

        self,

        generator

    ):

        self.callback.set_generator(

            generator

        )

    # -------------------------------------

    def start(self):

        self.stream.start()

    # -------------------------------------

    def stop(self):

        self.stream.stop()

    # -------------------------------------

    @property

    def active(self):

        return self.stream.active