# modules/instruments/properties.py
"""
Propriedades RNA do Blender para o módulo de Instrumentos.

Estado real fica em context.scene.daw_instruments.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from . import synth
from .instruments import gm_instrument_names, MIN_OCTAVE_SHIFT, MAX_OCTAVE_SHIFT

GM_INSTRUMENT_ITEMS = tuple(
    (str(iid), name, f"Timbre GM #{iid}") for iid, name in gm_instrument_names()
)

PROGRESSION_ITEMS = tuple(
    (name, name, synth.get_progression(name).get("description", ""))
    for name in synth.get_progression_names()
)


def _on_active_instrument_change(self: "InstrumentsRackProperties", context: bpy.types.Context) -> None:
    """Sincroniza o instrumento ativo do rack com o estado global do sintetizador (synth.py)."""
    if 0 <= self.active_instrument_index < len(self.instruments):
        inst = self.instruments[self.active_instrument_index]
        synth.set_instrument(int(inst.instrument_id))


def _on_instrument_id_change(self: "InstrumentProperties", context: bpy.types.Context) -> None:
    """Se este for o instrumento ativo, propaga a troca de timbre para o synth."""
    rack = context.scene.daw_instruments
    if 0 <= rack.active_instrument_index < len(rack.instruments):
        if rack.instruments[rack.active_instrument_index] == self:
            synth.set_instrument(int(self.instrument_id))


class InstrumentProperties(PropertyGroup):
    """Um instrumento do rack, referenciando um timbre do sintetizador interno (synth.py)."""

    name: StringProperty(
        name="Nome",
        description="Nome do instrumento",
        default="Novo Instrumento",
    )

    instrument_id: EnumProperty(
        name="Timbre",
        description="Timbre do sintetizador interno (estilo GM)",
        items=GM_INSTRUMENT_ITEMS,
        default="0",
        update=_on_instrument_id_change,
    )

    volume: FloatProperty(
        name="Volume", default=0.8, min=0.0, max=1.0, subtype='FACTOR',
    )
    pan: FloatProperty(
        name="Pan", default=0.0, min=-1.0, max=1.0, subtype='FACTOR',
    )

    octave_shift: IntProperty(
        name="Oitava",
        description="Desloca as notas tocadas neste instrumento em oitavas",
        default=0, min=MIN_OCTAVE_SHIFT, max=MAX_OCTAVE_SHIFT,
    )

    mono: BoolProperty(
        name="Mono",
        description="Modo monofônico — toca apenas uma nota por vez",
        default=False,
    )
    polyphony: IntProperty(
        name="Polifonia",
        description="Número máximo de vozes simultâneas (quando não está em modo mono)",
        default=8, min=1, max=32,
    )

    pitch_bend_range: IntProperty(
        name="Pitch Bend (semitons)",
        default=2, min=0, max=24,
    )

    mute: BoolProperty(name="Mudo", default=False)
    solo: BoolProperty(name="Solo", default=False)


class InstrumentsRackProperties(PropertyGroup):
    """Estado global do módulo de Instrumentos — anexado a context.scene.daw_instruments."""

    instruments: CollectionProperty(type=InstrumentProperties)
    active_instrument_index: IntProperty(
        name="Instrumento Ativo",
        default=0, min=0,
        update=_on_active_instrument_change,
    )

    preview_velocity: IntProperty(
        name="Velocity do Preview",
        default=100, min=1, max=127,
    )
    preview_duration: FloatProperty(
        name="Duração do Preview (s)",
        default=0.8, min=0.05, max=5.0,
    )

    selected_progression: EnumProperty(
        name="Progressão",
        description="Progressão de acordes pré-carregada (synth.CHORD_PROGRESSIONS)",
        items=PROGRESSION_ITEMS if PROGRESSION_ITEMS else [("NONE", "Nenhuma", "")],
    )
    insert_at_playhead: BoolProperty(
        name="Inserir no Playhead",
        description="Se ativo, insere a progressão a partir da posição atual do playhead; senão, a partir do início",
        default=True,
    )


_ALL_CLASSES = [
    InstrumentProperties,
    InstrumentsRackProperties,
]


def register() -> None:
    for cls in _ALL_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_instruments = bpy.props.PointerProperty(type=InstrumentsRackProperties)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "daw_instruments"):
        del bpy.types.Scene.daw_instruments
    for cls in reversed(_ALL_CLASSES):
        bpy.utils.unregister_class(cls)