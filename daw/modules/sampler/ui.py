# modules/sampler/ui.py
"""
Interface do usuário (painéis Blender) para o módulo Sampler.
"""
from __future__ import annotations

import bpy
from bpy.types import Panel


class SAMPLER_PT_MainPanel(Panel):
    """Painel principal do Sampler."""
    bl_label = "Sampler"
    bl_idname = "SAMPLER_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_sampler_settings

        # === Configurações Gerais ===
        box = layout.box()
        box.label(text="Configurações", icon='SETTINGS')

        row = box.row()
        row.prop(settings, "polyphony", text="Polifonia")
        row.prop(settings, "master_gain_db", text="Ganho Master (dB)")

        # === Samples ===
        box = layout.box()
        box.label(text="Samples", icon='SOUND')

        row = box.row()
        row.operator("sampler.load_sample", icon='IMPORT')

        if settings.samples:
            row = box.row()
            row.template_list(
                "SAMPLER_UL_Samples", "", settings, "samples",
                settings, "active_sample_index", rows=4
            )

            col = row.column(align=True)
            col.operator("sampler.delete_sample", icon='X', text="")

            # Painel do sample ativo
            sample = settings.samples[settings.active_sample_index]
            box_sample = layout.box()
            box_sample.label(text=f"Sample: {sample.name}", icon='SOUND')

            split = box_sample.split()
            split.label(text=f"Frames: {sample.num_frames}")
            split.label(text=f"Taxa: {sample.samplerate} Hz")
            split.label(text=f"Canais: {sample.channels}")


class SAMPLER_PT_SampleSettings(Panel):
    """Painel de configurações do sample ativo."""
    bl_label = "Configurações do Sample"
    bl_idname = "SAMPLER_PT_sample_settings"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    @classmethod
    def poll(cls, context):
        settings = context.scene.daw_sampler_settings
        return len(settings.samples) > 0

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_sampler_settings
        sample = settings.samples[settings.active_sample_index]

        # === Afinação ===
        box = layout.box()
        box.label(text="Afinação", icon='MUSIC')

        col = box.column(align=True)
        col.prop(sample, "root_note", text="Nota Raiz")
        col.prop(sample, "note_low", text="Nota Mínima")
        col.prop(sample, "note_high", text="Nota Máxima")

        col = box.column(align=True)
        col.prop(sample, "tune_semitones", text="Semitons")
        col.prop(sample, "tune_cents", text="Cents")

        # === Ganho e Pan ===
        box = layout.box()
        box.label(text="Volume", icon='SOUND')

        col = box.column(align=True)
        col.prop(sample, "gain_db", text="Ganho (dB)")
        col.prop(sample, "pan", text="Pan")
        col.prop(sample, "reverse", text="Reverso")

        # === Loop ===
        box = layout.box()
        box.label(text="Loop", icon='LOOP_BACK')

        col = box.column()
        col.prop(sample, "loop_mode", text="Modo")

        col = box.column(align=True)
        col.prop(sample, "loop_start", text="Início")
        col.prop(sample, "loop_end", text="Fim")
        col.prop(sample, "loop_crossfade_ms", text="Crossfade (ms)")

        # Botões de snap
        row = box.row(align=True)
        row.operator("sampler.loop_snap_start", text="Snap Start")
        row.operator("sampler.loop_snap_end", text="Snap End")

        row = box.row()
        row.operator("sampler.build_seamless_loop", text="Build Seamless", icon='SMOOTHCURVE')

        # === ADSR ===
        box = layout.box()
        box.label(text="Envelope ADSR", icon='FCURVE')

        adsr = sample.adsr
        col = box.column(align=True)
        col.prop(adsr, "attack", text="Attack")
        col.prop(adsr, "decay", text="Decay")
        col.prop(adsr, "sustain", text="Sustain")
        col.prop(adsr, "release", text="Release")

        # === Time-Stretch ===
        box = layout.box()
        box.label(text="Time-Stretch", icon='TIME')

        col = box.column()
        col.prop(sample, "stretch_enabled", text="Ativar")
        if sample.stretch_enabled:
            col.prop(sample, "stretch_ratio", text="Razão")


class SAMPLER_PT_Slicing(Panel):
    """Painel de fatiamento de samples."""
    bl_label = "Fatiamento (Slicing)"
    bl_idname = "SAMPLER_PT_slicing"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    @classmethod
    def poll(cls, context):
        settings = context.scene.daw_sampler_settings
        return len(settings.samples) > 0

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_sampler_settings
        sample = settings.samples[settings.active_sample_index]

        # === Métodos de Slicing ===
        box = layout.box()
        box.label(text="Métodos de Slicing", icon='KNIFE')

        row = box.row(align=True)
        row.operator("sampler.slice_equal", text="Dividir (Igual)")
        row.operator("sampler.slice_by_transients", text="Detectar (Transientes)")

        # === Slices ===
        if sample.slices:
            box = layout.box()
            box.label(text="Fatias", icon='GRIP')

            row = box.row()
            row.template_list(
                "SAMPLER_UL_Slices", "", sample, "slices",
                sample, "active_slice_index", rows=4
            )

            col = row.column(align=True)
            col.operator("sampler.add_slice", icon='ADD', text="")
            col.operator("sampler.delete_slice", icon='X', text="")

            # Info da slice
            if sample.active_slice_index < len(sample.slices):
                slice_item = sample.slices[sample.active_slice_index]
                box_info = layout.box()
                box_info.label(text=f"Fatia: {slice_item.name}")

                split = box_info.split()
                split.label(text=f"Início: {slice_item.start_frame}")
                split.label(text=f"Fim: {slice_item.end_frame}")

        row = layout.row()
        row.prop(sample, "play_as_slices", text="Tocar como Fatias")


class SAMPLER_PT_Preview(Panel):
    """Painel de preview e teste de notas."""
    bl_label = "Preview"
    bl_idname = "SAMPLER_PT_preview"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    @classmethod
    def poll(cls, context):
        settings = context.scene.daw_sampler_settings
        return len(settings.samples) > 0

    def draw(self, context):
        layout = self.layout
        settings = context.scene.daw_sampler_settings

        box = layout.box()
        box.label(text="Teste de Notas", icon='SPEAKER')

        row = box.row()
        row.prop(settings, "preview_note", text="Nota MIDI")
        row.prop(settings, "preview_velocity", text="Velocidade")

        row = box.row()
        row.operator("sampler.preview_note", text="Play", icon='PLAY')


# === UI Lists ===

class SAMPLER_UL_Samples(bpy.types.UIList):
    """Custom UIList para samples."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name)
            layout.label(text=f"{item.num_frames} fr", icon='TIME')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name)


class SAMPLER_UL_Slices(bpy.types.UIList):
    """Custom UIList para slices."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name)
            layout.label(text=f"{item.start_frame}-{item.end_frame}")
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=f"{index}")


classes = [
    SAMPLER_PT_MainPanel,
    SAMPLER_PT_SampleSettings,
    SAMPLER_PT_Slicing,
    SAMPLER_PT_Preview,
    SAMPLER_UL_Samples,
    SAMPLER_UL_Slices,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)