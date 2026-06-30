# instruments/__init__.py
"""
Pacote de instrumentos virtuais da DAW.

Atualmente:
    Synth — sintetizador subtrativo polifônico (oscilador + ADSR por voz)

Futuros instrumentos seguirão a mesma interface:
    .note_on(note, velocity)
    .note_off(note)
    .all_notes_off()
    .process(frames) -> np.ndarray shape (frames, 2) float32

Essa interface comum permite que o Mixer trate qualquer instrumento
da mesma forma, sem saber qual é.
"""
from __future__ import annotations

from .synth import Synth, SynthPreset, Voice

__all__ = [
    "Synth",
    "SynthPreset",
    "Voice",
]