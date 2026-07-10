# modules/effects/operators.py
"""
Operators do Blender para o módulo de Efeitos.

Responsabilidade:
    Ações de edição disparadas pela UI: adicionar/remover/mover efeito na
    cadeia de um canal, bypass/enable, aplicar e salvar presets, e editar
    bandas do EQ.
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import Operator

from . import presets as presets_module
from .rack import EFFECT_TYPES, default_params_for
from .utils import (
    get_or_create_chain,
    apply_params_dict_to_slot,
    slot_params_to_dict,
    clamp_index,
    params_attr_name,
)


def _rack(context):
    return context.scene.daw_effects


def _chain_for(context, channel_index: int, chain_index: int):
    """Resolve a cadeia por `chain_index` direto, ou por `channel_index` (cria se preciso)."""
    rack = _rack(context)
    if chain_index >= 0 and chain_index < len(rack.chains):
        return rack.chains[chain_index]
    return get_or_create_chain(rack, channel_index)


# ---------------------------------------------------------------------- #
# Slots de efeito
# ---------------------------------------------------------------------- #
class DAW_OT_AddEffect(Operator):
    bl_idname = "daw.add_effect"
    bl_label = "Adicionar Efeito"
    bl_description = "Adiciona um efeito ao final da cadeia de inserts do canal"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    chain_index: IntProperty(default=-1)
    effect_type: StringProperty(default="EQ")

    def execute(self, context):
        if self.effect_type not in EFFECT_TYPES:
            self.report({'ERROR'}, f"Tipo de efeito inválido: {self.effect_type}")
            return {'CANCELLED'}

        chain = _chain_for(context, self.channel_index, self.chain_index)
        slot = chain.slots.add()
        slot.effect_type = self.effect_type
        apply_params_dict_to_slot(slot, default_params_for(self.effect_type))
        chain.active_slot_index = len(chain.slots) - 1

        self.report({'INFO'}, f"Efeito '{self.effect_type.title()}' adicionado")
        return {'FINISHED'}


class DAW_OT_RemoveEffect(Operator):
    bl_idname = "daw.remove_effect"
    bl_label = "Remover Efeito"
    bl_description = "Remove o efeito selecionado da cadeia"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    chain_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)

    def execute(self, context):
        chain = _chain_for(context, self.channel_index, self.chain_index)
        index = self.slot_index if self.slot_index >= 0 else chain.active_slot_index
        if not (0 <= index < len(chain.slots)):
            return {'CANCELLED'}

        chain.slots.remove(index)
        chain.active_slot_index = clamp_index(chain.active_slot_index, len(chain.slots))
        return {'FINISHED'}


class DAW_OT_MoveEffect(Operator):
    bl_idname = "daw.move_effect"
    bl_label = "Mover Efeito"
    bl_description = "Move o efeito para cima ou para baixo na cadeia (altera a ordem de processamento)"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    chain_index: IntProperty(default=-1)
    direction: StringProperty(default="UP")  # 'UP' ou 'DOWN'

    def execute(self, context):
        chain = _chain_for(context, self.channel_index, self.chain_index)
        index = chain.active_slot_index
        target = index - 1 if self.direction == "UP" else index + 1

        if not (0 <= index < len(chain.slots)) or not (0 <= target < len(chain.slots)):
            return {'CANCELLED'}

        chain.slots.move(index, target)
        chain.active_slot_index = target
        return {'FINISHED'}


class DAW_OT_ToggleEffectBypass(Operator):
    bl_idname = "daw.toggle_effect_bypass"
    bl_label = "Bypass"
    bl_description = "Ativa/desativa o bypass deste efeito (mantém na cadeia sem processar)"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    chain_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)

    def execute(self, context):
        chain = _chain_for(context, self.channel_index, self.chain_index)
        index = self.slot_index if self.slot_index >= 0 else chain.active_slot_index
        if not (0 <= index < len(chain.slots)):
            return {'CANCELLED'}
        chain.slots[index].bypass = not chain.slots[index].bypass
        return {'FINISHED'}


class DAW_OT_ResetEffect(Operator):
    bl_idname = "daw.reset_effect"
    bl_label = "Restaurar Padrão"
    bl_description = "Restaura os parâmetros deste efeito para os valores padrão"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    chain_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)

    def execute(self, context):
        chain = _chain_for(context, self.channel_index, self.chain_index)
        index = self.slot_index if self.slot_index >= 0 else chain.active_slot_index
        if not (0 <= index < len(chain.slots)):
            return {'CANCELLED'}

        slot = chain.slots[index]
        apply_params_dict_to_slot(slot, default_params_for(slot.effect_type))
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Presets
# ---------------------------------------------------------------------- #
class DAW_OT_ApplyEffectPreset(Operator):
    bl_idname = "daw.apply_effect_preset"
    bl_label = "Aplicar Preset"
    bl_description = "Aplica um preset salvo aos parâmetros deste efeito"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    chain_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)
    preset_name: StringProperty(default="")

    def execute(self, context):
        chain = _chain_for(context, self.channel_index, self.chain_index)
        index = self.slot_index if self.slot_index >= 0 else chain.active_slot_index
        if not (0 <= index < len(chain.slots)):
            return {'CANCELLED'}

        slot = chain.slots[index]
        params = presets_module.resolve_params(slot.effect_type, self.preset_name)
        apply_params_dict_to_slot(slot, params)
        self.report({'INFO'}, f"Preset '{self.preset_name}' aplicado")
        return {'FINISHED'}


class DAW_OT_SaveEffectPreset(Operator):
    bl_idname = "daw.save_effect_preset"
    bl_label = "Salvar Preset"
    bl_description = "Salva os parâmetros atuais deste efeito como um novo preset"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    chain_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)
    preset_name: StringProperty(name="Nome do Preset", default="Meu Preset")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "preset_name")

    def execute(self, context):
        chain = _chain_for(context, self.channel_index, self.chain_index)
        index = self.slot_index if self.slot_index >= 0 else chain.active_slot_index
        if not (0 <= index < len(chain.slots)):
            return {'CANCELLED'}

        slot = chain.slots[index]
        params_dict = slot_params_to_dict(slot)
        ok = presets_module.save_user_preset(slot.effect_type, self.preset_name, params_dict)
        if ok:
            self.report({'INFO'}, f"Preset '{self.preset_name}' salvo")
        else:
            self.report({'ERROR'}, "Não foi possível salvar o preset")
        return {'FINISHED'} if ok else {'CANCELLED'}


# ---------------------------------------------------------------------- #
# Bandas do EQ
# ---------------------------------------------------------------------- #
class DAW_OT_AddEQBand(Operator):
    bl_idname = "daw.add_eq_band"
    bl_label = "Adicionar Banda"
    bl_description = "Adiciona uma banda ao EQ deste efeito"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    chain_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)

    def execute(self, context):
        from .eq import MAX_BANDS

        chain = _chain_for(context, self.channel_index, self.chain_index)
        index = self.slot_index if self.slot_index >= 0 else chain.active_slot_index
        if not (0 <= index < len(chain.slots)):
            return {'CANCELLED'}

        slot = chain.slots[index]
        if slot.effect_type != "EQ":
            self.report({'WARNING'}, "O efeito selecionado não é um EQ")
            return {'CANCELLED'}

        if len(slot.eq.bands) >= MAX_BANDS:
            self.report({'WARNING'}, f"Máximo de {MAX_BANDS} bandas atingido")
            return {'CANCELLED'}

        slot.eq.bands.add()
        slot.eq.active_band_index = len(slot.eq.bands) - 1
        return {'FINISHED'}


class DAW_OT_RemoveEQBand(Operator):
    bl_idname = "daw.remove_eq_band"
    bl_label = "Remover Banda"
    bl_description = "Remove a banda selecionada do EQ deste efeito"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    chain_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)
    band_index: IntProperty(default=-1)

    def execute(self, context):
        chain = _chain_for(context, self.channel_index, self.chain_index)
        index = self.slot_index if self.slot_index >= 0 else chain.active_slot_index
        if not (0 <= index < len(chain.slots)):
            return {'CANCELLED'}

        slot = chain.slots[index]
        if slot.effect_type != "EQ":
            return {'CANCELLED'}

        band_index = self.band_index if self.band_index >= 0 else slot.eq.active_band_index
        if not (0 <= band_index < len(slot.eq.bands)):
            return {'CANCELLED'}

        slot.eq.bands.remove(band_index)
        slot.eq.active_band_index = clamp_index(slot.eq.active_band_index, len(slot.eq.bands))
        return {'FINISHED'}


classes = [
    DAW_OT_AddEffect,
    DAW_OT_RemoveEffect,
    DAW_OT_MoveEffect,
    DAW_OT_ToggleEffectBypass,
    DAW_OT_ResetEffect,
    DAW_OT_ApplyEffectPreset,
    DAW_OT_SaveEffectPreset,
    DAW_OT_AddEQBand,
    DAW_OT_RemoveEQBand,
]