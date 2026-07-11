# modules/metronome/properties.py
"""
Propriedades RNA do Blender para o metrônomo.

O liga/desliga principal reaproveita context.scene.daw.metronome (já
definido em core/register.py e usado por daw/ui/panels.py). Este módulo
adiciona as configurações finas em context.scene.daw_metronome.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
)
from bpy.types import PropertyGroup

from .click import SOUND_STYLES

SOUND_STYLE_ITEMS = (
    ("CLICK", "Click", "Clique seco tradicional"),
    ("BEEP", "Beep", "Bipe eletrônico"),
    ("WOODBLOCK", "Wood Block", "Bloco de madeira"),
    ("COWBELL", "Cowbell", "Sino/cowbell"),
)


class MetronomeProperties(PropertyGroup):
    """Configurações finas do metrônomo — anexadas a context.scene.daw_metronome."""

    sound_style: EnumProperty(
        name="Som",
        description="Timbre do clique do metrônomo",
        items=SOUND_STYLE_ITEMS,
        default="CLICK",
    )

    volume: FloatProperty(
        name="Volume",
        default=0.8, min=0.0, max=1.0, subtype='FACTOR',
    )

    accent_first_beat: BoolProperty(
        name="Acentuar 1º Beat",
        description="Toca um clique mais forte/agudo no primeiro beat de cada compasso",
        default=True,
    )

    beats_per_bar: IntProperty(
        name="Beats por Compasso",
        description="Numerador da fórmula de compasso (ex: 4 em 4/4)",
        default=4, min=1, max=32,
    )

    beat_unit: IntProperty(
        name="Unidade de Beat",
        description="Denominador da fórmula de compasso (ex: 4 em 4/4)",
        default=4, min=1, max=32,
    )

    sync_with_playback: BoolProperty(
        name="Sincronizar com Reprodução",
        description="Se ativo, só clica enquanto o projeto está em reprodução; "
                     "se desativo, funciona como metrônomo de prática independente",
        default=True,
    )

    count_in_enabled: BoolProperty(
        name="Contagem de Entrada",
        description="Toca alguns compassos de clique antes de iniciar a reprodução",
        default=False,
    )

    count_in_bars: IntProperty(
        name="Compassos de Entrada",
        default=1, min=1, max=8,
    )

    # --- Estado interno (somente leitura pela UI) ---
    is_running: BoolProperty(
        name="Rodando",
        description="Indica se o timer interno do metrônomo está ativo no momento",
        default=False,
        options={'HIDDEN'},
    )

    is_counting_in: BoolProperty(
        name="Em Contagem",
        default=False,
        options={'HIDDEN'},
    )


def register() -> None:
    bpy.utils.register_class(MetronomeProperties)
    bpy.types.Scene.daw_metronome = bpy.props.PointerProperty(type=MetronomeProperties)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "daw_metronome"):
        del bpy.types.Scene.daw_metronome
    bpy.utils.unregister_class(MetronomeProperties)