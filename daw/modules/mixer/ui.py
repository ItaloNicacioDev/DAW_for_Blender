# modules/mixer/ui.py
"""
Painéis de UI do Blender para o módulo Mixer.

Segue o mesmo padrão dos outros painéis do projeto:
    - bl_space_type = 'SEQUENCE_EDITOR' (onde a DAW vive)
    - bl_category   = "DAW"
"""
from __future__ import annotations

import bpy
from bpy.types import Menu, Panel, UIList

from .effects import EFFECT_TYPE_ITEMS, icon_for, label_for
from .presets import list_insert_preset_names, list_strip_preset_names
from .routing import bus_names
from .tracks import MASTER_TRACK_NAME


def _icon_for_mute(active: bool) -> str:
    return 'HIDE_ON' if active else 'HIDE_OFF'


def _icon_for_solo(active: bool) -> str:
    return 'SOLO_ON' if active else 'SOLO_OFF'


# ---------------------------------------------------------------------- #
# Listas
# ---------------------------------------------------------------------- #
class DAW_UL_MixerTrackList(UIList):
    """Lista de faixas do Mixer (cor, nome, mudo/solo, bus de saída)."""
    bl_idname = "DAW_UL_mixer_track_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        track = item
        row = layout.row(align=True)

        sub = row.row()
        sub.scale_x = 0.35
        sub.prop(track, "color", text="")

        row.prop(track, "name", text="", emboss=False)
        row.label(text=track.output_bus, icon='FORWARD')

        row.prop(track, "mute", text="", icon=_icon_for_mute(track.mute), emboss=False)
        row.prop(track, "solo", text="", icon=_icon_for_solo(track.solo), emboss=False)


class DAW_UL_MixerBusList(UIList):
    """Lista de buses do Mixer (Master + auxiliares)."""
    bl_idname = "DAW_UL_mixer_bus_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        bus = item
        row = layout.row(align=True)

        row.label(text="", icon='SPEAKER' if bus.is_master else 'OUTLINER_OB_SPEAKER')

        if bus.is_master:
            row.label(text=bus.name)
        else:
            row.prop(bus, "name", text="", emboss=False)

        row.prop(bus, "volume", text="")
        row.prop(bus, "mute", text="", icon=_icon_for_mute(bus.mute), emboss=False)


class DAW_UL_MixerInsertList(UIList):
    """Lista de inserts (efeitos) na cadeia da faixa ativa."""
    bl_idname = "DAW_UL_mixer_insert_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        slot = item
        row = layout.row(align=True)

        icon_id = 'CHECKBOX_HLT' if (slot.enabled and not slot.bypass) else 'CHECKBOX_DEHLT'
        row.label(text="", icon=icon_id)
        row.label(text=label_for(slot.effect_type), icon=icon_for(slot.effect_type))
        row.prop(slot, "bypass", text="", icon='HIDE_ON' if slot.bypass else 'HIDE_OFF', emboss=False)


class DAW_UL_MixerSendList(UIList):
    """Lista de sends (envios auxiliares) da faixa ativa."""
    bl_idname = "DAW_UL_mixer_send_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        send = item
        row = layout.row(align=True)

        row.prop(
            send, "enabled", text="",
            icon='CHECKBOX_HLT' if send.enabled else 'CHECKBOX_DEHLT', emboss=False,
        )
        row.label(text=send.bus_name, icon='FORWARD')
        row.prop(send, "level", text="")
        row.prop(send, "pre_fader", text="Pré", toggle=True)


# ---------------------------------------------------------------------- #
# Menus
# ---------------------------------------------------------------------- #
class DAW_MT_AddMixerInsert(Menu):
    """Menu para escolher qual tipo de efeito adicionar à cadeia da faixa."""
    bl_idname = "DAW_MT_add_mixer_insert"
    bl_label = "Adicionar Insert"

    def draw(self, context):
        layout = self.layout
        mixer = context.scene.daw_mixer
        for effect_type, display_name, _desc in EFFECT_TYPE_ITEMS:
            op = layout.operator(
                "daw.add_mixer_insert", text=display_name, icon=icon_for(effect_type)
            )
            op.track_index = mixer.active_track_index
            op.effect_type = effect_type


class DAW_MT_MixerInsertPresets(Menu):
    """Menu com os presets disponíveis para o insert ativo."""
    bl_idname = "DAW_MT_mixer_insert_presets"
    bl_label = "Presets"

    def draw(self, context):
        layout = self.layout
        mixer = context.scene.daw_mixer
        track = mixer.active_track

        if track is None or not (0 <= track.active_insert_index < len(track.inserts)):
            layout.label(text="Nenhum insert selecionado")
            return

        slot = track.inserts[track.active_insert_index]
        names = list_insert_preset_names(slot.effect_type)
        if not names:
            layout.label(text="Sem presets")
            return

        for name in names:
            op = layout.operator("daw.apply_mixer_insert_preset", text=name)
            op.track_index = mixer.active_track_index
            op.slot_index = track.active_insert_index
            op.preset_name = name


class DAW_MT_SetMixerTrackOutput(Menu):
    """Menu para rotear a saída da faixa ativa para um bus existente."""
    bl_idname = "DAW_MT_set_mixer_track_output"
    bl_label = "Saída"

    def draw(self, context):
        layout = self.layout
        mixer = context.scene.daw_mixer
        for name in bus_names(mixer.buses):
            op = layout.operator("daw.set_mixer_track_output", text=name)
            op.index = mixer.active_track_index
            op.bus_name = name


class DAW_MT_AddMixerSend(Menu):
    """Menu para adicionar um send da faixa ativa para um bus auxiliar."""
    bl_idname = "DAW_MT_add_mixer_send"
    bl_label = "Adicionar Send"

    def draw(self, context):
        layout = self.layout
        mixer = context.scene.daw_mixer
        track = mixer.active_track
        if track is None:
            return

        used = {s.bus_name for s in track.sends}
        available = [b for b in bus_names(mixer.buses) if b != MASTER_TRACK_NAME and b not in used]

        if not available:
            layout.label(text="Nenhum bus auxiliar disponível")
            return

        for name in available:
            op = layout.operator("daw.add_mixer_send", text=name)
            op.track_index = mixer.active_track_index
            op.bus_name = name


class DAW_MT_MixerStripPresets(Menu):
    """Menu com os presets de channel strip salvos."""
    bl_idname = "DAW_MT_mixer_strip_presets"
    bl_label = "Presets de Faixa"

    def draw(self, context):
        layout = self.layout
        mixer = context.scene.daw_mixer
        names = list_strip_preset_names()
        if not names:
            layout.label(text="Sem presets salvos")
            return
        for name in names:
            op = layout.operator("daw.apply_mixer_strip_preset", text=name)
            op.track_index = mixer.active_track_index
            op.preset_name = name


# ---------------------------------------------------------------------- #
# Painéis
# ---------------------------------------------------------------------- #
class DAW_PT_Mixer(Panel):
    bl_label = "Mixer"
    bl_idname = "DAW_PT_mixer"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 4

    def draw(self, context):
        layout = self.layout
        mixer = context.scene.daw_mixer

        row = layout.row()
        row.template_list(
            "DAW_UL_mixer_track_list", "",
            mixer, "tracks",
            mixer, "active_track_index",
            rows=5,
        )

        col = row.column(align=True)
        col.operator("daw.add_mixer_track", text="", icon='ADD')
        col.operator("daw.remove_mixer_track", text="", icon='REMOVE')
        col.separator()
        col.operator("daw.duplicate_mixer_track", text="", icon='DUPLICATE')
        col.separator()
        col.operator("daw.move_mixer_track", text="", icon='TRIA_UP').direction = "UP"
        col.operator("daw.move_mixer_track", text="", icon='TRIA_DOWN').direction = "DOWN"
        col.separator()
        col.operator("daw.clear_mixer", text="", icon='TRASH')

        track = mixer.active_track
        if track is None:
            return

        box = layout.box()
        row = box.row(align=True)
        row.prop(track, "volume")
        row.prop(track, "pan")

        row = box.row(align=True)
        row.prop(track, "mute", icon=_icon_for_mute(track.mute), toggle=True)
        row.prop(track, "solo", icon=_icon_for_solo(track.solo), toggle=True)
        row.operator("daw.reset_mixer_track", text="", icon='LOOP_BACK').index = mixer.active_track_index

        row = box.row(align=True)
        row.menu("DAW_MT_set_mixer_track_output", text=f"Saída: {track.output_bus}", icon='FORWARD')

        row = box.row(align=True)
        row.menu("DAW_MT_mixer_strip_presets", text="Presets", icon='PRESET')
        op = row.operator("daw.save_mixer_strip_preset", text="", icon='FILE_TICK')
        op.track_index = mixer.active_track_index


class DAW_PT_MixerBuses(Panel):
    bl_label = "Buses"
    bl_idname = "DAW_PT_mixer_buses"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_mixer"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        mixer = context.scene.daw_mixer

        row = layout.row()
        row.template_list(
            "DAW_UL_mixer_bus_list", "",
            mixer, "buses",
            mixer, "active_bus_index",
            rows=4,
        )

        col = row.column(align=True)
        col.operator("daw.add_mixer_bus", text="", icon='ADD')
        op = col.operator("daw.remove_mixer_bus", text="", icon='REMOVE')


class DAW_PT_MixerInserts(Panel):
    bl_label = "Inserts"
    bl_idname = "DAW_PT_mixer_inserts"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_mixer"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        mixer = context.scene.daw_mixer
        track = mixer.active_track

        if track is None:
            layout.label(text="Nenhuma faixa selecionada")
            return

        row = layout.row()
        row.template_list(
            "DAW_UL_mixer_insert_list", "",
            track, "inserts",
            track, "active_insert_index",
            rows=4,
        )

        col = row.column(align=True)
        col.menu("DAW_MT_add_mixer_insert", text="", icon='ADD')
        op = col.operator("daw.remove_mixer_insert", text="", icon='REMOVE')
        op.track_index = mixer.active_track_index
        col.separator()
        op = col.operator("daw.move_mixer_insert", text="", icon='TRIA_UP')
        op.track_index = mixer.active_track_index
        op.direction = "UP"
        op = col.operator("daw.move_mixer_insert", text="", icon='TRIA_DOWN')
        op.track_index = mixer.active_track_index
        op.direction = "DOWN"

        if not (0 <= track.active_insert_index < len(track.inserts)):
            return

        slot = track.inserts[track.active_insert_index]

        box = layout.box()
        row = box.row(align=True)
        row.prop(slot, "enabled")
        row.prop(slot, "bypass")

        row = box.row(align=True)
        row.menu("DAW_MT_mixer_insert_presets", text="Presets", icon='PRESET')
        op = row.operator("daw.save_mixer_insert_preset", text="", icon='FILE_TICK')
        op.track_index = mixer.active_track_index
        op = row.operator("daw.reset_mixer_insert", text="", icon='LOOP_BACK')
        op.track_index = mixer.active_track_index

        if len(slot.params) > 0:
            box.separator()
            for param in slot.params:
                row = box.row(align=True)
                row.label(text=param.name.replace("_", " ").title())
                row.prop(param, "value", text="")


class DAW_PT_MixerSends(Panel):
    bl_label = "Sends"
    bl_idname = "DAW_PT_mixer_sends"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_mixer"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        mixer = context.scene.daw_mixer
        track = mixer.active_track

        if track is None:
            layout.label(text="Nenhuma faixa selecionada")
            return

        row = layout.row()
        row.template_list(
            "DAW_UL_mixer_send_list", "",
            track, "sends",
            track, "active_send_index",
            rows=3,
        )

        col = row.column(align=True)
        col.menu("DAW_MT_add_mixer_send", text="", icon='ADD')
        op = col.operator("daw.remove_mixer_send", text="", icon='REMOVE')
        op.track_index = mixer.active_track_index


class DAW_PT_MixerMaster(Panel):
    bl_label = "Master"
    bl_idname = "DAW_PT_mixer_master"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_mixer"

    def draw(self, context):
        layout = self.layout
        mixer = context.scene.daw_mixer

        box = layout.box()
        box.prop(mixer, "master_volume")

        master = mixer.master
        if master is not None:
            row = box.row(align=True)
            row.label(
                text=f"Pico  L: {master.meter.peak_left:.2f}   R: {master.meter.peak_right:.2f}",
                icon='SEQ_HISTOGRAM',
            )
            if master.meter.clipping:
                row.label(text="", icon='ERROR')

        box = layout.box()
        box.label(text="Medidores", icon='SETTINGS')
        box.prop(mixer, "meters_enabled")
        row = box.row()
        row.enabled = mixer.meters_enabled
        row.prop(mixer, "meter_decay_speed")


classes = [
    DAW_UL_MixerTrackList,
    DAW_UL_MixerBusList,
    DAW_UL_MixerInsertList,
    DAW_UL_MixerSendList,
    DAW_MT_AddMixerInsert,
    DAW_MT_MixerInsertPresets,
    DAW_MT_SetMixerTrackOutput,
    DAW_MT_AddMixerSend,
    DAW_MT_MixerStripPresets,
    DAW_PT_Mixer,
    DAW_PT_MixerBuses,
    DAW_PT_MixerInserts,
    DAW_PT_MixerSends,
    DAW_PT_MixerMaster,
]