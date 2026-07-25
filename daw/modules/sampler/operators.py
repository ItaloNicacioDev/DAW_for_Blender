# modules/sampler/operators.py
"""
Operadores Blender para o módulo Sampler: carregamento, preview, loop editing, etc.
"""
from __future__ import annotations

import os
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, EnumProperty
from bpy.types import Operator, OperatorFileListElement
from typing import Set

from .utils import read_wav_float
from .looping import find_nearest_zero_crossing, build_seamless_loop
from .slicing import slice_equal, detect_transients, slice_by_transients


class SAMPLER_OT_LoadSample(Operator):
    """Carrega um arquivo WAV como novo sample."""
    bl_idname = "sampler.load_sample"
    bl_label = "Carregar Sample"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(name="Arquivo", subtype='FILE_PATH')
    files: bpy.props.CollectionProperty(
        name="Arquivos",
        type=OperatorFileListElement,
    )

    filter_glob: StringProperty(default="*.wav", options={'HIDDEN'})

    def execute(self, context):
        settings = context.scene.daw_sampler_settings

        for f in self.files:
            if not f.name.lower().endswith('.wav'):
                continue

            filepath = os.path.join(os.path.dirname(self.filepath), f.name)

            try:
                data, sr, channels = read_wav_float(filepath)
            except Exception as e:
                self.report({'ERROR'}, f"Erro ao carregar {f.name}: {str(e)}")
                continue

            # Cria novo sample
            sample = settings.samples.add()
            sample.name = os.path.splitext(f.name)[0]
            sample.filepath = filepath
            sample.samplerate = sr
            sample.channels = channels
            sample.num_frames = len(data) if data.ndim == 1 else data.shape[0]
            sample.loop_end = sample.num_frames
            sample.adsr.attack = 0.01
            sample.adsr.decay = 0.1
            sample.adsr.sustain = 0.8
            sample.adsr.release = 0.2

            self.report({'INFO'}, f"Sample '{sample.name}' carregado ({sample.num_frames} frames)")

        settings.active_sample_index = min(settings.active_sample_index, len(settings.samples) - 1)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class SAMPLER_OT_DeleteSample(Operator):
    """Remove o sample ativo."""
    bl_idname = "sampler.delete_sample"
    bl_label = "Deletar Sample"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.daw_sampler_settings
        if settings.active_sample_index < len(settings.samples):
            settings.samples.remove(settings.active_sample_index)
            settings.active_sample_index = min(settings.active_sample_index, len(settings.samples) - 1)
            self.report({'INFO'}, "Sample deletado")
        return {'FINISHED'}


class SAMPLER_OT_PreviewNote(Operator):
    """Reproduz uma nota de preview do sample."""
    bl_idname = "sampler.preview_note"
    bl_label = "Preview Nota"
    bl_options = {'REGISTER'}

    def execute(self, context):
        settings = context.scene.daw_sampler_settings
        if not settings.samples or settings.active_sample_index >= len(settings.samples):
            self.report({'WARNING'}, "Nenhum sample selecionado")
            return {'CANCELLED'}

        sample = settings.samples[settings.active_sample_index]
        self.report({'INFO'}, f"Reproduzindo nota {sample.root_note} (ainda não implementado)")
        return {'FINISHED'}


class SAMPLER_OT_SliceEqual(Operator):
    """Divide o sample em fatias de tamanho igual."""
    bl_idname = "sampler.slice_equal"
    bl_label = "Fatiar (Igual)"
    bl_options = {'REGISTER', 'UNDO'}

    num_slices: IntProperty(
        name="Número de Fatias",
        default=8, min=1, max=128,
    )

    def execute(self, context):
        settings = context.scene.daw_sampler_settings
        sample = settings.samples[settings.active_sample_index]

        slices = slice_equal(sample.num_frames, self.num_slices)
        sample.slices.clear()

        for start, end in slices:
            slice_item = sample.slices.add()
            slice_item.start_frame = start
            slice_item.end_frame = end

        self.report({'INFO'}, f"Sample dividido em {len(slices)} fatias")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class SAMPLER_OT_SliceByTransients(Operator):
    """Detecta automaticamente pontos de transiente e cria fatias."""
    bl_idname = "sampler.slice_by_transients"
    bl_label = "Fatiar (Transientes)"
    bl_options = {'REGISTER', 'UNDO'}

    sensitivity: FloatProperty(
        name="Sensibilidade",
        default=0.35, min=0.0, max=1.0,
    )

    def execute(self, context):
        settings = context.scene.daw_sampler_settings
        sample = settings.samples[settings.active_sample_index]

        try:
            data, _, _ = read_wav_float(sample.filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Erro ao ler sample: {str(e)}")
            return {'CANCELLED'}

        slices = slice_by_transients(data, sample.samplerate, self.sensitivity)
        sample.slices.clear()

        for start, end in slices:
            slice_item = sample.slices.add()
            slice_item.start_frame = start
            slice_item.end_frame = end

        self.report({'INFO'}, f"Detectados {len(slices)} transientes")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class SAMPLER_OT_LoopSnapStart(Operator):
    """Alinha o início do loop para a passagem por zero mais próxima."""
    bl_idname = "sampler.loop_snap_start"
    bl_label = "Snap Loop Start (Zero)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.daw_sampler_settings
        sample = settings.samples[settings.active_sample_index]

        try:
            data, _, _ = read_wav_float(sample.filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Erro ao ler sample: {str(e)}")
            return {'CANCELLED'}

        new_pos = find_nearest_zero_crossing(data, sample.loop_start, search_radius=512)
        sample.loop_start = new_pos
        self.report({'INFO'}, f"Loop start ajustado para {new_pos}")
        return {'FINISHED'}


class SAMPLER_OT_LoopSnapEnd(Operator):
    """Alinha o fim do loop para a passagem por zero mais próxima."""
    bl_idname = "sampler.loop_snap_end"
    bl_label = "Snap Loop End (Zero)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.daw_sampler_settings
        sample = settings.samples[settings.active_sample_index]

        try:
            data, _, _ = read_wav_float(sample.filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Erro ao ler sample: {str(e)}")
            return {'CANCELLED'}

        new_pos = find_nearest_zero_crossing(data, sample.loop_end, search_radius=512)
        sample.loop_end = new_pos
        self.report({'INFO'}, f"Loop end ajustado para {new_pos}")
        return {'FINISHED'}


class SAMPLER_OT_BuildSeamlessLoop(Operator):
    """Aplica crossfade na junção do loop para melhorar continuidade."""
    bl_idname = "sampler.build_seamless_loop"
    bl_label = "Gerar Loop Seamless"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.daw_sampler_settings
        sample = settings.samples[settings.active_sample_index]

        try:
            data, sr, channels = read_wav_float(sample.filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Erro ao ler sample: {str(e)}")
            return {'CANCELLED'}

        crossfade_ms = sample.loop_crossfade_ms
        crossfade_samples = int(sr * crossfade_ms / 1000.0)
        seamless_data = build_seamless_loop(data, sample.loop_start, sample.loop_end, crossfade_samples)

        self.report({'INFO'}, f"Loop seamless gerado com {crossfade_samples} samples de crossfade")
        return {'FINISHED'}


class SAMPLER_OT_AddSlice(Operator):
    """Adiciona uma nova fatia."""
    bl_idname = "sampler.add_slice"
    bl_label = "Adicionar Fatia"

    def execute(self, context):
        settings = context.scene.daw_sampler_settings
        sample = settings.samples[settings.active_sample_index]
        slice_item = sample.slices.add()
        slice_item.start_frame = 0
        slice_item.end_frame = sample.num_frames
        return {'FINISHED'}


class SAMPLER_OT_DeleteSlice(Operator):
    """Remove a fatia ativa."""
    bl_idname = "sampler.delete_slice"
    bl_label = "Deletar Fatia"

    def execute(self, context):
        settings = context.scene.daw_sampler_settings
        sample = settings.samples[settings.active_sample_index]
        if sample.active_slice_index < len(sample.slices):
            sample.slices.remove(sample.active_slice_index)
            sample.active_slice_index = min(sample.active_slice_index, len(sample.slices) - 1)
        return {'FINISHED'}


classes = [
    SAMPLER_OT_LoadSample,
    SAMPLER_OT_DeleteSample,
    SAMPLER_OT_PreviewNote,
    SAMPLER_OT_SliceEqual,
    SAMPLER_OT_SliceByTransients,
    SAMPLER_OT_LoopSnapStart,
    SAMPLER_OT_LoopSnapEnd,
    SAMPLER_OT_BuildSeamlessLoop,
    SAMPLER_OT_AddSlice,
    SAMPLER_OT_DeleteSlice,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)