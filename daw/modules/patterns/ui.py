# modules/patterns/ui.py
"""
Painéis de UI do Blender para o módulo Patterns.

Segue o mesmo padrão do mixer:
    - bl_space_type = 'SEQUENCE_EDITOR'
    - bl_category   = "DAW"
"""
from __future__ import annotations

import bpy
from bpy.types import Menu, Panel, UIList

from .utils import midi_note_name


# ---------------------------------------------------------------------- #
# Listas
# ---------------------------------------------------------------------- #
class DAW_UL_PatternList(UIList):
    """Lista de patterns."""
    bl_idname = "DAW_UL_pattern_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        pattern = item
        row = layout.row(align=True)

        sub = row.row()
        sub.scale_x = 0.35
        sub.prop(pattern, "color", text="")

        row.prop(pattern, "name", text="", emboss=False)
        row.label(text=f"{pattern.note_count} notas", icon='SEQ_STRIP_DUPLICATE')


class DAW_UL_PatternNoteList(UIList):
    """Lista de notas do pattern ativo."""
    bl_idname = "DAW_UL_pattern_note_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        note = item
        row = layout.row(align=True)

        row.prop(note, "enabled", text="", icon='CHECKBOX_HLT' if note.enabled else 'CHECKBOX_DEHLT', emboss=False)
        row.label(text=midi_note_name(note.pitch), icon='IPO_CONSTANT')
        row.label(text=f"S{note.start_step}")
        row.prop(note, "velocity", text="")


class DAW_UL_PatternClipList(UIList):
    """Lista de clips na timeline."""
    bl_idname = "DAW_UL_pattern_clip_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        clip = item
        row = layout.row(align=True)

        row.prop(clip, "enabled", text="", icon='CHECKBOX_HLT' if clip.enabled else 'CHECKBOX_DEHLT', emboss=False)
        row.label(text=clip.pattern_name, icon='SEQ_STRIP_DUPLICATE')
        row.label(text=f"T{clip.track_index}")
        row.label(text=f"@{clip.start_beat:.1f}")


class DAW_UL_PatternGroupList(UIList):
    """Lista de grupos de patterns."""
    bl_idname = "DAW_UL_pattern_group_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        group = item
        row = layout.row(align=True)

        sub = row.row()
        sub.scale_x = 0.35
        sub.prop(group, "color", text="")

        row.prop(group, "name", text="", emboss=False)
        names = group.pattern_names
        row.label(text=f"{len(names)} patterns", icon='OUTLINER_COLLECTION')


# ---------------------------------------------------------------------- #
# Menus
# ---------------------------------------------------------------------- #
class DAW_MT_AddPatternClip(Menu):
    """Menu para adicionar um clip do pattern ativo na timeline."""
    bl_idname = "DAW_MT_add_pattern_clip"
    bl_label = "Adicionar Clip"

    def draw(self, context):
        layout = self.layout
        patterns = context.scene.daw_patterns
        pattern = patterns.active_pattern
        if pattern is None:
            layout.label(text="Nenhum pattern selecionado")
            return

        op = layout.operator("daw.add_pattern_clip", text=f"Clip de '{pattern.name}'")
        op.pattern_name = pattern.name
        op.track_index = 0
        op.start_beat = 0.0
        op.duration_beats = 4.0


class DAW_MT_PatternClipOptions(Menu):
    """Menu de opções para o clip selecionado."""
    bl_idname = "DAW_MT_pattern_clip_options"
    bl_label = "Opções do Clip"

    def draw(self, context):
        layout = self.layout
        patterns = context.scene.daw_patterns
        clip = patterns.active_clip
        if clip is None:
            layout.label(text="Nenhum clip selecionado")
            return

        layout.prop(clip, "track_index")
        layout.prop(clip, "start_beat")
        layout.prop(clip, "duration_beats")
        layout.prop(clip, "offset_beats")
        layout.separator()
        layout.prop(clip, "use_color_override")
        if clip.use_color_override:
            layout.prop(clip, "color_override")


# ---------------------------------------------------------------------- #
# Painéis
# ---------------------------------------------------------------------- #
class DAW_PT_Patterns(Panel):
    bl_label = "Patterns"
    bl_idname = "DAW_PT_patterns"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 5

    def draw(self, context):
        layout = self.layout
        patterns = context.scene.daw_patterns

        row = layout.row()
        row.template_list(
            "DAW_UL_pattern_list", "",
            patterns, "patterns",
            patterns, "active_pattern_index",
            rows=5,
        )

        col = row.column(align=True)
        col.operator("daw.add_pattern", text="", icon='ADD')
        col.operator("daw.remove_pattern", text="", icon='REMOVE')
        col.separator()
        col.operator("daw.duplicate_pattern", text="", icon='DUPLICATE')
        col.separator()
        col.operator("daw.clear_pattern_notes", text="", icon='TRASH')

        pattern = patterns.active_pattern
        if pattern is None:
            return

        box = layout.box()
        box.prop(pattern, "length_steps")
        row = box.row(align=True)
        row.prop(pattern, "bpm")
        row.prop(pattern, "time_signature_num")
        row.prop(pattern, "time_signature_den")
        box.prop(pattern, "swing")
        box.prop(pattern, "is_looping")


class DAW_PT_PatternNotes(Panel):
    bl_label = "Notas"
    bl_idname = "DAW_PT_pattern_notes"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_patterns"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        patterns = context.scene.daw_patterns
        pattern = patterns.active_pattern

        if pattern is None:
            layout.label(text="Nenhum pattern selecionado")
            return

        row = layout.row()
        row.template_list(
            "DAW_UL_pattern_note_list", "",
            pattern, "notes",
            pattern, "active_note_index",
            rows=4,
        )

        col = row.column(align=True)
        col.operator("daw.add_pattern_note", text="", icon='ADD')
        op = col.operator("daw.remove_pattern_note", text="", icon='REMOVE')
        op.pattern_index = patterns.active_pattern_index

        if not (0 <= pattern.active_note_index < len(pattern.notes)):
            return

        note = pattern.notes[pattern.active_note_index]
        box = layout.box()
        box.prop(note, "pitch")
        box.prop(note, "velocity")
        box.prop(note, "start_step")
        box.prop(note, "duration_steps")


class DAW_PT_PatternClips(Panel):
    bl_label = "Timeline (Clips)"
    bl_idname = "DAW_PT_pattern_clips"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_patterns"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        patterns = context.scene.daw_patterns

        row = layout.row()
        row.template_list(
            "DAW_UL_pattern_clip_list", "",
            patterns, "clips",
            patterns, "active_clip_index",
            rows=4,
        )

        col = row.column(align=True)
        col.menu("DAW_MT_add_pattern_clip", text="", icon='ADD')
        col.operator("daw.remove_pattern_clip", text="", icon='REMOVE')
        col.separator()
        col.menu("DAW_MT_pattern_clip_options", text="", icon='SETTINGS')
        col.separator()
        col.operator("daw.clear_pattern_clips", text="", icon='TRASH')

        clip = patterns.active_clip
        if clip is None:
            return

        box = layout.box()
        box.prop(clip, "track_index")
        box.prop(clip, "start_beat")
        box.prop(clip, "duration_beats")
        box.prop(clip, "offset_beats")
        box.prop(clip, "use_color_override")
        if clip.use_color_override:
            box.prop(clip, "color_override")


class DAW_PT_PatternGroups(Panel):
    bl_label = "Grupos"
    bl_idname = "DAW_PT_pattern_groups"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_patterns"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        patterns = context.scene.daw_patterns

        row = layout.row()
        row.template_list(
            "DAW_UL_pattern_group_list", "",
            patterns, "groups",
            patterns, "active_group_index",
            rows=4,
        )

        col = row.column(align=True)
        col.operator("daw.add_pattern_group", text="", icon='ADD')
        col.operator("daw.remove_pattern_group", text="", icon='REMOVE')

        group = patterns.active_group
        if group is None:
            return

        box = layout.box()
        box.label(text="Patterns no grupo:")
        for name in group.pattern_names:
            row = box.row(align=True)
            row.label(text=name, icon='SEQ_STRIP_DUPLICATE')
            op = row.operator("daw.remove_pattern_from_group", text="", icon='X')
            op.group_index = patterns.active_group_index
            op.pattern_name = name

        # Adicionar pattern atual ao grupo
        if patterns.active_pattern is not None:
            row = box.row()
            op = row.operator("daw.add_pattern_to_group", text="Adicionar Pattern Ativo", icon='ADD')
            op.group_index = patterns.active_group_index


class DAW_PT_PatternSettings(Panel):
    bl_label = "Configurações"
    bl_idname = "DAW_PT_pattern_settings"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_patterns"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        patterns = context.scene.daw_patterns

        box = layout.box()
        box.label(text="Editor", icon='SETTINGS')
        box.prop(patterns, "grid_step_division")
        box.prop(patterns, "piano_roll_zoom")


classes = [
    DAW_UL_PatternList,
    DAW_UL_PatternNoteList,
    DAW_UL_PatternClipList,
    DAW_UL_PatternGroupList,
    DAW_MT_AddPatternClip,
    DAW_MT_PatternClipOptions,
    DAW_PT_Patterns,
    DAW_PT_PatternNotes,
    DAW_PT_PatternClips,
    DAW_PT_PatternGroups,
    DAW_PT_PatternSettings,
]