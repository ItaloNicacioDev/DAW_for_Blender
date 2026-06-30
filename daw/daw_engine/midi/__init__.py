# midi/__init__.py
"""
Pacote MIDI da DAW.

Exporta os tipos de evento e utilitários usados por:
- Piano Roll (UI): lê/escreve NoteOnEvent/NoteOffEvent na MidiSequence
- Scheduler (core): despacha eventos pelo tempo durante a reprodução
- Synth (instruments): recebe NoteOnEvent e chama synth.note_on()
- Mixer (mixer): encaminha CCs e pitch bend para os canais corretos
- Futuro: midi_input.py (captura de teclado físico via rtmidi/mido)
"""
from __future__ import annotations

from .events import (
    # Enums e constantes
    MidiStatus,
    CC,
    # Tipos de evento
    MidiEvent,
    NoteOnEvent,
    NoteOffEvent,
    ControlChangeEvent,
    PitchBendEvent,
    ProgramChangeEvent,
    AftertouchEvent,
    # Sequência
    MidiSequence,
    # Helpers
    event_from_dict,
    event_from_raw,
    # Compat
    NoteEvent,
)

__all__ = [
    "MidiStatus",
    "CC",
    "MidiEvent",
    "NoteOnEvent",
    "NoteOffEvent",
    "ControlChangeEvent",
    "PitchBendEvent",
    "ProgramChangeEvent",
    "AftertouchEvent",
    "MidiSequence",
    "event_from_dict",
    "event_from_raw",
    "NoteEvent",
]