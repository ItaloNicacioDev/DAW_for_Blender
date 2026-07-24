# modules/piano_roll/operators.py
"""
Operators do Blender para o módulo Piano Roll.

Responsabilidade:
    Ações de edição: adicionar/remover/duplicar notas, quantizar,
    humanizar, gerar acordes, arpejos, e gerenciar seleção.
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator

from .scales import get_note_name
from .utils import clamp, clamp_index


def _pr(context):
    return context.scene.daw_piano_roll


def _note_for(context, index: int = -1):
    pr = _pr(context)
    i = index if index >= 0 else pr.active_note_index
    if not (0 <= i < len(pr.notes)):
        return None
    return pr.notes[i]


# ---------------------------------------------------------------------- #
# Notas básicas
# ---------------------------------------------------------------------- #
class DAW_OT_PRAddNote(Operator):
    bl_idname = "daw.pr_add_note"
    bl_label = "Adicionar Nota"
    bl_description = "Adiciona uma nota no piano roll"
    bl_options = {'REGISTER', 'UNDO'}

    pitch: IntProperty(default=60, min=0, max=127)
    start_beat: FloatProperty(default=0.0, min=0.0)
    duration_beats: FloatProperty(default=0.25, min=0.01)
    velocity: FloatProperty(default=0.8, min=0.0, max=1.0)

    def execute(self, context):
        pr = _pr(context)
        note = pr.notes.add()
        note.pitch = self.pitch
        note.start_beat = self.start_beat
        note.duration_beats = self.duration_beats
        note.velocity = self.velocity
        note.selected = True
        pr.active_note_index = len(pr.notes) - 1
        return {'FINISHED'}


class DAW_OT_PRRemoveNote(Operator):
    bl_idname = "daw.pr_remove_note"
    bl_label = "Remover Nota"
    bl_description = "Remove a nota selecionada"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        pr = _pr(context)
        index = self.index if self.index >= 0 else pr.active_note_index
        if not (0 <= index < len(pr.notes)):
            return {'CANCELLED'}
        pr.notes.remove(index)
        pr.active_note_index = clamp_index(pr.active_note_index, len(pr.notes))
        return {'FINISHED'}


class DAW_OT_PRClearNotes(Operator):
    bl_idname = "daw.pr_clear_notes"
    bl_label = "Limpar Notas"
    bl_description = "Remove todas as notas do piano roll"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _pr(context).clear_notes()
        return {'FINISHED'}


class DAW_OT_PRDuplicateNote(Operator):
    bl_idname = "daw.pr_duplicate_note"
    bl_label = "Duplicar Nota"
    bl_description = "Duplica a nota selecionada"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)
    offset_beats: FloatProperty(default=0.25, min=0.0)

    def execute(self, context):
        pr = _pr(context)
        note = _note_for(context, self.index)
        if note is None:
            return {'CANCELLED'}

        new = pr.notes.add()
        new.pitch = note.pitch
        new.start_beat = note.start_beat + self.offset_beats
        new.duration_beats = note.duration_beats
        new.velocity = note.velocity
        new.selected = True
        note.selected = False
        pr.active_note_index = len(pr.notes) - 1
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Seleção
# ---------------------------------------------------------------------- #
class DAW_OT_PRSelectAll(Operator):
    bl_idname = "daw.pr_select_all"
    bl_label = "Selecionar Tudo"
    bl_description = "Seleciona todas as notas"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for note in _pr(context).notes:
            note.selected = True
        return {'FINISHED'}


class DAW_OT_PRDeselectAll(Operator):
    bl_idname = "daw.pr_deselect_all"
    bl_label = "Desselecionar Tudo"
    bl_description = "Desseleciona todas as notas"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for note in _pr(context).notes:
            note.selected = False
        return {'FINISHED'}


class DAW_OT_PRInvertSelection(Operator):
    bl_idname = "daw.pr_invert_selection"
    bl_label = "Inverter Seleção"
    bl_description = "Inverte a seleção de notas"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for note in _pr(context).notes:
            note.selected = not note.selected
        return {'FINISHED'}


class DAW_OT_PRDeleteSelected(Operator):
    bl_idname = "daw.pr_delete_selected"
    bl_label = "Excluir Selecionadas"
    bl_description = "Remove todas as notas selecionadas"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pr = _pr(context)
        pr.notes = [n for n in pr.notes if not n.selected]
        pr.active_note_index = clamp_index(pr.active_note_index, len(pr.notes))
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Transposição e Velocity
# ---------------------------------------------------------------------- #
class DAW_OT_PRTransposeSelected(Operator):
    bl_idname = "daw.pr_transpose_selected"
    bl_label = "Transpor"
    bl_description = "Transpõe as notas selecionadas em semitons"
    bl_options = {'REGISTER', 'UNDO'}

    semitones: IntProperty(default=12, min=-127, max=127)

    def execute(self, context):
        for note in _pr(context).notes:
            if note.selected:
                note.pitch = max(0, min(127, note.pitch + self.semitones))
        return {'FINISHED'}


class DAW_OT_PRSetVelocitySelected(Operator):
    bl_idname = "daw.pr_set_velocity_selected"
    bl_label = "Definir Velocity"
    bl_description = "Define a velocity das notas selecionadas"
    bl_options = {'REGISTER', 'UNDO'}

    velocity: FloatProperty(default=0.8, min=0.0, max=1.0, subtype='FACTOR')

    def execute(self, context):
        for note in _pr(context).notes:
            if note.selected:
                note.velocity = self.velocity
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Quantize
# ---------------------------------------------------------------------- #
class DAW_OT_PRQuantizeSelected(Operator):
    bl_idname = "daw.pr_quantize_selected"
    bl_label = "Quantizar"
    bl_description = "Quantiza o timing das notas selecionadas"
    bl_options = {'REGISTER', 'UNDO'}

    strength: FloatProperty(default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    grid_division: FloatProperty(default=0.25, min=0.01, max=4.0)

    def execute(self, context):
        from .quantize import quantize_beat
        for note in _pr(context).notes:
            if note.selected:
                note.start_beat = quantize_beat(note.start_beat, self.grid_division, self.strength)
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Humanize
# ---------------------------------------------------------------------- #
class DAW_OT_PRHumanizeSelected(Operator):
    bl_idname = "daw.pr_humanize_selected"
    bl_label = "Humanizar"
    bl_description = "Aplica variação aleatória natural às notas selecionadas"
    bl_options = {'REGISTER', 'UNDO'}

    timing: FloatProperty(default=0.1, min=0.0, max=1.0, subtype='FACTOR')
    velocity: FloatProperty(default=0.1, min=0.0, max=1.0, subtype='FACTOR')

    def execute(self, context):
        from .humanize import humanize_timing, humanize_velocity
        notes = [n for n in _pr(context).notes if n.selected]
        humanize_timing(notes, self.timing)
        humanize_velocity(notes, self.velocity)
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Acordes
# ---------------------------------------------------------------------- #
class DAW_OT_PRInsertChord(Operator):
    bl_idname = "daw.pr_insert_chord"
    bl_label = "Inserir Acorde"
    bl_description = "Insere um acorde na posição do cursor"
    bl_options = {'REGISTER', 'UNDO'}

    root_pitch: IntProperty(default=60, min=0, max=127)
    chord_name: StringProperty(default="MAJOR")
    start_beat: FloatProperty(default=0.0, min=0.0)
    duration_beats: FloatProperty(default=0.5, min=0.01)
    velocity: FloatProperty(default=0.8, min=0.0, max=1.0)

    def execute(self, context):
        from .chords import generate_chord_notes
        pr = _pr(context)
        notes_data = generate_chord_notes(
            self.root_pitch, self.chord_name,
            self.start_beat, self.duration_beats, self.velocity
        )
        for data in notes_data:
            note = pr.notes.add()
            note.pitch = data["pitch"]
            note.start_beat = data["start_beat"]
            note.duration_beats = data["duration_beats"]
            note.velocity = data["velocity"]
            note.selected = True
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Arpeggiator
# ---------------------------------------------------------------------- #
class DAW_OT_PRGenerateArpeggio(Operator):
    bl_idname = "daw.pr_generate_arpeggio"
    bl_label = "Gerar Arpejo"
    bl_description = "Gera um arpejo a partir de um acorde"
    bl_options = {'REGISTER', 'UNDO'}

    root_pitch: IntProperty(default=60, min=0, max=127)
    chord_name: StringProperty(default="MAJOR")
    pattern: StringProperty(default="UP")
    start_beat: FloatProperty(default=0.0, min=0.0)
    step_beats: FloatProperty(default=0.25, min=0.01)
    duration_beats: FloatProperty(default=0.2, min=0.01)
    velocity: FloatProperty(default=0.8, min=0.0, max=1.0)
    octaves: IntProperty(default=1, min=1, max=4)

    def execute(self, context):
        from .chords import get_chord_notes
        from .arpeggiator import generate_arpeggio
        pr = _pr(context)

        pitches = get_chord_notes(self.root_pitch, self.chord_name)
        notes = generate_arpeggio(
            pitches, self.pattern, self.start_beat,
            self.step_beats, self.duration_beats, self.velocity, self.octaves
        )
        for n in notes:
            note = pr.notes.add()
            note.pitch = n.pitch
            note.start_beat = n.start_beat
            note.duration_beats = n.duration_beats
            note.velocity = n.velocity
            note.selected = True
        return {'FINISHED'}


classes = [
    DAW_OT_PRAddNote,
    DAW_OT_PRRemoveNote,
    DAW_OT_PRClearNotes,
    DAW_OT_PRDuplicateNote,
    DAW_OT_PRSelectAll,
    DAW_OT_PRDeselectAll,
    DAW_OT_PRInvertSelection,
    DAW_OT_PRDeleteSelected,
    DAW_OT_PRTransposeSelected,
    DAW_OT_PRSetVelocitySelected,
    DAW_OT_PRQuantizeSelected,
    DAW_OT_PRHumanizeSelected,
    DAW_OT_PRInsertChord,
    DAW_OT_PRGenerateArpeggio,
]