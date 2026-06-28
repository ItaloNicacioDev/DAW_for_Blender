"""
DAW Engine - Audio Formats

Este módulo contém todas as definições de formatos
de áudio utilizadas pela engine.

Nada aqui deve depender de SoundDevice ou Blender.
"""

from __future__ import annotations

from enum import Enum


# ==========================================================
# SAMPLE FORMAT
# ==========================================================

class SampleFormat(Enum):
    """
    Formato interno das amostras.

    FLOAT32 será utilizado em praticamente toda a engine.
    """

    FLOAT32 = "float32"

    FLOAT64 = "float64"

    INT16 = "int16"

    INT24 = "int24"

    INT32 = "int32"


# ==========================================================
# CHANNEL LAYOUT
# ==========================================================

class ChannelLayout(Enum):

    MONO = 1

    STEREO = 2


# ==========================================================
# SAMPLE RATE
# ==========================================================

class SampleRate(Enum):

    SR_22050 = 22050

    SR_32000 = 32000

    SR_44100 = 44100

    SR_48000 = 48000

    SR_88200 = 88200

    SR_96000 = 96000

    SR_192000 = 192000


# ==========================================================
# LATENCY
# ==========================================================

class LatencyMode(Enum):

    LOW = "low"

    BALANCED = "balanced"

    HIGH = "high"


# ==========================================================
# STREAM MODE
# ==========================================================

class StreamMode(Enum):

    OUTPUT = "output"

    INPUT = "input"

    DUPLEX = "duplex"


# ==========================================================
# BUFFER SIZE
# ==========================================================

class BufferSize(Enum):

    VERY_LOW = 64

    LOW = 128

    NORMAL = 256

    BALANCED = 512

    HIGH = 1024

    VERY_HIGH = 2048