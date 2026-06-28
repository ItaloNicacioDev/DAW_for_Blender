"""
DAW Engine - Recorder
"""

from __future__ import annotations

import soundfile as sf


class AudioRecorder:

    def __init__(self):

        self.file = None

        self.recording = False

    # ---------------------------------------------------------

    def start(

        self,

        filename,

        sample_rate,

        channels,

    ):

        self.file = sf.SoundFile(

            filename,

            mode="w",

            samplerate=sample_rate,

            channels=channels,

            subtype="PCM_24",

        )

        self.recording = True

    # ---------------------------------------------------------

    def process(self, buffer):

        if not self.recording:
            return

        self.file.write(buffer)

    # ---------------------------------------------------------

    def stop(self):

        if self.file:

            self.file.close()

            self.file = None

        self.recording = False