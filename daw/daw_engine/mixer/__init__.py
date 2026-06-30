# mixer/__init__.py
"""
Pacote de mixagem de áudio da DAW.

O Mixer é o ponto central do fluxo de áudio:

    Scheduler/Engine
        └─> Mixer.handle_midi_event()
                └─> Channel.note_on/off/cc
                        └─> Synth.process()  (dsp/oscillator + dsp/adsr)

    AudioCallback
        └─> Mixer.process(frames)
                └─> soma de todos os Channel.process()
                        └─> MasterBus (volume + soft limiter)
                                └─> np.ndarray (frames, 2) float32 → stream
"""
from __future__ import annotations

from .mixer import Mixer, Channel, MasterBus

__all__ = [
    "Mixer",
    "Channel",
    "MasterBus",
]