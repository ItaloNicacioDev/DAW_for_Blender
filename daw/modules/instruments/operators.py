# modules/instruments/operators.py
"""
Operators do Blender para o módulo de Instrumentos.

Responsabilidade:
    Ações de edição disparadas pela UI: adicionar/remover/duplicar
    instrumento, mute/solo, tocar preview de nota/acorde, inserir
    progressões de acordes no Piano Roll, aplicar e salvar presets.
"""
from __future__ import annotations

import bpy
from bpy.props import FloatProperty, IntProperty, StringProperty
from bpy.types import Operator

from . import synth
from . import midi as midi_module
from . import presets as presets_module
from .utils import (
    unique_instrument_name,
    clamp_index,
    get_active_instrument,
    instrument_props_to_model,
    apply_model_to_instrument_props,
    insert_progression_to_piano_roll,
    get_playhead_beat,
)


def _rack(context):
    return context.scene.daw_instruments


# ---------------------------------------------------------------------- #
# Instrumentos
# ---------------------------------------------------------------------- #
class DAW_OT_AddInstrument(Operator):
    bl_idname = "daw.add_instrument"
    bl_label = "Adicionar Instrumento"
    bl_description = "Adiciona um novo instrumento ao rack"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="Novo Instrumento")
    instrument_id: IntProperty(default=0, min=0, max=7)

    def execute(self, context):
        rack = _rack(context)
        inst = rack.instruments.add()
        inst.name = unique_instrument_name(rack, self.name)
        inst.instrument_id = str(self.instrument_id)
        rack.active_instrument_index = len(rack.instruments) - 1
        self.report({'INFO'}, f"Instrumento '{inst.name}' adicionado")
        return {'FINISHED'}


class DAW_OT_RemoveInstrument(Operator):
    bl_idname = "daw.remove_instrument"
    bl_label = "Remover Instrumento"
    bl_description = "Remove o instrumento selecionado do rack"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_instrument_index
        if not (0 <= index < len(rack.instruments)):
            self.report({'WARNING'}, "Nenhum instrumento para remover")
            return {'CANCELLED'}

        name = rack.instruments[index].name
        rack.instruments.remove(index)
        rack.active_instrument_index = clamp_index(rack.active_instrument_index, len(rack.instruments))
        self.report({'INFO'}, f"Instrumento '{name}' removido")
        return {'FINISHED'}


class DAW_OT_DuplicateInstrument(Operator):
    bl_idname = "daw.duplicate_instrument"
    bl_label = "Duplicar Instrumento"
    bl_description = "Duplica o instrumento selecionado"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_instrument_index
        if not (0 <= index < len(rack.instruments)):
            self.report({'WARNING'}, "Nenhum instrumento para duplicar")
            return {'CANCELLED'}

        src = rack.instruments[index]
        model = instrument_props_to_model(src).duplicate()
        model.name = unique_instrument_name(rack, model.name)

        new = rack.instruments.add()
        apply_model_to_instrument_props(model, new)

        rack.instruments.move(len(rack.instruments) - 1, index + 1)
        rack.active_instrument_index = index + 1
        self.report({'INFO'}, f"Instrumento '{new.name}' criado")
        return {'FINISHED'}


class DAW_OT_MoveInstrument(Operator):
    bl_idname = "daw.move_instrument"
    bl_label = "Mover Instrumento"
    bl_description = "Move o instrumento selecionado para cima ou para baixo na lista"
    bl_options = {'REGISTER', 'UNDO'}

    direction: StringProperty(default="UP")  # 'UP' ou 'DOWN'

    def execute(self, context):
        rack = _rack(context)
        index = rack.active_instrument_index
        target = index - 1 if self.direction == "UP" else index + 1

        if not (0 <= index < len(rack.instruments)) or not (0 <= target < len(rack.instruments)):
            return {'CANCELLED'}

        rack.instruments.move(index, target)
        rack.active_instrument_index = target
        return {'FINISHED'}


class DAW_OT_ToggleInstrumentMute(Operator):
    bl_idname = "daw.toggle_instrument_mute"
    bl_label = "Mudo"
    bl_description = "Ativa/desativa o mudo do instrumento"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_instrument_index
        if not (0 <= index < len(rack.instruments)):
            return {'CANCELLED'}
        rack.instruments[index].mute = not rack.instruments[index].mute
        return {'FINISHED'}


class DAW_OT_ToggleInstrumentSolo(Operator):
    bl_idname = "daw.toggle_instrument_solo"
    bl_label = "Solo"
    bl_description = "Ativa/desativa o solo do instrumento"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_instrument_index
        if not (0 <= index < len(rack.instruments)):
            return {'CANCELLED'}
        rack.instruments[index].solo = not rack.instruments[index].solo
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Preview de áudio
# ---------------------------------------------------------------------- #
class DAW_OT_PreviewInstrumentNote(Operator):
    bl_idname = "daw.preview_instrument_note"
    bl_label = "Tocar Nota"
    bl_description = "Toca uma nota de teste com o instrumento selecionado"
    bl_options = {'REGISTER'}

    index: IntProperty(default=-1)
    pitch: IntProperty(default=60, min=0, max=127)  # C4 por padrão

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_instrument_index
        if not (0 <= index < len(rack.instruments)):
            return {'CANCELLED'}

        props = rack.instruments[index]
        model = instrument_props_to_model(props)
        midi_module.note_on(model, self.pitch, velocity=rack.preview_velocity, duration=rack.preview_duration)
        return {'FINISHED'}


class DAW_OT_PreviewChordProgression(Operator):
    bl_idname = "daw.preview_chord_progression"
    bl_label = "Tocar Progressão"
    bl_description = "Toca o primeiro acorde da progressão selecionada com o instrumento ativo"
    bl_options = {'REGISTER'}

    def execute(self, context):
        rack = _rack(context)
        active = get_active_instrument(rack)
        if active is None:
            self.report({'WARNING'}, "Nenhum instrumento ativo")
            return {'CANCELLED'}

        prog = synth.get_progression(rack.selected_progression)
        if not prog or not prog.get("chords"):
            self.report({'WARNING'}, "Progressão inválida")
            return {'CANCELLED'}

        model = instrument_props_to_model(active)
        first_chord = prog["chords"][0]
        midi_module.play_chord(model, first_chord["notes"], velocity=85, duration=2.0)
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Inserção no Piano Roll
# ---------------------------------------------------------------------- #
class DAW_OT_InsertChordProgression(Operator):
    bl_idname = "daw.insert_chord_progression"
    bl_label = "Inserir Progressão"
    bl_description = "Insere as notas da progressão de acordes selecionada no Piano Roll"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rack = _rack(context)
        active = get_active_instrument(rack)

        start_beat = get_playhead_beat(context) if rack.insert_at_playhead else 0.0
        octave_shift = active.octave_shift if active is not None else 0

        count = insert_progression_to_piano_roll(
            context, rack.selected_progression,
            start_beat=start_beat, octave_shift=octave_shift,
        )

        if count == 0:
            self.report({'WARNING'}, "Nenhuma nota inserida (progressão vazia ou Piano Roll indisponível)")
            return {'CANCELLED'}

        self.report({'INFO'}, f"{count} notas inseridas no Piano Roll")
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Presets
# ---------------------------------------------------------------------- #
class DAW_OT_ApplyInstrumentPreset(Operator):
    bl_idname = "daw.apply_instrument_preset"
    bl_label = "Aplicar Preset"
    bl_description = "Aplica um preset salvo ao instrumento selecionado"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)
    preset_name: StringProperty(default="")

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_instrument_index
        if not (0 <= index < len(rack.instruments)):
            return {'CANCELLED'}

        preset = presets_module.get_preset(self.preset_name)
        if preset is None:
            self.report({'ERROR'}, f"Preset '{self.preset_name}' não encontrado")
            return {'CANCELLED'}

        props = rack.instruments[index]
        original_name = props.name
        apply_model_to_instrument_props(preset, props)
        props.name = original_name  # mantém o nome do instrumento, só troca os parâmetros

        self.report({'INFO'}, f"Preset '{self.preset_name}' aplicado")
        return {'FINISHED'}


class DAW_OT_SaveInstrumentPreset(Operator):
    bl_idname = "daw.save_instrument_preset"
    bl_label = "Salvar Preset"
    bl_description = "Salva os parâmetros atuais do instrumento como um novo preset"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)
    preset_name: StringProperty(name="Nome do Preset", default="Meu Instrumento")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "preset_name")

    def execute(self, context):
        rack = _rack(context)
        index = self.index if self.index >= 0 else rack.active_instrument_index
        if not (0 <= index < len(rack.instruments)):
            return {'CANCELLED'}

        model = instrument_props_to_model(rack.instruments[index])
        ok = presets_module.save_user_preset(self.preset_name, model)
        if ok:
            self.report({'INFO'}, f"Preset '{self.preset_name}' salvo")
        else:
            self.report({'ERROR'}, "Não foi possível salvar o preset")
        return {'FINISHED'} if ok else {'CANCELLED'}


classes = [
    DAW_OT_AddInstrument,
    DAW_OT_RemoveInstrument,
    DAW_OT_DuplicateInstrument,
    DAW_OT_MoveInstrument,
    DAW_OT_ToggleInstrumentMute,
    DAW_OT_ToggleInstrumentSolo,
    DAW_OT_PreviewInstrumentNote,
    DAW_OT_PreviewChordProgression,
    DAW_OT_InsertChordProgression,
    DAW_OT_ApplyInstrumentPreset,
    DAW_OT_SaveInstrumentPreset,
]