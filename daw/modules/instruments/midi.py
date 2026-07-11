# modules/instruments/midi.py
"""
Eventos MIDI e roteamento para o sintetizador interno (sem dependência de bpy).

Responsabilidade:
    Representar eventos de nota (note on/off) de forma independente da
    origem (teclado virtual do Piano Roll, dispositivo MIDI externo via
    `bpy.types.Event` do teclado do sistema, ou notas de uma progressão de
    acordes) e rotear para synth.play_note / synth.play_chord.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from . import synth
from .instruments import Instrument

NOTE_ON = "NOTE_ON"
NOTE_OFF = "NOTE_OFF"


@dataclass
class MidiEvent:
    """Um evento MIDI simples (note on/off)."""

    kind: str            # NOTE_ON ou NOTE_OFF
    pitch: int            # nota MIDI 0-127
    velocity: int = 100    # 0-127 (irrelevante em NOTE_OFF)
    channel: int = 0        # canal MIDI 0-15 (reservado para uso futuro)


# Notas atualmente soando por instrumento (para lógica de mono/portamento futura)
_active_notes: dict[int, set[int]] = {}


def note_on(instrument: Instrument, pitch: int, velocity: int = 100, duration: float = 0.8) -> None:
    """
    Dispara uma nota em um instrumento, aplicando deslocamento de oitava
    e volume, e respeitando o modo mono (corta vozes anteriores).
    """
    shifted_pitch = instrument.apply_octave_shift(pitch)
    scaled_velocity = max(1, min(127, int(velocity * instrument.volume)))

    if instrument.mono:
        _active_notes[instrument.instrument_id] = {shifted_pitch}
    else:
        _active_notes.setdefault(instrument.instrument_id, set()).add(shifted_pitch)

    synth.play_note(
        shifted_pitch,
        instrument.instrument_id,
        duration=duration,
        velocity=scaled_velocity,
    )


def note_off(instrument: Instrument, pitch: int) -> None:
    """
    Marca uma nota como solta. O sintetizador atual (synth.py) tem release
    fixo por-nota (sem sustain contínuo), então isso só atualiza o estado
    de vozes ativas — mantido para compatibilidade futura com um motor
    com sustain real.
    """
    shifted_pitch = instrument.apply_octave_shift(pitch)
    _active_notes.get(instrument.instrument_id, set()).discard(shifted_pitch)


def play_chord(instrument: Instrument, pitches: List[int], velocity: int = 90, duration: float = 1.5) -> None:
    """Toca várias notas simultaneamente em um instrumento (aplica oitava/volume de cada uma)."""
    shifted = [instrument.apply_octave_shift(p) for p in pitches]
    scaled_velocity = max(1, min(127, int(velocity * instrument.volume)))
    synth.play_chord(shifted, instrument.instrument_id, duration=duration, velocity=scaled_velocity)


def active_notes_for(instrument: Instrument) -> List[int]:
    """Lista as notas atualmente marcadas como ativas para um instrumento."""
    return sorted(_active_notes.get(instrument.instrument_id, set()))


def panic() -> None:
    """Limpa o estado interno de notas ativas de todos os instrumentos (não interrompe áudio já disparado)."""
    _active_notes.clear()