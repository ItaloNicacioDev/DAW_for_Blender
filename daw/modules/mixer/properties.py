# modules/effects/properties.py
"""
Propriedades RNA do Blender para o módulo de Efeitos.

Cada tipo de efeito tem seu próprio PropertyGroup (espelhando os
dataclasses de chorus.py, compressor.py, etc). Um EffectSlotProperties
guarda todos eles como PointerProperty e usa `effect_type` para saber
qual exibir/usar — é o jeito padrão de simular um "union type" em RNA.

Estado real fica em context.scene.daw_effects.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .delay import SYNC_DIVISIONS
from .distortion import DISTORTION_MODES
from .eq import BAND_TYPES, MAX_BANDS
from .rack import EFFECT_TYPES

EFFECT_TYPE_ITEMS = (
    ("CHORUS", "Chorus", "Duplica e modula o sinal para um efeito de coro"),
    ("COMPRESSOR", "Compressor", "Reduz a faixa dinâmica do sinal"),
    ("DELAY", "Delay", "Repetições atrasadas do sinal"),
    ("DISTORTION", "Distorção", "Satura/distorce o sinal"),
    ("EQ", "EQ", "Equalizador paramétrico multibanda"),
    ("FLANGER", "Flanger", "Modulação de fase com regeneração metálica"),
    ("LIMITER", "Limiter", "Limita o pico máximo do sinal"),
    ("PHASER", "Phaser", "Modulação de fase em múltiplos estágios"),
    ("REVERB", "Reverb", "Simula a reverberação de um ambiente"),
)


# ------------------------------------------------------------------ #
# Um PropertyGroup por tipo de efeito (espelha o dataclass correspondente)
# ------------------------------------------------------------------ #
class ChorusProperties(PropertyGroup):
    rate: FloatProperty(name="Velocidade", default=1.2, min=0.05, max=10.0, unit='NONE')
    depth: FloatProperty(name="Profundidade", default=0.35, min=0.0, max=1.0, subtype='FACTOR')
    voices: IntProperty(name="Vozes", default=2, min=1, max=4)
    feedback: FloatProperty(name="Feedback", default=0.15, min=0.0, max=0.9, subtype='FACTOR')
    mix: FloatProperty(name="Mix", default=0.5, min=0.0, max=1.0, subtype='FACTOR')


class CompressorProperties(PropertyGroup):
    threshold_db: FloatProperty(name="Threshold (dB)", default=-18.0, min=-60.0, max=0.0)
    ratio: FloatProperty(name="Ratio", default=4.0, min=1.0, max=20.0)
    attack_ms: FloatProperty(name="Attack (ms)", default=10.0, min=0.1, max=200.0)
    release_ms: FloatProperty(name="Release (ms)", default=120.0, min=5.0, max=2000.0)
    knee_db: FloatProperty(name="Knee (dB)", default=6.0, min=0.0, max=24.0)
    makeup_gain_db: FloatProperty(name="Makeup Gain (dB)", default=0.0, min=-12.0, max=24.0)
    mix: FloatProperty(name="Mix", default=1.0, min=0.0, max=1.0, subtype='FACTOR')


class DelayProperties(PropertyGroup):
    time_ms: FloatProperty(name="Tempo (ms)", default=350.0, min=1.0, max=4000.0)
    sync: BoolProperty(name="Sincronizar com BPM", default=False)
    sync_division: EnumProperty(
        name="Divisão", items=[(d, d, "") for d in SYNC_DIVISIONS], default="1/4"
    )
    feedback: FloatProperty(name="Feedback", default=0.35, min=0.0, max=0.95, subtype='FACTOR')
    ping_pong: BoolProperty(name="Ping Pong", default=False)
    mix: FloatProperty(name="Mix", default=0.35, min=0.0, max=1.0, subtype='FACTOR')


class DistortionProperties(PropertyGroup):
    drive: FloatProperty(name="Drive", default=0.4, min=0.0, max=1.0, subtype='FACTOR')
    tone: FloatProperty(name="Tom", default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    mode: EnumProperty(
        name="Modo", items=[(m, m.title(), "") for m in DISTORTION_MODES], default="SOFT"
    )
    output_gain_db: FloatProperty(name="Ganho de Saída (dB)", default=0.0, min=-24.0, max=24.0)
    mix: FloatProperty(name="Mix", default=1.0, min=0.0, max=1.0, subtype='FACTOR')


class EQBandProperties(PropertyGroup):
    enabled: BoolProperty(name="Ativa", default=True)
    band_type: EnumProperty(
        name="Tipo", items=[(t, t.title(), "") for t in BAND_TYPES], default="PEAK"
    )
    freq: FloatProperty(name="Frequência (Hz)", default=1000.0, min=20.0, max=20000.0)
    gain_db: FloatProperty(name="Ganho (dB)", default=0.0, min=-24.0, max=24.0)
    q: FloatProperty(name="Q", default=0.71, min=0.1, max=10.0)


class EQProperties(PropertyGroup):
    bands: CollectionProperty(type=EQBandProperties)
    active_band_index: IntProperty(name="Banda Ativa", default=0, min=0)


class FlangerProperties(PropertyGroup):
    rate: FloatProperty(name="Velocidade", default=0.25, min=0.02, max=10.0)
    depth: FloatProperty(name="Profundidade", default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    feedback: FloatProperty(name="Feedback", default=0.4, min=0.0, max=0.95, subtype='FACTOR')
    manual_ms: FloatProperty(name="Manual (ms)", default=1.0, min=0.1, max=20.0)
    mix: FloatProperty(name="Mix", default=0.5, min=0.0, max=1.0, subtype='FACTOR')


class LimiterProperties(PropertyGroup):
    ceiling_db: FloatProperty(name="Teto (dB)", default=-0.3, min=-12.0, max=0.0)
    release_ms: FloatProperty(name="Release (ms)", default=50.0, min=1.0, max=1000.0)
    lookahead_ms: FloatProperty(name="Lookahead (ms)", default=5.0, min=0.0, max=20.0)
    input_gain_db: FloatProperty(name="Ganho de Entrada (dB)", default=0.0, min=-12.0, max=24.0)


class PhaserProperties(PropertyGroup):
    rate: FloatProperty(name="Velocidade", default=0.5, min=0.02, max=10.0)
    depth: FloatProperty(name="Profundidade", default=0.6, min=0.0, max=1.0, subtype='FACTOR')
    feedback: FloatProperty(name="Feedback", default=0.3, min=0.0, max=0.95, subtype='FACTOR')
    stages: IntProperty(name="Estágios", default=4, min=2, max=12, step=2)
    mix: FloatProperty(name="Mix", default=0.5, min=0.0, max=1.0, subtype='FACTOR')


class ReverbProperties(PropertyGroup):
    room_size: FloatProperty(name="Tamanho da Sala", default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    damping: FloatProperty(name="Amortecimento", default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    width: FloatProperty(name="Largura Estéreo", default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    pre_delay_ms: FloatProperty(name="Pre-Delay (ms)", default=20.0, min=0.0, max=200.0)
    mix: FloatProperty(name="Mix", default=0.3, min=0.0, max=1.0, subtype='FACTOR')


# ------------------------------------------------------------------ #
# Slot / Cadeia / Rack
# ------------------------------------------------------------------ #
class EffectSlotProperties(PropertyGroup):
    """Um efeito dentro da cadeia de inserts de um canal."""

    effect_type: EnumProperty(name="Tipo", items=EFFECT_TYPE_ITEMS, default="EQ")
    enabled: BoolProperty(name="Ativo", default=True)
    bypass: BoolProperty(name="Bypass", default=False)

    # Um PointerProperty por tipo — só o que corresponde a `effect_type` é usado
    chorus: PointerProperty(type=ChorusProperties)
    compressor: PointerProperty(type=CompressorProperties)
    delay: PointerProperty(type=DelayProperties)
    distortion: PointerProperty(type=DistortionProperties)
    eq: PointerProperty(type=EQProperties)
    flanger: PointerProperty(type=FlangerProperties)
    limiter: PointerProperty(type=LimiterProperties)
    phaser: PointerProperty(type=PhaserProperties)
    reverb: PointerProperty(type=ReverbProperties)

    def get_active_params(self):
        """Retorna o PropertyGroup correspondente ao `effect_type` atual."""
        return getattr(self, self.effect_type.lower())


class EffectsChainProperties(PropertyGroup):
    """Cadeia de efeitos associada a um canal do Channel Rack."""

    channel_index: IntProperty(name="Índice do Canal", default=-1)
    slots: CollectionProperty(type=EffectSlotProperties)
    active_slot_index: IntProperty(name="Slot Ativo", default=0, min=0)


class EffectsRackProperties(PropertyGroup):
    """Estado global do módulo de Efeitos — anexado a context.scene.daw_effects."""

    chains: CollectionProperty(type=EffectsChainProperties)
    active_chain_index: IntProperty(name="Cadeia Ativa", default=0, min=0)


_ALL_CLASSES = [
    ChorusProperties,
    CompressorProperties,
    DelayProperties,
    DistortionProperties,
    EQBandProperties,
    EQProperties,
    FlangerProperties,
    LimiterProperties,
    PhaserProperties,
    ReverbProperties,
    EffectSlotProperties,
    EffectsChainProperties,
    EffectsRackProperties,
]


def register() -> None:
    for cls in _ALL_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_effects = bpy.props.PointerProperty(type=EffectsRackProperties)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "daw_effects"):
        del bpy.types.Scene.daw_effects
    for cls in reversed(_ALL_CLASSES):
        bpy.utils.unregister_class(cls)