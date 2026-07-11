# modules/instruments/utils.py
"""
Utilitários do módulo de Instrumentos.

Responsabilidade:
    Funções auxiliares usadas pelos operadores e pela UI: nomes únicos,
    clamp de índices, ponte entre InstrumentProperties (RNA) e o modelo
    puro Instrument, e inserção de progressões de acordes no Piano Roll.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from . import synth
from .instruments import Instrument

if TYPE_CHECKING:
    from .properties import InstrumentProperties, InstrumentsRackProperties


def clamp_index(index: int, length: int) -> int:
    """Restringe um índice ao range válido [0, length-1]. Retorna 0 se length <= 0."""
    if length <= 0:
        return 0
    return max(0, min(index, length - 1))


def unique_instrument_name(rack_props: "InstrumentsRackProperties", base_name: str) -> str:
    """Garante que `base_name` seja único dentro da coleção de instrumentos."""
    existing = {i.name for i in rack_props.instruments}
    if base_name not in existing:
        return base_name

    n = 2
    while f"{base_name} ({n})" in existing:
        n += 1
    return f"{base_name} ({n})"


def get_active_instrument(rack_props: "InstrumentsRackProperties") -> Optional["InstrumentProperties"]:
    if 0 <= rack_props.active_instrument_index < len(rack_props.instruments):
        return rack_props.instruments[rack_props.active_instrument_index]
    return None


def instrument_props_to_model(props: "InstrumentProperties") -> Instrument:
    """Converte um InstrumentProperties (RNA) no modelo puro Instrument."""
    return Instrument(
        name=props.name,
        instrument_id=int(props.instrument_id),
        volume=props.volume,
        pan=props.pan,
        octave_shift=props.octave_shift,
        mono=props.mono,
        polyphony=props.polyphony,
        pitch_bend_range=props.pitch_bend_range,
        mute=props.mute,
        solo=props.solo,
    )


def apply_model_to_instrument_props(instrument: Instrument, props: "InstrumentProperties") -> None:
    """Copia os valores do modelo puro Instrument de volta para o InstrumentProperties (RNA)."""
    props.name = instrument.name
    props.instrument_id = str(instrument.instrument_id)
    props.volume = instrument.volume
    props.pan = instrument.pan
    props.octave_shift = instrument.octave_shift
    props.mono = instrument.mono
    props.polyphony = instrument.polyphony
    props.pitch_bend_range = instrument.pitch_bend_range
    props.mute = instrument.mute
    props.solo = instrument.solo


def any_solo_active(rack_props: "InstrumentsRackProperties") -> bool:
    return any(i.solo for i in rack_props.instruments)


def insert_progression_to_piano_roll(
    context,
    progression_name: str,
    start_beat: float = 0.0,
    octave_shift: int = 0,
) -> int:
    """
    Insere as notas de uma progressão de acordes pré-definida (synth.CHORD_PROGRESSIONS)
    em context.scene.piano_roll.notes, deslocadas para começar em `start_beat`.
    Retorna a quantidade de notas inseridas.
    """
    piano_roll = getattr(context.scene, "piano_roll", None)
    if piano_roll is None:
        return 0

    note_dicts = synth.progression_to_midi_notes(progression_name)
    if not note_dicts:
        return 0

    for nd in note_dicts:
        note = piano_roll.notes.add()
        note.pitch = max(0, min(127, nd["pitch"] + octave_shift * 12))
        note.start = nd["start"] + start_beat
        note.length = nd["length"]
        note.velocity = nd["velocity"]

    return len(note_dicts)


def get_playhead_beat(context) -> float:
    """
    Lê a posição atual do playhead em beats, se o timeline/transport do
    projeto expuser essa informação; caso contrário retorna 0.0.
    """
    daw_props = getattr(context.scene, "daw", None)
    if daw_props is not None and hasattr(daw_props, "playhead_beat"):
        return float(daw_props.playhead_beat)
    return 0.0