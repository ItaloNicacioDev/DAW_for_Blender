"""
Gerenciamento de dispositivos de áudio.
"""

from __future__ import annotations

from .backend import create_backend
from .config import ENGINE_CONFIG


class AudioDeviceManager:

    def __init__(self):

        self.backend = create_backend(
            ENGINE_CONFIG.backend
        )

    # ------------------------------------------

    def devices(self):

        return self.backend.list_devices()

    # ------------------------------------------

    def default_output(self):

        return self.backend.default_output()

    # ------------------------------------------

    def outputs(self):

        devices = self.devices()

        result = []

        for idx, dev in enumerate(devices):

            if dev["max_output_channels"] > 0:

                result.append((idx, dev))

        return result

    # ------------------------------------------

    def inputs(self):

        devices = self.devices()

        result = []

        for idx, dev in enumerate(devices):

            if dev["max_input_channels"] > 0:

                result.append((idx, dev))

        return result