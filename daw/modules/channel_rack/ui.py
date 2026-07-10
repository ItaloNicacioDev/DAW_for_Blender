# modules/channel_rack/ui.py
"""
Painéis de UI do Blender para o Channel Rack.

Segue o mesmo padrão dos outros painéis do projeto:
    - bl_space_type = 'SEQUENCE_EDITOR' (onde a DAW vive)
    - bl_category   = "DAW"
"""
from __future__ import annotations

import bpy
from bpy.types import Panel, UIList

from .icons import (
    icon_for_instrument,
    icon_for_mute,
    icon_for_solo,
    icon_for_step,
    ICON_ADD,
    ICON_REMOVE,
    ICON_DUPLICATE,
    ICON_GROUP,
    ICON_LOCKED,
    ICON_UNLOCKED,
)


class DAW_UL_ChannelList(UIList):
    """Lista de canais do Channel Rack (nome, cor, mute/solo)."""
    bl_idname = "DAW_UL_channel_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        channel = item
        row = layout.row(align=True)

        row.label(text="", icon=icon_for_instrument(channel.instrument_type))

        sub = row.row()
        sub.scale_x = 0.35
        sub.prop(channel, "color", text="")

        row.prop(channel, "name", text="", emboss=False)

        row.prop(
            channel, "mute", text="",
            icon=icon_for_mute(channel.mute), emboss=False,
        )
        row.prop(
            channel, "solo", text="",
            icon=icon_for_solo(channel.solo), emboss=False,
        )
        row.prop(
            channel, "locked", text="",
            icon=ICON_LOCKED if channel.locked else ICON_UNLOCKED, emboss=False,
        )


class DAW_PT_ChannelRack(Panel):
    bl_label = "Channel Rack"
    bl_idname = "DAW_PT_channel_rack"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        rack = context.scene.daw_channel_rack

        # --- Lista de canais ---
        row = layout.row()
        row.template_list(
            "DAW_UL_channel_list", "",
            rack, "channels",
            rack, "active_channel_index",
            rows=5,
        )

        col = row.column(align=True)
        col.operator("daw.add_channel", text="", icon=ICON_ADD)
        col.operator("daw.remove_channel", text="", icon=ICON_REMOVE)
        col.separator()
        col.operator("daw.duplicate_channel", text="", icon=ICON_DUPLICATE)
        col.separator()
        col.operator("daw.move_channel", text="", icon='TRIA_UP').direction = "UP"
        col.operator("daw.move_channel", text="", icon='TRIA_DOWN').direction = "DOWN"

        # --- Propriedades do canal ativo ---
        channel = None
        if 0 <= rack.active_channel_index < len(rack.channels):
            channel = rack.channels[rack.active_channel_index]

        if channel is not None:
            box = layout.box()
            box.prop(channel, "instrument_type")
            if channel.instrument_type == "SAMPLER":
                box.prop(channel, "sample_path", text="Amostra")

            row = box.row(align=True)
            row.prop(channel, "volume")
            row.prop(channel, "pan")

            row = box.row(align=True)
            row.operator("daw.clear_channel_steps", text="Limpar Pattern", icon='TRASH')

        # --- Steps do canal ativo ---
        if channel is not None:
            box = layout.box()
            box.label(text=f"Pattern — {channel.name}", icon='SEQUENCE')

            grid = box.grid_flow(row_major=True, columns=8, even_columns=True, even_rows=True)
            for i in range(rack.step_count):
                op = grid.operator(
                    "daw.toggle_step",
                    text=str(i + 1),
                    icon=icon_for_step(channel.steps[i]),
                    depress=channel.steps[i],
                )
                op.channel_index = rack.active_channel_index
                op.step_index = i

        # --- Opções gerais do rack ---
        box = layout.box()
        box.label(text="Opções do Rack", icon='SETTINGS')
        box.prop(rack, "step_count")
        box.prop(rack, "master_volume")


class DAW_PT_ChannelGroups(Panel):
    bl_label = "Grupos"
    bl_idname = "DAW_PT_channel_groups"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_channel_rack"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        rack = context.scene.daw_channel_rack

        row = layout.row()
        col = row.column()
        for i, group in enumerate(rack.groups):
            box = col.box()
            r = box.row(align=True)
            r.label(text="", icon=ICON_GROUP)
            r.prop(group, "color", text="")
            r.prop(group, "name", text="")
            r.prop(group, "muted", text="", icon=icon_for_mute(group.muted))
            op = r.operator("daw.remove_channel_group", text="", icon='X')
            op.index = i

        layout.operator("daw.add_channel_group", text="Adicionar Grupo", icon=ICON_ADD)

        channel = None
        if 0 <= rack.active_channel_index < len(rack.channels):
            channel = rack.channels[rack.active_channel_index]

        if channel is not None and len(rack.groups) > 0:
            layout.separator()
            layout.label(text=f"Grupo do canal '{channel.name}':")
            row = layout.row(align=True)
            for i, group in enumerate(rack.groups):
                op = row.operator(
                    "daw.assign_channel_to_group",
                    text=group.name,
                    depress=(channel.group_index == i),
                )
                op.channel_index = rack.active_channel_index
                op.group_index = i


classes = [
    DAW_UL_ChannelList,
    DAW_PT_ChannelRack,
    DAW_PT_ChannelGroups,
]