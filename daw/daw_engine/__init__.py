# daw_engine/__init__.py
"""
Pacote raiz da engine de áudio da DAW.

Correção vs versão anterior:
    - `from .core.engine import DAWEngine` — DAWEngine não existe.
      A classe se chama Engine e o singleton global é ENGINE (ver engine.py).
      Importar um nome errado faz o addon inteiro falhar ao carregar no Blender
      com um ImportError silencioso.

Estrutura do pacote:
    core/        — motor principal: clock, transport, scheduler, events,
                   session, project, timeline, history, commands, registry...
    audio/       — hardware: config, backend, state, callback, stream
    dsp/         — processamento de sinal: osciladores, envelope ADSR
    instruments/ — instrumentos virtuais: Synth (polifônico)
    midi/        — eventos MIDI: NoteOn/Off, CC, PitchBend, MidiSequence
    mixer/       — mixagem: canais, pan, mute/solo, master bus

Uso mínimo de fora do pacote (ex: operadores Blender):

    from daw.daw_engine import ENGINE

    ENGINE.start()
    ENGINE.play()
    ENGINE.mixer.note_on(60, 100)
    ENGINE.stop()
    ENGINE.shutdown()
"""
from __future__ import annotations

# --- Core (importado primeiro — outros pacotes dependem dele) ---
from .core.engine import Engine, ENGINE
from .core.clock import Clock
from .core.transport import Transport
from .core.scheduler import Scheduler
from .core.events import EventSystem
from .core.session import Session
from .core.project import Project
from .core.timeline import Timeline, Track, Clip
from .core.history import History
from .core.commands import Command
from .core.registry import Registry
from .core.state import State
from .core.settings import Settings
from .core.logger import LOGGER
from .core.constants import (
    EngineState,
    TrackType,
    ClipType,
)

# --- Audio ---
from .audio.config import AudioConfig, ENGINE_CONFIG
from .audio.state import AudioState, ENGINE_STATE
from .audio.backend import AudioBackend, create_backend
from .audio.callback import AudioCallback
from .audio.stream import OutputStream

# --- DSP ---
from .dsp.oscillator import (
    Oscillator,
    SineOsc,
    SawOsc,
    SquareOsc,
    TriangleOsc,
    create_oscillator,
    available_waveforms,
)
from .dsp.adsr import ADSR, ADSRStage

# --- Instruments ---
from .instruments.synth import Synth, SynthPreset

# --- MIDI ---
from .midi.events import (
    MidiEvent,
    NoteOnEvent,
    NoteOffEvent,
    ControlChangeEvent,
    PitchBendEvent,
    ProgramChangeEvent,
    MidiSequence,
    event_from_raw,
    event_from_dict,
    NoteEvent,         # compat
)

# --- Mixer ---
from .mixer.mixer import Mixer, Channel, MasterBus


__all__ = [
    # Engine — ponto de entrada principal
    "Engine", "ENGINE",

    # Core
    "Clock", "Transport", "Scheduler", "EventSystem",
    "Session", "Project", "Timeline", "Track", "Clip",
    "History", "Command", "Registry", "State", "Settings", "LOGGER",
    "EngineState", "TrackType", "ClipType",

    # Audio
    "AudioConfig", "ENGINE_CONFIG",
    "AudioState", "ENGINE_STATE",
    "AudioBackend", "create_backend",
    "AudioCallback", "OutputStream",

    # DSP
    "Oscillator", "SineOsc", "SawOsc", "SquareOsc", "TriangleOsc",
    "create_oscillator", "available_waveforms",
    "ADSR", "ADSRStage",

    # Instruments
    "Synth", "SynthPreset",

    # MIDI
    "MidiEvent", "NoteOnEvent", "NoteOffEvent",
    "ControlChangeEvent", "PitchBendEvent", "ProgramChangeEvent",
    "MidiSequence", "event_from_raw", "event_from_dict",
    "NoteEvent",

    # Mixer
    "Mixer", "Channel", "MasterBus",
]