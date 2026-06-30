# modules/automation/properties.py
"""
Propriedades RNA do Blender para o módulo de automação.

Estas propriedades ficam em context.scene.daw_automation e servem como
estado da UI (qual clip está selecionado, qual parâmetro está sendo editado,
valor do zoom do editor de curvas, etc.).

O dado real (AutomationClip, AutomationCurve) vive no core/timeline.py —
aqui só temos o estado de seleção/edição necessário para o painel.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .interpolation import INTERPOLATION_ITEMS


class AutomationPointProperties(PropertyGroup):
    """Representa um ponto de controle editável no painel."""
    time: FloatProperty(
         name="Tempo",
        description="Posição do ponto em segundos",
        default=0.0,
        min=0.0,
        soft_max=600.0,
        unit='TIME',
    )
    value: FloatProperty(
        name="Valor",
        description="Valor do parâmetro neste ponto",
        default=0.5,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )
    mode: EnumProperty(
        name="Interpolação",
        description="Modo de interpolação até o próximo ponto",
        items=INTERPOLATION_ITEMS,
        default="LINEAR",
    )


class AutomationCurveProperties(PropertyGroup):
    """Metadados de uma curva no painel de UI."""
    target_param: StringProperty(
        name="Parâmetro",
        description="Parâmetro alvo (ex: 'channel.0.volume', 'master.volume', 'bpm')",
        default="volume",
    )
    enabled: BoolProperty(
        name="Ativada",
        description="Se False, a curva é ignorada durante a reprodução",
        default=True,
    )
    min_val: FloatProperty(
        name="Mínimo",
        default=0.0,
    )
    max_val: FloatProperty(
        name="Máximo",
        default=1.0,
    )


class AutomationProperties(PropertyGroup):
    """
    Estado global da UI de automação — anexado a context.scene.daw_automation.
    """

    # Clip selecionado (índice na lista global de clips de automação)
    selected_clip_index: IntProperty(
        name="Clip Selecionado",
        default=0,
        min=0,
    )

    # Parâmetro sendo editado no momento
    active_param: StringProperty(
        name="Parâmetro Ativo",
        description="Parâmetro sendo editado na curva",
        default="volume",
    )

    # Interpolação padrão para novos pontos
    default_interpolation: EnumProperty(
        name="Interpolação Padrão",
        description="Modo de interpolação aplicado a novos pontos",
        items=INTERPOLATION_ITEMS,
        default="LINEAR",
    )

    # Zoom do editor de curvas
    zoom_x: FloatProperty(
        name="Zoom Horizontal",
        description="Escala de tempo do editor de curvas (px/s)",
        default=100.0,
        min=10.0,
        max=2000.0,
    )
    zoom_y: FloatProperty(
        name="Zoom Vertical",
        description="Escala de valor do editor de curvas",
        default=1.0,
        min=0.1,
        max=10.0,
    )

    # Grade de snap
    snap_enabled: BoolProperty(
        name="Snap",
        description="Ativa o snap ao grid de tempo",
        default=True,
    )
    snap_grid: FloatProperty(
        name="Grid (s)",
        description="Resolução do snap em segundos",
        default=0.25,
        min=0.0,
        soft_max=1.0,
    )

    # Visibilidade
    show_all_curves: BoolProperty(
        name="Mostrar Todas as Curvas",
        description="Exibe curvas de todos os parâmetros ou só o ativo",
        default=False,
    )


def register():
    bpy.utils.register_class(AutomationPointProperties)
    bpy.utils.register_class(AutomationCurveProperties)
    bpy.utils.register_class(AutomationProperties)
    bpy.types.Scene.daw_automation = bpy.props.PointerProperty(type=AutomationProperties)


def unregister():
    if hasattr(bpy.types.Scene, "daw_automation"):
        del bpy.types.Scene.daw_automation
    bpy.utils.unregister_class(AutomationProperties)
    bpy.utils.unregister_class(AutomationCurveProperties)
    bpy.utils.unregister_class(AutomationPointProperties)