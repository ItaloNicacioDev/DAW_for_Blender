# modules/patterns/operators.py
"""
Operators do Blender para o módulo Patterns.

Responsabilidade:
    Ações de edição disparadas pela UI: gerenciar patterns, notas,
    clips na timeline e grupos.
"""
from __future__ import annotations

import bpy
from bpy.props import FloatProperty, IntProperty, StringProperty
from bpy.types import Operator

from .colors import get_color_by_index
from .utils import clamp_index, unique_pattern_name, unique_group_name, midi_note_name


def _patterns(context):
    return context.scene.daw_patterns


def _pattern_for(context, index: int = -1):
    patterns = _patterns(context)
    i = index if index >= 0 else patterns.active_pattern_index
    if not (0 <= i < len(patterns.patterns)):
        return None
    return patterns.patterns[i]


def _clip_for(context, index: int = -1):
    patterns = _patterns(context)
    i = index if index >= 0 else patterns.active_clip_index
    if not (0 <= i < len(patterns.clips)):
        return None
    return patterns.clips[i]


def _group_for(context, index: int = -1):
    patterns = _patterns(context)
    i = index if index >= 0 else patterns.active_group_index
    if not (0 <= i < len(patterns.groups)):
        return None
    return patterns.groups[i]


# ---------------------------------------------------------------------- #
# Patterns
# ---------------------------------------------------------------------- #
class DAW_OT_AddPattern(Operator):
    bl_idname = "daw.add_pattern"
    bl_label = "Adicionar Pattern"
    bl_description = "Adiciona um novo pattern vazio"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="Novo Pattern")
    length_steps: IntProperty(default=16, min=1, max=256)

    def execute(self, context):
        patterns = _patterns(context)
        pattern = patterns.patterns.add()
        pattern.name = unique_pattern_name(patterns, self.name)
        pattern.color = get_color_by_index(len(patterns.patterns) - 1)
        pattern.length_steps = self.length_steps
        patterns.active_pattern_index = len(patterns.patterns) - 1
        self.report({'INFO'}, f"Pattern '{pattern.name}' adicionado")
        return {'FINISHED'}


class DAW_OT_RemovePattern(Operator):
    bl_idname = "daw.remove_pattern"
    bl_label = "Remover Pattern"
    bl_description = "Remove o pattern selecionado"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        patterns = _patterns(context)
        index = self.index if self.index >= 0 else patterns.active_pattern_index
        if not (0 <= index < len(patterns.patterns)):
            self.report({'WARNING'}, "Nenhum pattern para remover")
            return {'CANCELLED'}

        name = patterns.patterns[index].name
        patterns.patterns.remove(index)
        patterns.active_pattern_index = clamp_index(patterns.active_pattern_index, len(patterns.patterns))

        # Remove clips que referenciavam este pattern
        for i in reversed(range(len(patterns.clips))):
            if patterns.clips[i].pattern_name == name:
                patterns.clips.remove(i)
        patterns.active_clip_index = clamp_index(patterns.active_clip_index, len(patterns.clips))

        self.report({'INFO'}, f"Pattern '{name}' removido")
        return {'FINISHED'}


class DAW_OT_DuplicatePattern(Operator):
    bl_idname = "daw.duplicate_pattern"
    bl_label = "Duplicar Pattern"
    bl_description = "Duplica o pattern selecionado (notas e configurações)"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        patterns = _patterns(context)
        index = self.index if self.index >= 0 else patterns.active_pattern_index
        if not (0 <= index < len(patterns.patterns)):
            return {'CANCELLED'}

        src = patterns.patterns[index]
        new = patterns.patterns.add()
        new.name = unique_pattern_name(patterns, f"{src.name} (cópia)")
        new.color = tuple(src.color)
        new.length_steps = src.length_steps
        new.bpm = src.bpm
        new.time_signature_num = src.time_signature_num
        new.time_signature_den = src.time_signature_den
        new.is_looping = src.is_looping
        new.swing = src.swing

        for note in src.notes:
            n = new.notes.add()
            n.pitch = note.pitch
            n.velocity = note.velocity
            n.start_step = note.start_step
            n.duration_steps = note.duration_steps
            n.enabled = note.enabled

        patterns.patterns.move(len(patterns.patterns) - 1, index + 1)
        patterns.active_pattern_index = index + 1
        self.report({'INFO'}, f"Pattern '{new.name}' criado")
        return {'FINISHED'}


class DAW_OT_ClearPatternNotes(Operator):
    bl_idname = "daw.clear_pattern_notes"
    bl_label = "Limpar Notas"
    bl_description = "Remove todas as notas do pattern selecionado"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        pattern = _pattern_for(context, self.index)
        if pattern is None:
            return {'CANCELLED'}
        pattern.notes.clear()
        pattern.active_note_index = 0
        self.report({'INFO'}, f"Notas de '{pattern.name}' limpas")
        return {'FINISHED'}


class DAW_OT_ResizePattern(Operator):
    bl_idname = "daw.resize_pattern"
    bl_label = "Redimensionar Pattern"
    bl_description = "Altera o número de steps do pattern"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)
    length_steps: IntProperty(default=16, min=1, max=256)

    def execute(self, context):
        pattern = _pattern_for(context, self.index)
        if pattern is None:
            return {'CANCELLED'}
        pattern.length_steps = self.length_steps
        # Remove notas fora do novo range
        for i in reversed(range(len(pattern.notes))):
            if pattern.notes[i].start_step >= self.length_steps:
                pattern.notes.remove(i)
        pattern.active_note_index = clamp_index(pattern.active_note_index, len(pattern.notes))
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Notas
# ---------------------------------------------------------------------- #
class DAW_OT_AddPatternNote(Operator):
    bl_idname = "daw.add_pattern_note"
    bl_label = "Adicionar Nota"
    bl_description = "Adiciona uma nota ao pattern ativo"
    bl_options = {'REGISTER', 'UNDO'}

    pattern_index: IntProperty(default=-1)
    pitch: IntProperty(default=60, min=0, max=127)
    velocity: FloatProperty(default=0.8, min=0.0, max=1.0)
    start_step: IntProperty(default=0, min=0)
    duration_steps: IntProperty(default=1, min=1)

    def execute(self, context):
        pattern = _pattern_for(context, self.pattern_index)
        if pattern is None:
            return {'CANCELLED'}
        if self.start_step >= pattern.length_steps:
            self.report({'WARNING'}, "Step fora do range do pattern")
            return {'CANCELLED'}

        note = pattern.notes.add()
        note.pitch = self.pitch
        note.velocity = self.velocity
        note.start_step = self.start_step
        note.duration_steps = self.duration_steps
        pattern.active_note_index = len(pattern.notes) - 1
        self.report({'INFO'}, f"Nota {midi_note_name(self.pitch)} adicionada")
        return {'FINISHED'}


class DAW_OT_RemovePatternNote(Operator):
    bl_idname = "daw.remove_pattern_note"
    bl_label = "Remover Nota"
    bl_description = "Remove a nota selecionada do pattern"
    bl_options = {'REGISTER', 'UNDO'}

    pattern_index: IntProperty(default=-1)
    note_index: IntProperty(default=-1)

    def execute(self, context):
        pattern = _pattern_for(context, self.pattern_index)
        if pattern is None:
            return {'CANCELLED'}
        index = self.note_index if self.note_index >= 0 else pattern.active_note_index
        if not (0 <= index < len(pattern.notes)):
            return {'CANCELLED'}

        pattern.notes.remove(index)
        pattern.active_note_index = clamp_index(pattern.active_note_index, len(pattern.notes))
        return {'FINISHED'}


class DAW_OT_TogglePatternNote(Operator):
    """Toggle rápido de nota em um step (útil para step sequencer)."""
    bl_idname = "daw.toggle_pattern_note"
    bl_label = "Toggle Nota"
    bl_description = "Adiciona ou remove uma nota no step informado"
    bl_options = {'REGISTER', 'UNDO'}

    pattern_index: IntProperty(default=-1)
    step: IntProperty(default=0, min=0)
    pitch: IntProperty(default=60, min=0, max=127)

    def execute(self, context):
        pattern = _pattern_for(context, self.pattern_index)
        if pattern is None:
            return {'CANCELLED'}

        # Procura nota existente no mesmo step/pitch
        for i, note in enumerate(pattern.notes):
            if note.start_step == self.step and note.pitch == self.pitch:
                pattern.notes.remove(i)
                return {'FINISHED'}

        # Adiciona nova nota
        note = pattern.notes.add()
        note.pitch = self.pitch
        note.start_step = self.step
        note.duration_steps = 1
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Clips
# ---------------------------------------------------------------------- #
class DAW_OT_AddPatternClip(Operator):
    bl_idname = "daw.add_pattern_clip"
    bl_label = "Adicionar Clip"
    bl_description = "Adiciona um clip do pattern selecionado na timeline"
    bl_options = {'REGISTER', 'UNDO'}

    pattern_name: StringProperty(default="")
    track_index: IntProperty(default=0, min=0)
    start_beat: FloatProperty(default=0.0, min=0.0)
    duration_beats: FloatProperty(default=4.0, min=0.25)

    def execute(self, context):
        patterns = _patterns(context)
        if not self.pattern_name:
            pattern = patterns.active_pattern
            if pattern is None:
                self.report({'WARNING'}, "Nenhum pattern selecionado")
                return {'CANCELLED'}
            self.pattern_name = pattern.name

        if patterns.get_pattern_by_name(self.pattern_name) is None:
            self.report({'ERROR'}, f"Pattern '{self.pattern_name}' não existe")
            return {'CANCELLED'}

        clip = patterns.clips.add()
        clip.pattern_name = self.pattern_name
        clip.track_index = self.track_index
        clip.start_beat = self.start_beat
        clip.duration_beats = self.duration_beats
        patterns.active_clip_index = len(patterns.clips) - 1
        self.report({'INFO'}, f"Clip de '{clip.pattern_name}' adicionado")
        return {'FINISHED'}


class DAW_OT_RemovePatternClip(Operator):
    bl_idname = "daw.remove_pattern_clip"
    bl_label = "Remover Clip"
    bl_description = "Remove o clip selecionado da timeline"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        patterns = _patterns(context)
        index = self.index if self.index >= 0 else patterns.active_clip_index
        if not (0 <= index < len(patterns.clips)):
            return {'CANCELLED'}

        patterns.clips.remove(index)
        patterns.active_clip_index = clamp_index(patterns.active_clip_index, len(patterns.clips))
        return {'FINISHED'}


class DAW_OT_MovePatternClip(Operator):
    bl_idname = "daw.move_pattern_clip"
    bl_label = "Mover Clip"
    bl_description = "Move o clip para uma nova posição na timeline"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)
    new_start_beat: FloatProperty(default=0.0, min=0.0)

    def execute(self, context):
        clip = _clip_for(context, self.index)
        if clip is None:
            return {'CANCELLED'}
        clip.start_beat = self.new_start_beat
        return {'FINISHED'}


class DAW_OT_ResizePatternClip(Operator):
    bl_idname = "daw.resize_pattern_clip"
    bl_label = "Redimensionar Clip"
    bl_description = "Altera a duração do clip"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)
    new_duration: FloatProperty(default=4.0, min=0.25)

    def execute(self, context):
        clip = _clip_for(context, self.index)
        if clip is None:
            return {'CANCELLED'}
        clip.duration_beats = self.new_duration
        return {'FINISHED'}


class DAW_OT_SplitPatternClip(Operator):
    bl_idname = "daw.split_pattern_clip"
    bl_label = "Dividir Clip"
    bl_description = "Divide o clip em dois no beat informado"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)
    at_beat: FloatProperty(default=0.0, min=0.0)

    def execute(self, context):
        patterns = _patterns(context)
        clip = _clip_for(context, self.index)
        if clip is None:
            return {'CANCELLED'}

        end_beat = clip.start_beat + clip.duration_beats
        if self.at_beat <= clip.start_beat or self.at_beat >= end_beat:
            self.report({'WARNING'}, "Ponto de divisão fora do clip")
            return {'CANCELLED'}

        first_duration = self.at_beat - clip.start_beat
        second_offset = clip.offset_beats + first_duration
        second_duration = end_beat - self.at_beat

        # Ajusta o clip original (primeira metade)
        clip.duration_beats = first_duration

        # Cria o novo clip (segunda metade)
        new_clip = patterns.clips.add()
        new_clip.pattern_name = clip.pattern_name
        new_clip.track_index = clip.track_index
        new_clip.start_beat = self.at_beat
        new_clip.duration_beats = second_duration
        new_clip.offset_beats = second_offset
        new_clip.enabled = clip.enabled
        new_clip.use_color_override = clip.use_color_override
        new_clip.color_override = tuple(clip.color_override)

        patterns.active_clip_index = len(patterns.clips) - 1
        self.report({'INFO'}, "Clip dividido")
        return {'FINISHED'}


class DAW_OT_ClearPatternClips(Operator):
    bl_idname = "daw.clear_pattern_clips"
    bl_label = "Limpar Clips"
    bl_description = "Remove todos os clips da timeline"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        patterns = _patterns(context)
        patterns.clips.clear()
        patterns.active_clip_index = 0
        self.report({'INFO'}, "Todos os clips removidos")
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Grupos
# ---------------------------------------------------------------------- #
class DAW_OT_AddPatternGroup(Operator):
    bl_idname = "daw.add_pattern_group"
    bl_label = "Adicionar Grupo"
    bl_description = "Cria um novo grupo de patterns"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="Novo Grupo")

    def execute(self, context):
        patterns = _patterns(context)
        group = patterns.groups.add()
        group.name = unique_group_name(patterns, self.name)
        group.color = get_color_by_index(len(patterns.groups) - 1)
        patterns.active_group_index = len(patterns.groups) - 1
        self.report({'INFO'}, f"Grupo '{group.name}' criado")
        return {'FINISHED'}


class DAW_OT_RemovePatternGroup(Operator):
    bl_idname = "daw.remove_pattern_group"
    bl_label = "Remover Grupo"
    bl_description = "Remove o grupo selecionado"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        patterns = _patterns(context)
        index = self.index if self.index >= 0 else patterns.active_group_index
        if not (0 <= index < len(patterns.groups)):
            return {'CANCELLED'}

        patterns.groups.remove(index)
        patterns.active_group_index = clamp_index(patterns.active_group_index, len(patterns.groups))
        return {'FINISHED'}


class DAW_OT_AddPatternToGroup(Operator):
    bl_idname = "daw.add_pattern_to_group"
    bl_label = "Adicionar ao Grupo"
    bl_description = "Adiciona o pattern ativo ao grupo selecionado"
    bl_options = {'REGISTER', 'UNDO'}

    group_index: IntProperty(default=-1)
    pattern_name: StringProperty(default="")

    def execute(self, context):
        patterns = _patterns(context)
        group = _group_for(context, self.group_index)
        if group is None:
            return {'CANCELLED'}

        name = self.pattern_name
        if not name:
            pattern = patterns.active_pattern
            if pattern is None:
                return {'CANCELLED'}
            name = pattern.name

        group.add_pattern_name(name)
        return {'FINISHED'}


class DAW_OT_RemovePatternFromGroup(Operator):
    bl_idname = "daw.remove_pattern_from_group"
    bl_label = "Remover do Grupo"
    bl_description = "Remove um pattern do grupo selecionado"
    bl_options = {'REGISTER', 'UNDO'}

    group_index: IntProperty(default=-1)
    pattern_name: StringProperty(default="")

    def execute(self, context):
        group = _group_for(context, self.group_index)
        if group is None or not self.pattern_name:
            return {'CANCELLED'}
        group.remove_pattern_name(self.pattern_name)
        return {'FINISHED'}


classes = [
    # Patterns
    DAW_OT_AddPattern,
    DAW_OT_RemovePattern,
    DAW_OT_DuplicatePattern,
    DAW_OT_ClearPatternNotes,
    DAW_OT_ResizePattern,
    # Notas
    DAW_OT_AddPatternNote,
    DAW_OT_RemovePatternNote,
    DAW_OT_TogglePatternNote,
    # Clips
    DAW_OT_AddPatternClip,
    DAW_OT_RemovePatternClip,
    DAW_OT_MovePatternClip,
    DAW_OT_ResizePatternClip,
    DAW_OT_SplitPatternClip,
    DAW_OT_ClearPatternClips,
    # Grupos
    DAW_OT_AddPatternGroup,
    DAW_OT_RemovePatternGroup,
    DAW_OT_AddPatternToGroup,
    DAW_OT_RemovePatternFromGroup,
]