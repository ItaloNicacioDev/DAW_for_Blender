"""
DAW Engine - Audio Configuration

Este módulo contém apenas configurações globais da engine.
Nenhum código de reprodução de áudio deve ficar aqui.

Responsabilidade:
- Configurações padrão
- Validação
- Estrutura de configuração
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# ENUMS
# ============================================================

class AudioBackend(Enum):
    """
    Backend de áudio utilizado pela engine.

    Atualmente utilizamos SoundDevice (PortAudio),
    mas no futuro poderá ser expandido para outros.
    """
    SOUNDDEVICE = "sounddevice"


class SampleFormat(Enum):
    """
    Formato interno de áudio.

    FLOAT32 será utilizado em toda a engine.
    """

    FLOAT32 = "float32"
    INT16 = "int16"


# ============================================================
# DEFAULTS
# ============================================================

DEFAULT_SAMPLE_RATE = 48000

DEFAULT_BUFFER_SIZE = 512

DEFAULT_CHANNELS = 2

DEFAULT_MASTER_VOLUME = 1.0

DEFAULT_BPM = 120

DEFAULT_PPQ = 960


# ============================================================
# CONFIG
# ============================================================

@dataclass
class AudioConfig:
    """
    Configuração global da engine.

    Esta classe é utilizada pelo AudioDevice,
    Mixer, Transport e demais módulos.
    """

    sample_rate: int = DEFAULT_SAMPLE_RATE

    buffer_size: int = DEFAULT_BUFFER_SIZE

    channels: int = DEFAULT_CHANNELS

    sample_format: SampleFormat = SampleFormat.FLOAT32

    backend: AudioBackend = AudioBackend.SOUNDDEVICE

    master_volume: float = DEFAULT_MASTER_VOLUME

    bpm: int = DEFAULT_BPM

    ppq: int = DEFAULT_PPQ

    output_device: int | None = None

    input_device: int | None = None

    latency: str = "low"

    extra: dict = field(default_factory=dict)

    # --------------------------------------------------------

    def validate(self) -> None:
        """
        Valida todas as configurações.

        Levanta ValueError caso alguma configuração seja inválida.
        """

        if self.sample_rate <= 0:
            raise ValueError("Sample Rate inválido.")

        if self.buffer_size <= 0:
            raise ValueError("Buffer Size inválido.")

        if self.channels not in (1, 2):
            raise ValueError("A engine suporta apenas Mono ou Stereo.")

        if not 0.0 <= self.master_volume <= 1.0:
            raise ValueError("Master Volume deve estar entre 0.0 e 1.0.")

        if self.bpm <= 0:
            raise ValueError("BPM inválido.")

        if self.ppq <= 0:
            raise ValueError("PPQ inválido.")

# ============================================================
#  RESETAR CONFIG GLOBAL
# ============================================================
    def reset(self) -> None:
     """Restaura as configurações padrão."""
     self.sample_rate = DEFAULT_SAMPLE_RATE
     self.buffer_size = DEFAULT_BUFFER_SIZE
     self.channels = DEFAULT_CHANNELS
     self.sample_format = SampleFormat.FLOAT32
     self.backend = AudioBackend.SOUNDDEVICE
     self.master_volume = DEFAULT_MASTER_VOLUME
     self.bpm = DEFAULT_BPM
     self.ppq = DEFAULT_PPQ
     self.output_device = None
     self.input_device = None
     self.latency = "low"
     self.extra.clear()

# ============================================================
# CONFIG GLOBAL
# ============================================================

ENGINE_CONFIG = AudioConfig()