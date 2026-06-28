"""
DAW Engine - Global Constants

Este módulo contém apenas constantes globais da Engine.

Nenhuma lógica deve existir aqui.

Todas as outras partes da engine importam constantes deste arquivo.
"""

from __future__ import annotations

from enum import Enum

# ============================================================
# ENGINE
# ============================================================

ENGINE_NAME = "DAW Engine"

ENGINE_VERSION = "0.1.0"

ENGINE_AUTHOR = "Italo Nicacio"

ENGINE_API_VERSION = 1

# ============================================================
# AUDIO
# ============================================================

DEFAULT_SAMPLE_RATE = 48000

DEFAULT_BUFFER_SIZE = 512

DEFAULT_CHANNELS = 2

DEFAULT_BPM = 120

DEFAULT_PPQ = 960

MAX_CHANNELS = 2

MIN_BPM = 20

MAX_BPM = 999

# ============================================================
# PLAYLIST
# ============================================================

DEFAULT_TIME_SIGNATURE_NUMERATOR = 4

DEFAULT_TIME_SIGNATURE_DENOMINATOR = 4

DEFAULT_LOOP_ENABLED = False

# ============================================================
# PROJECT
# ============================================================

PROJECT_EXTENSION = ".blendaw"

PROJECT_VERSION = 1

DEFAULT_PROJECT_NAME = "Untitled"

# ============================================================
# TRANSPORT
# ============================================================

DEFAULT_PLAYHEAD = 0

# ============================================================
# MIXER
# ============================================================

DEFAULT_TRACKS = 16

MAX_TRACKS = 512

MASTER_TRACK_INDEX = 0

# ============================================================
# CHANNEL RACK
# ============================================================

DEFAULT_CHANNELS_COUNT = 8

MAX_CHANNELS_COUNT = 512

# ============================================================
# MIDI
# ============================================================

MIDI_NOTE_MIN = 0

MIDI_NOTE_MAX = 127

MIDI_VELOCITY_MIN = 0

MIDI_VELOCITY_MAX = 127

# ============================================================
# COLORS
# ============================================================

DEFAULT_TRACK_COLOR = (0.35, 0.35, 0.35)

DEFAULT_CLIP_COLOR = (0.18, 0.63, 0.93)

# ============================================================
# LIMITS
# ============================================================

MAX_POLYPHONY = 256

MAX_EFFECTS_PER_TRACK = 32

MAX_SENDS_PER_TRACK = 16

# ============================================================
# FILESYSTEM
# ============================================================

SUPPORTED_AUDIO_EXTENSIONS = {

    ".wav",

    ".flac",

    ".ogg",

    ".aiff",

    ".mp3",

}

SUPPORTED_PROJECT_EXTENSIONS = {

    PROJECT_EXTENSION,

}

# ============================================================
# ENUMS
# ============================================================

class EngineState(Enum):

    STOPPED = "stopped"

    PLAYING = "playing"

    PAUSED = "paused"

    RECORDING = "recording"


class TrackType(Enum):

    AUDIO = "audio"

    MIDI = "midi"

    BUS = "bus"

    MASTER = "master"


class ClipType(Enum):

    MIDI = "midi"

    AUDIO = "audio"

    AUTOMATION = "automation"


class AutomationInterpolation(Enum):

    STEP = "step"

    LINEAR = "linear"

    BEZIER = "bezier"


class LoopMode(Enum):

    OFF = "off"

    PLAYLIST = "playlist"

    PATTERN = "pattern"


class LogLevel(Enum):

    DEBUG = 10

    INFO = 20

    WARNING = 30

    ERROR = 40

    CRITICAL = 50


class CommandStatus(Enum):

    SUCCESS = "success"

    FAILED = "failed"

    CANCELLED = "cancelled"

    PENDING = "pending"