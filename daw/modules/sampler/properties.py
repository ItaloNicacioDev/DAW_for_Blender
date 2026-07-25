# modules/sampler/properties.py
"""
Propriedades e estados do módulo Sampler.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
    CollectionProperty,
)
from bpy.types import PropertyGroup


class DAW_SamplerADSR(PropertyGroup):
    attack: FloatProperty(name="Attack", default=0.01, min=0.0001, max=10.0, unit='TIME')
    decay: FloatProperty(name="Decay", default=0.1, min=0.0001, max=10.0, unit='TIME')
    sustain: FloatProperty(name="Sustain", default=0.8, min=0.0, max=1.0)
    release: FloatProperty(name="Release", default=0.2, min=0.0001, max=10.0, unit='TIME')


class DAW_SamplerSlice(PropertyGroup):
    name: StringProperty(default="Slice")
    start_frame: IntProperty(default=0, min=0)
    end_frame: IntProperty(default=0, min=0)


class DAW_SamplerSample(PropertyGroup):
    name: StringProperty(name="Nome", default="Sample")
    filepath: StringProperty(name="Arquivo", subtype='FILE_PATH', default="")

    samplerate: IntProperty(default=48000)
    channels: IntProperty(default=1)
    num_frames: IntProperty(default=0)

    # --- Afinação ----------------------------------------------------------
    root_note: IntProperty(
        name="Nota Raiz",
        description="Nota MIDI (0-127) na qual o sample toca sem transposição",
        default=60, min=0, max=127,
    )
    note_low: IntProperty(name="Nota Mínima", default=0, min=0, max=127)
    note_high: IntProperty(name="Nota Máxima", default=127, min=0, max=127)
    tune_semitones: FloatProperty(name="Afinação (semitons)", default=0.0, min=-48.0, max=48.0)
    tune_cents: FloatProperty(name="Afinação (cents)", default=0.0, min=-100.0, max=100.0)

    gain_db: FloatProperty(name="Ganho (dB)", default=0.0, min=-60.0, max=24.0)
    pan: FloatProperty(name="Pan", default=0.0, min=-1.0, max=1.0)
    reverse: BoolProperty(name="Reverso", default=False)

    # --- Loop ----------------------------------------------------------------
    loop_mode: EnumProperty(
        name="Modo de Loop",
        items=[
            ('OFF', "Sem Loop", "Reproduz o sample uma única vez"),
            ('FORWARD', "Forward", "Repete do início ao fim do loop continuamente"),
            ('PING_PONG', "Ping-Pong", "Alterna direção a cada extremidade do loop"),
        ],
        default='OFF',
    )
    loop_start: IntProperty(name="Início do Loop", default=0, min=0)
    loop_end: IntProperty(name="Fim do Loop", default=0, min=0)
    loop_crossfade_ms: FloatProperty(name="Crossfade (ms)", default=5.0, min=0.0, max=500.0)

    # --- Envelope --------------------------------------------------------------
    adsr: PointerProperty(type=DAW_SamplerADSR)

    # --- Time-stretch --------------------------------------------------------
    stretch_enabled: BoolProperty(name="Time-Stretch", default=False)
    stretch_ratio: FloatProperty(
        name="Razão",
        description="1.0 = duração original; >1 = mais longo; <1 = mais curto",
        default=1.0, min=0.1, max=4.0,
    )

    # --- Slices ------------------------------------------------------------------
    slices: CollectionProperty(type=DAW_SamplerSlice)
    active_slice_index: IntProperty(default=0)
    play_as_slices: BoolProperty(
        name="Tocar como Fatias",
        description="Cada fatia é disparada por uma nota MIDI sequencial a partir da nota raiz",
        default=False,
    )


class DAW_SamplerSettings(PropertyGroup):
    bl_idname = "DAW_SamplerSettings"

    samples: CollectionProperty(type=DAW_SamplerSample)
    active_sample_index: IntProperty(default=0)

    polyphony: IntProperty(
        name="Polifonia",
        description="Número máximo de vozes simultâneas",
        default=16, min=1, max=64,
    )

    master_gain_db: FloatProperty(name="Ganho Master (dB)", default=0.0, min=-60.0, max=12.0)
    output_device: StringProperty(name="Dispositivo de Saída", default="Default")

    preview_note: IntProperty(name="Nota de Preview", default=60, min=0, max=127)
    preview_velocity: FloatProperty(name="Velocidade", default=1.0, min=0.0, max=1.0)

    is_previewing: BoolProperty(default=False)


classes = [
    DAW_SamplerADSR,
    DAW_SamplerSlice,
    DAW_SamplerSample,
    DAW_SamplerSettings,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_sampler_settings = PointerProperty(type=DAW_SamplerSettings)


def unregister():
    del bpy.types.Scene.daw_sampler_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)