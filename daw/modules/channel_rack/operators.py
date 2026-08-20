# modules/channel_rack/operators.py
"""
Operators do Blender para o Channel Rack.

Responsabilidade:
    Ações de edição disparadas pela UI: adicionar/remover/duplicar canal,
    mover canal, alternar step, mute/solo, gerenciar grupos.
"""
from __future__ import annotations

import bpy
from bpy.props import IntProperty, StringProperty
from bpy.types import Operator

from .colors import get_color_by_index
from .utils import unique_channel_name, clamp_index


def _rack(context):
    return context.scene.daw_channel_rack


# ---------------------------------------------------------------------- #
# Canais
# ---------------------------------------------------------------------- #
class DAW_OT_AddChannel(Operator):
    bl_idname = "daw.add_channel"
    bl_label = "Adicionar Canal"
    bl_description = "Adiciona um novo canal ao Channel Rack"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="Novo Canal")
    instrument_type: StringProperty(default="SAMPLER")

    def execute(self, context):
        rack = _rack(context)
        ch = rack.channels.add()
        ch.name = unique_channel_name(rack, self.name)
        ch.instrument_type = self.instrument_type
        ch.color = get_color_by_index(len(rack.channels) - 1)
        ch.step_count = rack.step_count
        # Cada track novo nasce apontando pro próximo canal do VSE ainda
        # não usado por nenhum outro track do rack, pra não sobrepor
        # strips de tracks diferentes no mesmo canal por padrão -- o
        # usuário pode trocar depois em "Canal VSE" na lista.
        used = {c.vse_channel for c in rack.channels[:-1]}
        next_channel = 1
        while next_channel in used:
            next_channel += 1
        ch.vse_channel = next_channel
        rack.active_channel_index = len(rack.channels) - 1
        self.report({'INFO'}, f"Canal '{ch.name}' adicionado (VSE canal {next_channel})")
        return {'FINISHED'}


class DAW_OT_SelectChannel(Operator):
    bl_idname = "daw.select_channel"
    bl_label = "Selecionar Track"
    bl_description = "Torna este track o canal ativo (pra editar detalhes abaixo)"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=0)

    def execute(self, context):
        rack = _rack(context)
        if 0 <= self.index < len(rack.channels):
            rack.active_channel_index = self.index
        return {'FINISHED'}


class DAW_OT_RemoveChannel(Operator):
    bl_idname = "daw.remove_channel"
    bl_label = "Remover Canal"
    bl_description = "Remove o canal selecionado do Channel Rack"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_channel_index
        if not (0 <= index < len(rack.channels)):
            self.report({'WARNING'}, "Nenhum canal para remover")
            return {'CANCELLED'}

        name = rack.channels[index].name
        rack.channels.remove(index)
        rack.active_channel_index = clamp_index(rack.active_channel_index, len(rack.channels))
        self.report({'INFO'}, f"Canal '{name}' removido")
        return {'FINISHED'}


class DAW_OT_DuplicateChannel(Operator):
    bl_idname = "daw.duplicate_channel"
    bl_label = "Duplicar Canal"
    bl_description = "Duplica o canal selecionado (mesmo pattern e configurações)"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_channel_index
        if not (0 <= index < len(rack.channels)):
            self.report({'WARNING'}, "Nenhum canal para duplicar")
            return {'CANCELLED'}

        src = rack.channels[index]
        new = rack.channels.add()
        new.name = unique_channel_name(rack, f"{src.name} (cópia)")
        new.instrument_type = src.instrument_type
        new.sample_path = src.sample_path
        new.color = src.color
        new.volume = src.volume
        new.pan = src.pan
        new.mute = src.mute
        new.solo = False
        new.locked = False
        new.group_index = src.group_index
        new.step_count = src.step_count
        for i in range(len(src.steps)):
            new.steps[i] = src.steps[i]

        # Move o novo canal para logo abaixo do original
        rack.channels.move(len(rack.channels) - 1, index + 1)
        rack.active_channel_index = index + 1
        self.report({'INFO'}, f"Canal '{new.name}' criado")
        return {'FINISHED'}


class DAW_OT_MoveChannel(Operator):
    bl_idname = "daw.move_channel"
    bl_label = "Mover Canal"
    bl_description = "Move o canal selecionado para cima ou para baixo na lista"
    bl_options = {'REGISTER', 'UNDO'}

    direction: StringProperty(default="UP")  # 'UP' ou 'DOWN'

    def execute(self, context):
        rack = _rack(context)
        index = rack.active_channel_index
        target = index - 1 if self.direction == "UP" else index + 1

        if not (0 <= index < len(rack.channels)) or not (0 <= target < len(rack.channels)):
            return {'CANCELLED'}

        rack.channels.move(index, target)
        rack.active_channel_index = target
        return {'FINISHED'}


class DAW_OT_ToggleMute(Operator):
    bl_idname = "daw.toggle_channel_mute"
    bl_label = "Mudo"
    bl_description = "Ativa/desativa o mudo do canal"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_channel_index
        if not (0 <= index < len(rack.channels)):
            return {'CANCELLED'}
        rack.channels[index].mute = not rack.channels[index].mute
        return {'FINISHED'}


class DAW_OT_ToggleSolo(Operator):
    bl_idname = "daw.toggle_channel_solo"
    bl_label = "Solo"
    bl_description = "Ativa/desativa o solo do canal"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_channel_index
        if not (0 <= index < len(rack.channels)):
            return {'CANCELLED'}
        rack.channels[index].solo = not rack.channels[index].solo
        return {'FINISHED'}


class DAW_OT_ToggleChannelLock(Operator):
    bl_idname = "daw.toggle_channel_lock"
    bl_label = "Bloquear Canal"
    bl_description = "Bloqueia/desbloqueia a edição dos steps deste canal"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_channel_index
        if not (0 <= index < len(rack.channels)):
            return {'CANCELLED'}
        rack.channels[index].locked = not rack.channels[index].locked
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Steps
# ---------------------------------------------------------------------- #
class DAW_OT_ToggleStep(Operator):
    bl_idname = "daw.toggle_step"
    bl_label = "Alternar Step"
    bl_description = "Ativa/desativa um step do pattern do canal"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=0)
    step_index: IntProperty(default=0)

    def execute(self, context):
        rack = _rack(context)
        if not (0 <= self.channel_index < len(rack.channels)):
            return {'CANCELLED'}

        channel = rack.channels[self.channel_index]
        if channel.locked:
            self.report({'WARNING'}, f"Canal '{channel.name}' está bloqueado")
            return {'CANCELLED'}

        if not (0 <= self.step_index < len(channel.steps)):
            return {'CANCELLED'}

        channel.steps[self.step_index] = not channel.steps[self.step_index]
        return {'FINISHED'}


class DAW_OT_ClearSteps(Operator):
    bl_idname = "daw.clear_channel_steps"
    bl_label = "Limpar Pattern"
    bl_description = "Remove todos os steps ativos do canal selecionado"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_channel_index
        if not (0 <= index < len(rack.channels)):
            return {'CANCELLED'}

        channel = rack.channels[index]
        if channel.locked:
            self.report({'WARNING'}, f"Canal '{channel.name}' está bloqueado")
            return {'CANCELLED'}

        for i in range(len(channel.steps)):
            channel.steps[i] = False
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Grupos
# ---------------------------------------------------------------------- #
class DAW_OT_AddGroup(Operator):
    bl_idname = "daw.add_channel_group"
    bl_label = "Adicionar Grupo"
    bl_description = "Cria um novo grupo de canais"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="Novo Grupo")

    def execute(self, context):
        rack = _rack(context)
        group = rack.groups.add()
        group.name = self.name
        group.color = get_color_by_index(len(rack.groups) - 1)
        rack.active_group_index = len(rack.groups) - 1
        return {'FINISHED'}


class DAW_OT_RemoveGroup(Operator):
    bl_idname = "daw.remove_channel_group"
    bl_label = "Remover Grupo"
    bl_description = "Remove o grupo selecionado e desassocia seus canais"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_group_index
        if not (0 <= index < len(rack.groups)):
            return {'CANCELLED'}

        for ch in rack.channels:
            if ch.group_index == index:
                ch.group_index = -1
            elif ch.group_index > index:
                ch.group_index -= 1

        rack.groups.remove(index)
        rack.active_group_index = clamp_index(rack.active_group_index, len(rack.groups))
        return {'FINISHED'}


class DAW_OT_AssignChannelToGroup(Operator):
    bl_idname = "daw.assign_channel_to_group"
    bl_label = "Atribuir ao Grupo"
    bl_description = "Atribui o canal selecionado ao grupo ativo (-1 remove do grupo)"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    group_index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        ch_index = self.channel_index if self.channel_index >= 0 else rack.active_channel_index
        if not (0 <= ch_index < len(rack.channels)):
            return {'CANCELLED'}
        rack.channels[ch_index].group_index = self.group_index
        return {'FINISHED'}


classes = [
    DAW_OT_AddChannel,
    DAW_OT_SelectChannel,
    DAW_OT_RemoveChannel,
    DAW_OT_DuplicateChannel,
    DAW_OT_MoveChannel,
    DAW_OT_ToggleMute,
    DAW_OT_ToggleSolo,
    DAW_OT_ToggleChannelLock,
    DAW_OT_ToggleStep,
    DAW_OT_ClearSteps,
    DAW_OT_AddGroup,
    DAW_OT_RemoveGroup,
    DAW_OT_AssignChannelToGroup,
]