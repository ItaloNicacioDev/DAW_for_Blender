# modules/recorder/input.py
"""
Gerenciamento de dispositivos de entrada de áudio.
"""
from __future__ import annotations

import numpy as np


class InputDeviceManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.stream = None
        self.device_name = "Default"
        self.sample_rate = 48000
        self.channels = 1
        self.blocksize = 1024
        self.dtype = 'float32'
        self.last_buffer = np.zeros(self.blocksize, dtype=self.dtype)
        self.peak_level = 0.0
        self.rms_level = 0.0
        self._callback_count = 0

    def _audio_callback(self, indata, frames, time_info, status):
        if indata is not None and len(indata) > 0:
            self.last_buffer = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
            self.peak_level = float(np.max(np.abs(self.last_buffer)))
            self.rms_level = float(np.sqrt(np.mean(self.last_buffer ** 2)))
            self._callback_count += 1

    def get_devices(self):
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            inputs = []
            for idx, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    inputs.append((str(idx), dev['name'], f"{dev['name']} [in:{dev['max_input_channels']}]"))
            return inputs if inputs else [('-1', "Nenhum", "Nenhum dispositivo de entrada")]
        except ImportError:
            return [('-1', "sounddevice não instalado", "Instale sounddevice para captura real")]

    def start(self, device_name: str = "Default", samplerate: int = 48000):
        try:
            import sounddevice as sd
            device_id = None
            if device_name != "Default":
                devices = sd.query_devices()
                for idx, dev in enumerate(devices):
                    if dev['name'] == device_name and dev['max_input_channels'] > 0:
                        device_id = idx
                        break

            self.stream = sd.InputStream(
                device=device_id,
                channels=self.channels,
                samplerate=samplerate,
                blocksize=self.blocksize,
                dtype=self.dtype,
                callback=self._audio_callback,
            )
            self.stream.start()
            return True
        except ImportError:
            return False
        except Exception as e:
            print(f"[DAW Recorder] Erro ao iniciar entrada: {e}")
            return False

    def stop(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                print(f"[DAW Recorder] Erro ao parar entrada: {e}")
            finally:
                self.stream = None

    def get_levels(self):
        return self.peak_level, self.rms_level

    def read_buffer(self):
        return self.last_buffer.copy()


def get_input_manager() -> InputDeviceManager:
    return InputDeviceManager()


classes = []


def register():
    pass


def unregister():
    mgr = get_input_manager()
    mgr.stop()