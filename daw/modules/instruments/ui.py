# modules/instruments/ui.py
"""
Painéis de UI do Blender para o módulo de Instrumentos.

Segue o mesmo padrão dos outros painéis do projeto:
    - bl_space_type = 'SEQUENCE_EDITOR' (onde a DAW vive)
    - bl_category   = "DAW"
"""
from __future__ import annotations

import bpy
from bpy.types import Panel, UIList, Menu

from . import synth
from .presets import list_all_preset_names


class DAW_UL_InstrumentList(UIList):
    """Lista de instrumentos do rack (nome, timbre, mute/solo)."""
    bl_idname = "DAW_UL_instrument_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        inst = item
        row = layout.row(align=True)

        row.label(text="", icon='SPEAKER')
        row.prop(inst, "name", text="", emboss=False)

        timbre_name = dict(
            (str(iid), d["name"]) for iid, d in synth.INSTRUMENTS.items()
        ).get(inst.instrument_id, "?")
        row.label(text=timbre_name)

        row.prop(inst, "mute", text="", icon='HIDE_ON' if inst.mute else 'HIDE_OFF', emboss=False)
        row.prop(inst, "solo", text="", icon='SOLO_ON' if inst.solo else 'SOLO_OFF', emboss=False)


class DAW_MT_InstrumentPresets(Menu):
    """Menu com os presets de instrumento disponíveis (embutidos + do usuário)."""
    bl_idname = "DAW_MT_instrument_presets"
    bl_label = "Presets"

    def draw(self, context):
        layout = self.layout
        rack = context.scene.daw_instruments
        names = list_all_preset_names()

        if not names:
            layout.label(text="Sem presets")
            return

        for name in names:
            op = layout.operator("daw.apply_instrument_preset", text=name)
            op.index = rack.active_instrument_index
            op.preset_name = name


class DAW_PT_Instruments(Panel):
    bl_label = "Instrumentos"
    bl_idname = "DAW_PT_instruments"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        rack = context.scene.daw_instruments

        row = layout.row()
        row.template_list(
            "DAW_UL_instrument_list", "",
            rack, "instruments",
            rack, "active_instrument_index",
            rows=5,
        )

        col = row.column(align=True)
        col.operator("daw.add_instrument", text="", icon='ADD')
        col.operator("daw.remove_instrument", text="", icon='REMOVE')
        col.separator()
        col.operator("daw.duplicate_instrument", text="", icon='DUPLICATE')
        col.separator()
        col.operator("daw.move_instrument", text="", icon='TRIA_UP').direction = "UP"
        col.operator("daw.move_instrument", text="", icon='TRIA_DOWN').direction = "DOWN"

        inst = None
        if 0 <= rack.active_instrument_index < len(rack.instruments):
            inst = rack.instruments[rack.active_instrument_index]

        if inst is None:
            return

        box = layout.box()
        row = box.row(align=True)
        row.menu("DAW_MT_instrument_presets", text="Presets", icon='PRESET')
        op = row.operator("daw.save_instrument_preset", text="", icon='FILE_TICK')
        op.index = rack.active_instrument_index

        box.prop(inst, "instrument_id")

        row = box.row(align=True)
        row.prop(inst, "volume")
        row.prop(inst, "pan")

        row = box.row(align=True)
        row.prop(inst, "octave_shift")
        row.prop(inst, "pitch_bend_range")

        row = box.row(align=True)
        row.prop(inst, "mono")
        sub = row.row()
        sub.enabled = not inst.mono
        sub.prop(inst, "polyphony")

        row = box.row(align=True)
        op = row.operator("daw.preview_instrument_note", text="Tocar C4", icon='PLAY')
        op.index = rack.active_instrument_index
        op.pitch = 60

        row2 = box.row(align=True)
        row2.prop(rack, "preview_velocity")
        row2.prop(rack, "preview_duration")


class DAW_PT_ChordProgressions(Panel):
    bl_label = "Progressões de Acordes"
    bl_idname = "DAW_PT_chord_progressions"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_instruments"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        rack = context.scene.daw_instruments

        layout.prop(rack, "selected_progression", text="")

        prog = synth.get_progression(rack.selected_progression)
        if prog:
            info = layout.box()
            info.label(text=prog.get("description", ""), icon='INFO')
            row = info.row(align=True)
            row.label(text=f"BPM: {prog.get('bpm', '?')}")
            row.label(text=f"Acordes: {len(prog.get('chords', []))}")

            chord_names = ", ".join(c["name"] for c in prog.get("chords", []))
            info.label(text=chord_names)

        layout.prop(rack, "insert_at_playhead")

        row = layout.row(align=True)
        row.operator("daw.preview_chord_progression", text="Tocar", icon='PLAY')
        row.operator("daw.insert_chord_progression", text="Inserir no Piano Roll", icon='IMPORT')


classes = [
    DAW_UL_InstrumentList,
    DAW_MT_InstrumentPresets,
    DAW_PT_Instruments,
    DAW_PT_ChordProgressions,
]