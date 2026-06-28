"""
DAW Engine - Backend Manager

Responsável por selecionar e gerenciar o backend de áudio.

A engine conversa apenas com este módulo.
Nunca diretamente com SoundDevice ou outro backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


# ==========================================================
# BACKENDS DISPONÍVEIS
# ==========================================================

class AudioBackend(Enum):

    SOUNDDEVICE = "sounddevice"

    DUMMY = "dummy"

    # futuros

    RTAUDIO = "rtaudio"

    JUCE = "juce"

    PIPEWIRE = "pipewire"


# ==========================================================
# BACKEND BASE
# ==========================================================

class BackendBase(ABC):

    @abstractmethod
    def initialize(self):
        ...

    @abstractmethod
    def terminate(self):
        ...

    @abstractmethod
    def list_devices(self):
        ...

    @abstractmethod
    def default_output(self):
        ...


# ==========================================================
# SOUNDDEVICE
# ==========================================================

class SoundDeviceBackend(BackendBase):

    def __init__(self):

        import sounddevice as sd

        self.sd = sd

    def initialize(self):
        return True

    def terminate(self):
        pass

    def list_devices(self):
        return self.sd.query_devices()

    def default_output(self):
        return self.sd.default.device[1]


# ==========================================================
# DUMMY
# ==========================================================

class DummyBackend(BackendBase):

    def initialize(self):
        return True

    def terminate(self):
        pass

    def list_devices(self):
        return []

    def default_output(self):
        return None


# ==========================================================
# FACTORY
# ==========================================================

def create_backend(kind: AudioBackend):

    if kind == AudioBackend.SOUNDDEVICE:
        return SoundDeviceBackend()

    if kind == AudioBackend.DUMMY:
        return DummyBackend()

    raise RuntimeError(f"Backend não suportado: {kind}")