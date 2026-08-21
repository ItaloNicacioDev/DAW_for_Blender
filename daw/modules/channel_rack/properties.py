# modules/channel_rack/properties.py
"""
Propriedades RNA do Blender para o Channel Rack.

Estas propriedades ficam em context.scene.daw_channel_rack e são o "dado
vivo" editado pela UI e pelos operadores. Para lógica de áudio/scheduler
pura (sem bpy), use rack.py / channels.py e a ponte em utils.py.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    BoolVectorProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .channels import INSTRUMENT_TYPES, MAX_STEPS, DEFAULT_STEP_COUNT
from .colors import get_color_by_index

INSTRUMENT_TYPE_ITEMS = (
    ("SAMPLER", "Sampler", "Reproduz uma amostra de áudio carregada"),
    ("SYNTH", "Synth", "Sintetizador interno"),
    ("AUDIO", "Áudio", "Canal de áudio simples"),
    ("MIDI", "MIDI", "Canal MIDI roteado para um instrumento externo"),
    ("DRUM", "Bateria", "Canal de percussão/bateria"),
)


def _on_step_count_change(self: "ChannelRackProperties", context: bpy.types.Context) -> None:
    """Propaga a mudança de step_count do rack para todos os canais."""
    for channel in self.channels:
        channel.step_count = self.step_count


def _on_active_channel_index_change(self: "ChannelRackProperties", context: bpy.types.Context) -> None:
    """Garante que o índice ativo nunca fique fora do range da coleção."""
    if len(self.channels) == 0:
        return
    if self.active_channel_index >= len(self.channels):
        self.active_channel_index = len(self.channels) - 1


class ChannelProperties(PropertyGroup):
    """Um canal do Channel Rack (instrumento/sample/áudio + pattern de steps)."""

    name: StringProperty(
        name="Nome",
        description="Nome do canal",
        default="Novo Canal",
    )

    instrument_type: EnumProperty(
        name="Tipo",
        description="Tipo de instrumento/fonte de áudio do canal",
        items=INSTRUMENT_TYPE_ITEMS,
        default="SAMPLER",
    )

    sample_path: StringProperty(
        name="Amostra",
        description="Caminho do arquivo de áudio usado pelo canal (Sampler)",
        default="",
        subtype='FILE_PATH',
    )

    color: FloatVectorProperty(
        name="Cor",
        description="Cor de identificação do canal",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=get_color_by_index(0),
    )

    volume: FloatProperty(
        name="Volume",
        description="Volume do canal",
        default=0.78,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )

    pan: FloatProperty(
        name="Pan",
        description="Panorâmica esquerda/direita do canal",
        default=0.0,
        min=-1.0,
        max=1.0,
        subtype='FACTOR',
    )

    mute: BoolProperty(
        name="Mudo",
        description="Silencia o canal",
        default=False,
    )

    solo: BoolProperty(
        name="Solo",
        description="Isola o canal (silencia os demais que não estão em solo)",
        default=False,
    )

    locked: BoolProperty(
        name="Bloqueado",
        description="Impede edição acidental dos steps deste canal",
        default=False,
    )

    group_index: IntProperty(
        name="Grupo",
        description="Índice do grupo ao qual este canal pertence (-1 = sem grupo)",
        default=-1,
        min=-1,
    )

    # ── Roteamento de VSE + monitoramento ao vivo ──────────────────────
    vse_channel: IntProperty(
        name="Canal VSE",
        description="Canal do Video Sequence Editor que este track do "
                     "Channel Rack controla -- strips de áudio criadas "
                     "por este track (bounce, gravação ao vivo, etc.) vão "
                     "para este canal do VSE",
        default=1,
        min=1,
        max=128,
    )

    monitor_source: EnumProperty(
        name="Fonte do Monitor",
        description="De onde o medidor de nível (VU) deste track lê o "
                     "áudio ao vivo",
        items=(
            ('NONE', 'Nenhuma', 'Sem monitoramento ao vivo -- medidor fica em silêncio'),
            ('INPUT', 'Entrada de Áudio', 'Lê o nível do dispositivo de entrada '
             'configurado globalmente (Preferências > Áudio) -- use para tracks '
             'de gravação ao vivo (voz, instrumento via linha/microfone)'),
        ),
        default='NONE',
    )

    meter_level: FloatProperty(
        name="Nível (VU)",
        description="Nível de pico atual, 0.0-1.0 -- atualizado ao vivo por "
                     "um timer enquanto monitor_source != 'NONE' (ver "
                     "channel_rack/register.py::_meter_update_tick)",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )

    step_count: IntProperty(
        name="Steps",
        description="Quantidade de steps ativos no pattern deste canal",
        default=DEFAULT_STEP_COUNT,
        min=1,
        max=MAX_STEPS,
    )

    steps: BoolVectorProperty(
        name="Pattern",
        description="Passos ativos/inativos do step sequencer",
        size=MAX_STEPS,
        default=[False] * MAX_STEPS,
    )


class ChannelGroupProperties(PropertyGroup):
    """Um grupo de canais do Channel Rack."""

    name: StringProperty(
        name="Nome",
        description="Nome do grupo",
        default="Novo Grupo",
    )

    color: FloatVectorProperty(
        name="Cor",
        description="Cor de identificação do grupo",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=get_color_by_index(0),
    )

    collapsed: BoolProperty(
        name="Recolhido",
        description="Recolhe os canais deste grupo na lista",
        default=False,
    )

    muted: BoolProperty(
        name="Mudo",
        description="Silencia todos os canais deste grupo",
        default=False,
    )


class ChannelRackProperties(PropertyGroup):
    """Estado global do Channel Rack — anexado a context.scene.daw_channel_rack."""

    channels: CollectionProperty(type=ChannelProperties)
    active_channel_index: IntProperty(
        name="Canal Ativo",
        default=0,
        min=0,
        update=_on_active_channel_index_change,
    )

    groups: CollectionProperty(type=ChannelGroupProperties)
    active_group_index: IntProperty(
        name="Grupo Ativo",
        default=0,
        min=0,
    )

    step_count: IntProperty(
        name="Steps do Pattern",
        description="Quantidade de steps do pattern atual (compartilhada por todos os canais)",
        default=DEFAULT_STEP_COUNT,
        min=1,
        max=MAX_STEPS,
        update=_on_step_count_change,
    )

    current_step: IntProperty(
        name="Step Atual",
        description="Step em reprodução no momento (controlado pelo clock/scheduler)",
        default=0,
        min=0,
    )

    master_volume: FloatProperty(
        name="Volume Master",
        description="Volume geral do Channel Rack",
        default=1.0,
        min=0.0,
        max=2.0,
        subtype='FACTOR',
    )

    show_mixer_strip_overlay: BoolProperty(
        name="Mostrar Mixer (overlay)",
        description="Mostra o card do mixer (channel strips com fader, "
                     "knob de pan e medidor de nível) ancorado no canto "
                     "inferior esquerdo do Sequencer",
        default=True,
    )


def register() -> None:
    bpy.utils.register_class(ChannelProperties)
    bpy.utils.register_class(ChannelGroupProperties)
    bpy.utils.register_class(ChannelRackProperties)
    bpy.types.Scene.daw_channel_rack = bpy.props.PointerProperty(type=ChannelRackProperties)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "daw_channel_rack"):
        del bpy.types.Scene.daw_channel_rack
    bpy.utils.unregister_class(ChannelRackProperties)
    bpy.utils.unregister_class(ChannelGroupProperties)
    bpy.utils.unregister_class(ChannelProperties)