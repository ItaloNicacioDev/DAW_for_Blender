# modules/instruments/__init__.py
"""
Módulo de Instrumentos da DAW.

Responsabilidade:
    Gerenciar um rack de instrumentos configurados a partir do
    sintetizador interno (synth.py — timbres estilo GM 0-7), com volume,
    pan, oitava, mono/poly, presets e progressões de acordes prontas para
    inserir no Piano Roll.

Arquitetura:
    synth.py       — sintetizador interno (síntese aditiva via `aud`), já existente
    instruments.py — Instrument: modelo puro de um instrumento (sem bpy)
    midi.py        — eventos de nota (note on/off, acordes) roteados para synth.py
    presets.py     — combina presets embutidos com presets salvos pelo usuário
    utils.py       — ponte entre o modelo puro e o RNA + inserção no Piano Roll
    properties.py  — PropertyGroups do Blender (estado real da UI)
    operators.py   — Operators do Blender (ações de edição / preview / inserção)
    ui.py          — Painéis do Blender
    register.py    — register() / unregister()

Uso fora do Blender, a partir do modelo puro:
    from daw.modules.instruments import Instrument, note_on

    piano = Instrument(name="Piano", instrument_id=0, volume=0.85)
    note_on(piano, pitch=60, velocity=100)  # toca C4

Uso a partir da cena do Blender (RNA), dentro de um Operator/Panel:
    rack_props = context.scene.daw_instruments
    for inst in rack_props.instruments:
        ...
"""
from __future__ import annotations

from . import synth
from .instruments import Instrument, gm_instrument_names, MIN_OCTAVE_SHIFT, MAX_OCTAVE_SHIFT
from .midi import MidiEvent, NOTE_ON, NOTE_OFF, note_on, note_off, play_chord, active_notes_for, panic
from .presets import (
    BUILTIN_PRESETS,
    list_all_preset_names,
    get_preset,
    save_user_preset,
    delete_user_preset,
)
from .utils import (
    clamp_index,
    unique_instrument_name,
    get_active_instrument,
    instrument_props_to_model,
    apply_model_to_instrument_props,
    any_solo_active,
    insert_progression_to_piano_roll,
    get_playhead_beat,
)
from .register import register, unregister

__all__ = [
    # Sintetizador interno (já existente)
    "synth",
    # Modelo puro
    "Instrument", "gm_instrument_names", "MIN_OCTAVE_SHIFT", "MAX_OCTAVE_SHIFT",
    "MidiEvent", "NOTE_ON", "NOTE_OFF", "note_on", "note_off", "play_chord",
    "active_notes_for", "panic",
    # Presets
    "BUILTIN_PRESETS", "list_all_preset_names", "get_preset",
    "save_user_preset", "delete_user_preset",
    # Utils / ponte RNA
    "clamp_index", "unique_instrument_name", "get_active_instrument",
    "instrument_props_to_model", "apply_model_to_instrument_props",
    "any_solo_active", "insert_progression_to_piano_roll", "get_playhead_beat",
    # Blender
    "register", "unregister",
]