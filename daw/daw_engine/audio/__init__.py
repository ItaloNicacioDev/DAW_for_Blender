# audio/__init__.py
"""
Pacote de áudio da DAW — camada de hardware e stream.

Responsabilidades deste pacote:
    config.py   — AudioConfig (sample rate, buffer size, formato, BPM, PPQ)
    backend.py  — abstração de backend (SoundDevice, Dummy, futuro RtAudio...)
    state.py    — ENGINE_STATE: singleton com status em tempo real (xruns, CPU...)
    callback.py — AudioCallback: __call__ chamado pela thread de áudio do SO
    stream.py   — OutputStream: cria e controla o sd.OutputStream

Fluxo de dados:
    Engine.start()
        └─> OutputStream.start()
                └─> sd.OutputStream(callback=AudioCallback())
                        └─> AudioCallback.__call__(outdata, frames, ...)
                                └─> Mixer.process(frames)   → np.ndarray
                                └─> outdata[:] = audio      → hardware

Regras que NUNCA devem ser quebradas neste pacote:
    - NUNCA importar bpy em callback.py ou stream.py
    - NUNCA fazer I/O de disco na thread de áudio
    - NUNCA criar objetos Python na thread de áudio (aloca memória → GIL)
    - NUNCA fazer print() na thread de áudio
"""
from __future__ import annotations

from .config import (
    AudioConfig,
    AudioBackend,
    SampleFormat,
    ENGINE_CONFIG,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_CHANNELS,
    DEFAULT_BPM,
    DEFAULT_PPQ,
)
from .backend import (
    BackendBase,
    SoundDeviceBackend,
    DummyBackend,
    create_backend,
)
from .state import AudioState, ENGINE_STATE
from .callback import AudioCallback
from .stream import OutputStream

__all__ = [
    # Config
    "AudioConfig",
    "AudioBackend",
    "SampleFormat",
    "ENGINE_CONFIG",
    "DEFAULT_SAMPLE_RATE",
    "DEFAULT_BUFFER_SIZE",
    "DEFAULT_CHANNELS",
    "DEFAULT_BPM",
    "DEFAULT_PPQ",
    # Backend
    "BackendBase",
    "SoundDeviceBackend",
    "DummyBackend",
    "create_backend",
    # Estado
    "AudioState",
    "ENGINE_STATE",
    # Stream
    "AudioCallback",
    "OutputStream",
]