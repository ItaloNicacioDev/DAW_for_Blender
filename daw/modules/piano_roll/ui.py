# modules/piano_roll/ui.py
"""
Painéis de UI do Blender para o módulo Piano Roll.

Segue o padrão:
    - bl_space_type = 'SEQUENCE_EDITOR'
    - bl_category   = "DAW"
"""
from __future__ import annotations

import bpy
from bpy.types import Menu, Panel, UIList

from .scales import SCALE_ITEMS, get_note_name
from .chords import CHORD_ITEMS
from .snap import SNAP_ITEMS


# ---------------------------------------------------------------------- #
# Lista de notas
# ---------------------------------------------------------------------- #
class DAW_UL_PianoRollNoteList(UIList):
    """Lista de notas do piano roll."""
    bl_idname = "DAW_UL_piano_roll_note_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        note = item
        row = layout.row(align=True)

        row.prop(note, "selected", text="", icon='CHECKBOX_HLT' if note.selected else 'CHECKBOX_DEHLT', emboss=False)
        row.label(text=get_note_name(note.pitch), icon='IPO_CONSTANT')
        row.label(text=f"@{note.start_beat:.2f}")
        row.prop(note, "velocity", text="")
        row.prop(note, "duration_beats", text="")


# ---------------------------------------------------------------------- #
# Menus
# ---------------------------------------------------------------------- #
class DAW_MT_PRInsertChord(Menu):
    """Menu para inserir acordes."""
    bl_idname = "DAW_MT_pr_insert_chord"
    bl_label = "Inserir Acorde"

    def draw(self, context):
        layout = self.layout
        pr = context.scene.daw_piano_roll
        for identifier, label, _desc in CHORD_ITEMS:
            op = layout.operator("daw.pr_insert_chord", text=label)
            op.chord_name = identifier
            op.root_pitch = 60
            op.start_beat = 0.0


class DAW_MT_PRGenerateArpeggio(Menu):
    """Menu para gerar arpejos."""
    bl_idname = "DAW_MT_pr_generate_arpeggio"
    bl_label = "Gerar Arpejo"

    def draw(self, context):
        layout = self.layout
        from .arpeggiator import ARPEGGIO_ITEMS
        for identifier, label, _desc in ARPEGGIO_ITEMS:
            op = layout.operator("daw.pr_generate_arpeggio", text=label)
            op.pattern = identifier
            op.chord_name = "MAJOR"
            op.root_pitch = 60


# ---------------------------------------------------------------------- #
# Painéis
# ---------------------------------------------------------------------- #
class DAW_PT_PianoRoll(Panel):
    bl_label = "Piano Roll"
    bl_idname = "DAW_PT_piano_roll"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 6

    def draw(self, context):
        layout = self.layout
        pr = context.scene.daw_piano_roll
        settings = pr.settings

        # Pattern sendo editado
        box = layout.box()
        box.label(text="Editando:", icon='SEQ_STRIP_DUPLICATE')
        box.prop(pr, "edited_pattern_name", text="")

        # Lista de notas
        row = layout.row()
        row.template_list(
            "DAW_UL_piano_roll_note_list", "",
            pr, "notes",
            pr, "active_note_index",
            rows=5,
        )

        col = row.column(align=True)
        col.operator("daw.pr_add_note", text="", icon='ADD')
        col.operator("daw.pr_remove_note", text="", icon='REMOVE')
        col.separator()
        col.operator("daw.pr_duplicate_note", text="", icon='DUPLICATE')
        col.separator()
        col.operator("daw.pr_clear_notes", text="", icon='TRASH')

        # Seleção
        box = layout.box()
        box.label(text="Seleção", icon='RESTRICT_SELECT_OFF')
        row = box.row(align=True)
        row.operator("daw.pr_select_all", text="Tudo")
        row.operator("daw.pr_deselect_all", text="Nada")
        row.operator("daw.pr_invert_selection", text="Inverter")
        row = box.row(align=True)
        row.operator("daw.pr_delete_selected", text="Excluir Selecionadas", icon='X')


class DAW_PT_PianoRollEdit(Panel):
    bl_label = "Edição"
    bl_idname = "DAW_PT_piano_roll_edit"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_piano_roll"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        pr = context.scene.daw_piano_roll
        note = pr.active_note

        if note is not None:
            box = layout.box()
            box.label(text=f"Nota: {get_note_name(note.pitch)}")
            box.prop(note, "pitch")
            box.prop(note, "start_beat")
            box.prop(note, "duration_beats")
            box.prop(note, "velocity")
            box.prop(note, "muted")

        # Transposição
        box = layout.box()
        box.label(text="Transpor", icon='ARROW_LEFTRIGHT')
        row = box.row(align=True)
        op = row.operator("daw.pr_transpose_selected", text="-12")
        op.semitones = -12
        op = row.operator("daw.pr_transpose_selected", text="-1")
        op.semitones = -1
        op = row.operator("daw.pr_transpose_selected", text="+1")
        op.semitones = 1
        op = row.operator("daw.pr_transpose_selected", text="+12")
        op.semitones = 12

        # Velocity
        box = layout.box()
        box.label(text="Velocity", icon='FORCE_FORCE')
        row = box.row(align=True)
        for vel in [0.25, 0.5, 0.75, 1.0]:
            op = row.operator("daw.pr_set_velocity_selected", text=f"{int(vel*100)}%")
            op.velocity = vel


class DAW_PT_PianoRollSnap(Panel):
    bl_label = "Snap & Escala"
    bl_idname = "DAW_PT_piano_roll_snap"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_piano_roll"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_piano_roll.settings

        box = layout.box()
        box.label(text="Snap", icon='SNAP_GRID')
        box.prop(settings, "snap_enabled")
        row = box.row()
        row.enabled = settings.snap_enabled
        row.prop(settings, "snap_division")

        box = layout.box()
        box.label(text="Escala", icon='MODIFIER')
        box.prop(settings, "scale_enabled")
        row = box.row()
        row.enabled = settings.scale_enabled
        row.prop(settings, "scale_root")
        row.prop(settings, "scale_name")
        box.prop(settings, "scale_highlight")


class DAW_PT_PianoRollTools(Panel):
    bl_label = "Ferramentas"
    bl_idname = "DAW_PT_piano_roll_tools"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_piano_roll"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        pr = context.scene.daw_piano_roll
        settings = pr.settings

        # Quantize
        box = layout.box()
        box.label(text="Quantizar", icon='GRID')
        box.prop(settings, "quantize_strength")
        box.prop(settings, "quantize_grid")
        op = box.operator("daw.pr_quantize_selected", text="Quantizar Selecionadas")
        op.strength = settings.quantize_strength
        # Mapeia nome de snap para valor
        from .snap import get_division_value
        op.grid_division = get_division_value(settings.quantize_grid)

        # Humanize
        box = layout.box()
        box.label(text="Humanizar", icon='MOD_WAVE')
        box.prop(settings, "humanize_timing")
        box.prop(settings, "humanize_velocity")
        op = box.operator("daw.pr_humanize_selected", text="Humanizar Selecionadas")
        op.timing = settings.humanize_timing
        op.velocity = settings.humanize_velocity

        # Acordes
        box = layout.box()
        box.label(text="Acordes", icon='IPO_ELASTIC')
        box.menu("DAW_MT_pr_insert_chord", text="Inserir Acorde")

        # Arpeggiator
        box = layout.box()
        box.label(text="Arpeggiator", icon='MOD_ARRAY')
        box.menu("DAW_MT_pr_generate_arpeggio", text="Gerar Arpejo")


class DAW_PT_PianoRollView(Panel):
    bl_label = "Visualização"
    bl_idname = "DAW_PT_piano_roll_view"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_piano_roll"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_piano_roll.settings

        box = layout.box()
        box.label(text="Zoom & Scroll", icon='VIEWZOOM')
        box.prop(settings, "zoom_x")
        box.prop(settings, "zoom_y")
        box.prop(settings, "scroll_x")
        box.prop(settings, "scroll_y")

        box = layout.box()
        box.label(text="Opções", icon='SETTINGS')
        box.prop(settings, "follow_playhead")
        box.prop(settings, "show_ghost_notes")


classes = [
    DAW_UL_PianoRollNoteList,
    DAW_MT_PRInsertChord,
    DAW_MT_PRGenerateArpeggio,
    DAW_PT_PianoRoll,
    DAW_PT_PianoRollEdit,
    DAW_PT_PianoRollSnap,
    DAW_PT_PianoRollTools,
    DAW_PT_PianoRollView,
]