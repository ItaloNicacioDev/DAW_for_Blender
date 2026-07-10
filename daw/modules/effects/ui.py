# modules/effects/ui.py
"""
Painéis de UI do Blender para o módulo de Efeitos.

Segue o mesmo padrão dos outros painéis do projeto:
    - bl_space_type = 'SEQUENCE_EDITOR' (onde a DAW vive)
    - bl_category   = "DAW"
"""
from __future__ import annotations

import bpy
from bpy.types import Panel, UIList, Menu

from .rack import EFFECT_TYPES
from .presets import list_all_preset_names
from .utils import get_or_create_chain


def _active_channel_index(context) -> int:
    """
    Usa o canal ativo do Channel Rack como referência, se o módulo estiver
    disponível; caso contrário assume o canal 0.
    """
    rack_props = getattr(context.scene, "daw_channel_rack", None)
    if rack_props is not None:
        return rack_props.active_channel_index
    return 0


def _active_channel_name(context) -> str:
    rack_props = getattr(context.scene, "daw_channel_rack", None)
    if rack_props is not None and 0 <= rack_props.active_channel_index < len(rack_props.channels):
        return rack_props.channels[rack_props.active_channel_index].name
    return "Canal 0"


class DAW_UL_EffectSlotList(UIList):
    """Lista de efeitos na cadeia de inserts do canal."""
    bl_idname = "DAW_UL_effect_slot_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        slot = item
        row = layout.row(align=True)

        icon_id = 'CHECKBOX_HLT' if (slot.enabled and not slot.bypass) else 'CHECKBOX_DEHLT'
        row.label(text="", icon=icon_id)

        label = dict(
            CHORUS="Chorus", COMPRESSOR="Compressor", DELAY="Delay",
            DISTORTION="Distorção", EQ="EQ", FLANGER="Flanger",
            LIMITER="Limiter", PHASER="Phaser", REVERB="Reverb",
        ).get(slot.effect_type, slot.effect_type.title())
        row.label(text=label)

        row.prop(slot, "bypass", text="", icon='HIDE_ON' if slot.bypass else 'HIDE_OFF', emboss=False)


class DAW_MT_AddEffect(Menu):
    """Menu para escolher qual tipo de efeito adicionar à cadeia."""
    bl_idname = "DAW_MT_add_effect"
    bl_label = "Adicionar Efeito"

    def draw(self, context):
        layout = self.layout
        channel_index = _active_channel_index(context)
        labels = dict(
            CHORUS="Chorus", COMPRESSOR="Compressor", DELAY="Delay",
            DISTORTION="Distorção", EQ="EQ", FLANGER="Flanger",
            LIMITER="Limiter", PHASER="Phaser", REVERB="Reverb",
        )
        for effect_type in EFFECT_TYPES:
            op = layout.operator("daw.add_effect", text=labels.get(effect_type, effect_type))
            op.channel_index = channel_index
            op.effect_type = effect_type


class DAW_MT_EffectPresets(Menu):
    """Menu com os presets disponíveis (embutidos + do usuário) para o efeito ativo."""
    bl_idname = "DAW_MT_effect_presets"
    bl_label = "Presets"

    def draw(self, context):
        layout = self.layout
        rack = context.scene.daw_effects
        channel_index = _active_channel_index(context)
        chain = get_or_create_chain(rack, channel_index)

        if not (0 <= chain.active_slot_index < len(chain.slots)):
            layout.label(text="Nenhum efeito selecionado")
            return

        slot = chain.slots[chain.active_slot_index]
        names = list_all_preset_names(slot.effect_type)
        if not names:
            layout.label(text="Sem presets")
            return

        for name in names:
            op = layout.operator("daw.apply_effect_preset", text=name)
            op.channel_index = channel_index
            op.slot_index = chain.active_slot_index
            op.preset_name = name


def _draw_slot_params(layout, slot) -> None:
    """Desenha os campos de parâmetro apropriados para o effect_type do slot."""
    if slot.effect_type == "CHORUS":
        p = slot.chorus
        layout.prop(p, "rate")
        layout.prop(p, "depth")
        layout.prop(p, "voices")
        layout.prop(p, "feedback")
        layout.prop(p, "mix")

    elif slot.effect_type == "COMPRESSOR":
        p = slot.compressor
        layout.prop(p, "threshold_db")
        layout.prop(p, "ratio")
        row = layout.row(align=True)
        row.prop(p, "attack_ms")
        row.prop(p, "release_ms")
        layout.prop(p, "knee_db")
        layout.prop(p, "makeup_gain_db")
        layout.prop(p, "mix")

    elif slot.effect_type == "DELAY":
        p = slot.delay
        layout.prop(p, "sync")
        if p.sync:
            layout.prop(p, "sync_division")
        else:
            layout.prop(p, "time_ms")
        layout.prop(p, "feedback")
        layout.prop(p, "ping_pong")
        layout.prop(p, "mix")

    elif slot.effect_type == "DISTORTION":
        p = slot.distortion
        layout.prop(p, "mode")
        layout.prop(p, "drive")
        layout.prop(p, "tone")
        layout.prop(p, "output_gain_db")
        layout.prop(p, "mix")

    elif slot.effect_type == "EQ":
        p = slot.eq
        row = layout.row()
        row.template_list(
            "UI_UL_list", "eq_bands",
            p, "bands",
            p, "active_band_index",
            rows=3,
        )
        col = row.column(align=True)
        op = col.operator("daw.add_eq_band", text="", icon='ADD')
        op = col.operator("daw.remove_eq_band", text="", icon='REMOVE')

        if 0 <= p.active_band_index < len(p.bands):
            band = p.bands[p.active_band_index]
            box = layout.box()
            box.prop(band, "enabled")
            box.prop(band, "band_type")
            box.prop(band, "freq")
            if band.band_type not in ("LOWCUT", "HIGHCUT"):
                box.prop(band, "gain_db")
            box.prop(band, "q")

    elif slot.effect_type == "FLANGER":
        p = slot.flanger
        layout.prop(p, "rate")
        layout.prop(p, "depth")
        layout.prop(p, "feedback")
        layout.prop(p, "manual_ms")
        layout.prop(p, "mix")

    elif slot.effect_type == "LIMITER":
        p = slot.limiter
        layout.prop(p, "ceiling_db")
        layout.prop(p, "release_ms")
        layout.prop(p, "lookahead_ms")
        layout.prop(p, "input_gain_db")

    elif slot.effect_type == "PHASER":
        p = slot.phaser
        layout.prop(p, "rate")
        layout.prop(p, "depth")
        layout.prop(p, "feedback")
        layout.prop(p, "stages")
        layout.prop(p, "mix")

    elif slot.effect_type == "REVERB":
        p = slot.reverb
        layout.prop(p, "room_size")
        layout.prop(p, "damping")
        layout.prop(p, "width")
        layout.prop(p, "pre_delay_ms")
        layout.prop(p, "mix")


class DAW_PT_Effects(Panel):
    bl_label = "Efeitos"
    bl_idname = "DAW_PT_effects"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 3

    def draw(self, context):
        layout = self.layout
        rack = context.scene.daw_effects
        channel_index = _active_channel_index(context)
        chain = get_or_create_chain(rack, channel_index)

        layout.label(text=f"Canal: {_active_channel_name(context)}", icon='SEQ_STRIP_DUPLICATE')

        row = layout.row()
        row.template_list(
            "DAW_UL_effect_slot_list", "",
            chain, "slots",
            chain, "active_slot_index",
            rows=4,
        )

        col = row.column(align=True)
        col.menu("DAW_MT_add_effect", text="", icon='ADD')
        op = col.operator("daw.remove_effect", text="", icon='REMOVE')
        op.channel_index = channel_index
        col.separator()
        op = col.operator("daw.move_effect", text="", icon='TRIA_UP')
        op.channel_index = channel_index
        op.direction = "UP"
        op = col.operator("daw.move_effect", text="", icon='TRIA_DOWN')
        op.channel_index = channel_index
        op.direction = "DOWN"

        if not (0 <= chain.active_slot_index < len(chain.slots)):
            return

        slot = chain.slots[chain.active_slot_index]

        box = layout.box()
        row = box.row(align=True)
        row.prop(slot, "enabled")
        row.prop(slot, "bypass")

        row = box.row(align=True)
        row.menu("DAW_MT_effect_presets", text="Presets", icon='PRESET')
        op = row.operator("daw.save_effect_preset", text="", icon='FILE_TICK')
        op.channel_index = channel_index
        op = row.operator("daw.reset_effect", text="", icon='LOOP_BACK')
        op.channel_index = channel_index

        box.separator()
        _draw_slot_params(box, slot)


classes = [
    DAW_UL_EffectSlotList,
    DAW_MT_AddEffect,
    DAW_MT_EffectPresets,
    DAW_PT_Effects,
]