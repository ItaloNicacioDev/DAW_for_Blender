# modules/mixer/operators.py
"""
Operators do Blender para o módulo Mixer.

Responsabilidade:
    Ações de edição disparadas pela UI: adicionar/remover/duplicar/mover
    faixas, mute/solo, gerenciar buses e roteamento, inserts (efeitos) e
    sends, além de aplicar/salvar presets de channel strip e de insert.
"""
from __future__ import annotations

import bpy
from bpy.props import FloatProperty, IntProperty, StringProperty
from bpy.types import Operator

from . import presets as presets_module
from .effects import EFFECT_TYPES, default_params_for
from .routing import bus_names
from .tracks import MASTER_TRACK_NAME, get_color_by_index
from .utils import clamp_index, unique_bus_name, unique_track_name


def _mixer(context):
    return context.scene.daw_mixer


def _track_for(context, index: int = -1):
    mixer = _mixer(context)
    i = index if index >= 0 else mixer.active_track_index
    if not (0 <= i < len(mixer.tracks)):
        return None
    return mixer.tracks[i]


def _bus_for(context, index: int = -1):
    mixer = _mixer(context)
    i = index if index >= 0 else mixer.active_bus_index
    if not (0 <= i < len(mixer.buses)):
        return None
    return mixer.buses[i]


# ---------------------------------------------------------------------- #
# Faixas
# ---------------------------------------------------------------------- #
class DAW_OT_AddMixerTrack(Operator):
    bl_idname = "daw.add_mixer_track"
    bl_label = "Adicionar Faixa"
    bl_description = "Adiciona uma nova faixa ao Mixer"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="Nova Faixa")

    def execute(self, context):
        mixer = _mixer(context)
        track = mixer.tracks.add()
        track.name = unique_track_name(mixer, self.name)
        track.color = get_color_by_index(len(mixer.tracks) - 1)
        track.output_bus = MASTER_TRACK_NAME
        mixer.active_track_index = len(mixer.tracks) - 1
        self.report({'INFO'}, f"Faixa '{track.name}' adicionada")
        return {'FINISHED'}


class DAW_OT_RemoveMixerTrack(Operator):
    bl_idname = "daw.remove_mixer_track"
    bl_label = "Remover Faixa"
    bl_description = "Remove a faixa selecionada do Mixer"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        mixer = _mixer(context)
        index = self.index if self.index >= 0 else mixer.active_track_index
        if not (0 <= index < len(mixer.tracks)):
            self.report({'WARNING'}, "Nenhuma faixa para remover")
            return {'CANCELLED'}

        name = mixer.tracks[index].name
        mixer.tracks.remove(index)
        mixer.active_track_index = clamp_index(mixer.active_track_index, len(mixer.tracks))
        self.report({'INFO'}, f"Faixa '{name}' removida")
        return {'FINISHED'}


class DAW_OT_DuplicateMixerTrack(Operator):
    bl_idname = "daw.duplicate_mixer_track"
    bl_label = "Duplicar Faixa"
    bl_description = "Duplica a faixa selecionada (volume, pan, inserts e sends)"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        mixer = _mixer(context)
        index = self.index if self.index >= 0 else mixer.active_track_index
        if not (0 <= index < len(mixer.tracks)):
            self.report({'WARNING'}, "Nenhuma faixa para duplicar")
            return {'CANCELLED'}

        src = mixer.tracks[index]
        data = presets_module.track_to_strip_dict(src)

        new = mixer.tracks.add()
        new.name = unique_track_name(mixer, f"{src.name} (cópia)")
        new.color = tuple(src.color)
        new.mute = src.mute
        new.solo = False
        new.source_index = -1
        presets_module.apply_strip_dict_to_track(new, data)

        mixer.tracks.move(len(mixer.tracks) - 1, index + 1)
        mixer.active_track_index = index + 1
        self.report({'INFO'}, f"Faixa '{new.name}' criada")
        return {'FINISHED'}


class DAW_OT_MoveMixerTrack(Operator):
    bl_idname = "daw.move_mixer_track"
    bl_label = "Mover Faixa"
    bl_description = "Move a faixa selecionada para cima ou para baixo na lista"
    bl_options = {'REGISTER', 'UNDO'}

    direction: StringProperty(default="UP")  # 'UP' ou 'DOWN'

    def execute(self, context):
        mixer = _mixer(context)
        index = mixer.active_track_index
        target = index - 1 if self.direction == "UP" else index + 1

        if not (0 <= index < len(mixer.tracks)) or not (0 <= target < len(mixer.tracks)):
            return {'CANCELLED'}

        mixer.tracks.move(index, target)
        mixer.active_track_index = target
        return {'FINISHED'}


class DAW_OT_ToggleMixerTrackMute(Operator):
    bl_idname = "daw.toggle_mixer_track_mute"
    bl_label = "Mudo"
    bl_description = "Ativa/desativa o mudo da faixa"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        track = _track_for(context, self.index)
        if track is None:
            return {'CANCELLED'}
        track.mute = not track.mute
        return {'FINISHED'}


class DAW_OT_ToggleMixerTrackSolo(Operator):
    bl_idname = "daw.toggle_mixer_track_solo"
    bl_label = "Solo"
    bl_description = "Ativa/desativa o solo da faixa"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        track = _track_for(context, self.index)
        if track is None:
            return {'CANCELLED'}
        track.solo = not track.solo
        return {'FINISHED'}


class DAW_OT_ResetMixerTrack(Operator):
    bl_idname = "daw.reset_mixer_track"
    bl_label = "Restaurar Faixa"
    bl_description = "Restaura volume e pan da faixa para os valores padrão"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        track = _track_for(context, self.index)
        if track is None:
            return {'CANCELLED'}
        track.volume = 0.78
        track.pan = 0.0
        return {'FINISHED'}


class DAW_OT_SetMixerTrackOutput(Operator):
    bl_idname = "daw.set_mixer_track_output"
    bl_label = "Rotear Saída"
    bl_description = "Define o bus de saída da faixa"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)
    bus_name: StringProperty(default=MASTER_TRACK_NAME)

    def execute(self, context):
        mixer = _mixer(context)
        track = _track_for(context, self.index)
        if track is None:
            return {'CANCELLED'}
        if self.bus_name not in bus_names(mixer.buses):
            self.report({'ERROR'}, f"Bus '{self.bus_name}' não existe")
            return {'CANCELLED'}
        track.output_bus = self.bus_name
        return {'FINISHED'}


class DAW_OT_ClearMixer(Operator):
    bl_idname = "daw.clear_mixer"
    bl_label = "Limpar Mixer"
    bl_description = "Remove todas as faixas e buses auxiliares do Mixer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mixer = _mixer(context)
        mixer.tracks.clear()
        mixer.active_track_index = 0

        # Mantém apenas o bus Master (índice 0).
        while len(mixer.buses) > 1:
            mixer.buses.remove(len(mixer.buses) - 1)
        mixer.active_bus_index = 0

        self.report({'INFO'}, "Mixer limpo")
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Buses / roteamento
# ---------------------------------------------------------------------- #
class DAW_OT_AddMixerBus(Operator):
    bl_idname = "daw.add_mixer_bus"
    bl_label = "Adicionar Bus"
    bl_description = "Cria um novo bus auxiliar"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="Bus")
    volume: FloatProperty(default=0.8, min=0.0, max=1.0)

    def execute(self, context):
        mixer = _mixer(context)
        bus = mixer.buses.add()
        bus.name = unique_bus_name(mixer, self.name)
        bus.volume = self.volume
        bus.is_master = False
        mixer.active_bus_index = len(mixer.buses) - 1
        self.report({'INFO'}, f"Bus '{bus.name}' criado")
        return {'FINISHED'}


class DAW_OT_RemoveMixerBus(Operator):
    bl_idname = "daw.remove_mixer_bus"
    bl_label = "Remover Bus"
    bl_description = "Remove o bus selecionado (o Master nunca é removido)"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        mixer = _mixer(context)
        index = self.index if self.index >= 0 else mixer.active_bus_index
        if not (0 <= index < len(mixer.buses)) or mixer.buses[index].is_master:
            self.report({'WARNING'}, "Não é possível remover este bus")
            return {'CANCELLED'}

        removed_name = mixer.buses[index].name
        mixer.buses.remove(index)
        mixer.active_bus_index = clamp_index(mixer.active_bus_index, len(mixer.buses))

        # Reatribui faixas roteadas para este bus ao Master e remove sends.
        for track in mixer.tracks:
            if track.output_bus == removed_name:
                track.output_bus = MASTER_TRACK_NAME
            for i in reversed(range(len(track.sends))):
                if track.sends[i].bus_name == removed_name:
                    track.sends.remove(i)

        self.report({'INFO'}, f"Bus '{removed_name}' removido")
        return {'FINISHED'}


class DAW_OT_ToggleMixerBusMute(Operator):
    bl_idname = "daw.toggle_mixer_bus_mute"
    bl_label = "Mudo do Bus"
    bl_description = "Ativa/desativa o mudo do bus"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        bus = _bus_for(context, self.index)
        if bus is None:
            return {'CANCELLED'}
        bus.mute = not bus.mute
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Inserts (efeitos)
# ---------------------------------------------------------------------- #
class DAW_OT_AddMixerInsert(Operator):
    bl_idname = "daw.add_mixer_insert"
    bl_label = "Adicionar Insert"
    bl_description = "Adiciona um efeito ao final da cadeia de inserts da faixa"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    effect_type: StringProperty(default="EQ")

    def execute(self, context):
        if self.effect_type not in EFFECT_TYPES:
            self.report({'ERROR'}, f"Tipo de efeito inválido: {self.effect_type}")
            return {'CANCELLED'}

        track = _track_for(context, self.track_index)
        if track is None:
            self.report({'WARNING'}, "Nenhuma faixa selecionada")
            return {'CANCELLED'}

        slot = track.inserts.add()
        slot.effect_type = self.effect_type
        presets_module.apply_params_to_insert_slot(slot, default_params_for(self.effect_type))
        track.active_insert_index = len(track.inserts) - 1

        self.report({'INFO'}, f"Insert '{self.effect_type.title()}' adicionado")
        return {'FINISHED'}


class DAW_OT_RemoveMixerInsert(Operator):
    bl_idname = "daw.remove_mixer_insert"
    bl_label = "Remover Insert"
    bl_description = "Remove o insert selecionado da cadeia"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)

    def execute(self, context):
        track = _track_for(context, self.track_index)
        if track is None:
            return {'CANCELLED'}
        index = self.slot_index if self.slot_index >= 0 else track.active_insert_index
        if not (0 <= index < len(track.inserts)):
            return {'CANCELLED'}

        track.inserts.remove(index)
        track.active_insert_index = clamp_index(track.active_insert_index, len(track.inserts))
        return {'FINISHED'}


class DAW_OT_MoveMixerInsert(Operator):
    bl_idname = "daw.move_mixer_insert"
    bl_label = "Mover Insert"
    bl_description = "Move o insert para cima ou para baixo (altera a ordem de processamento)"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    direction: StringProperty(default="UP")  # 'UP' ou 'DOWN'

    def execute(self, context):
        track = _track_for(context, self.track_index)
        if track is None:
            return {'CANCELLED'}

        index = track.active_insert_index
        target = index - 1 if self.direction == "UP" else index + 1
        if not (0 <= index < len(track.inserts)) or not (0 <= target < len(track.inserts)):
            return {'CANCELLED'}

        track.inserts.move(index, target)
        track.active_insert_index = target
        return {'FINISHED'}


class DAW_OT_ToggleMixerInsertBypass(Operator):
    bl_idname = "daw.toggle_mixer_insert_bypass"
    bl_label = "Bypass"
    bl_description = "Ativa/desativa o bypass deste insert (mantém na cadeia sem processar)"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)

    def execute(self, context):
        track = _track_for(context, self.track_index)
        if track is None:
            return {'CANCELLED'}
        index = self.slot_index if self.slot_index >= 0 else track.active_insert_index
        if not (0 <= index < len(track.inserts)):
            return {'CANCELLED'}
        track.inserts[index].bypass = not track.inserts[index].bypass
        return {'FINISHED'}


class DAW_OT_ResetMixerInsert(Operator):
    bl_idname = "daw.reset_mixer_insert"
    bl_label = "Restaurar Insert"
    bl_description = "Restaura os parâmetros deste insert para os valores padrão"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)

    def execute(self, context):
        track = _track_for(context, self.track_index)
        if track is None:
            return {'CANCELLED'}
        index = self.slot_index if self.slot_index >= 0 else track.active_insert_index
        if not (0 <= index < len(track.inserts)):
            return {'CANCELLED'}

        slot = track.inserts[index]
        presets_module.apply_params_to_insert_slot(slot, default_params_for(slot.effect_type))
        return {'FINISHED'}


class DAW_OT_ApplyMixerInsertPreset(Operator):
    bl_idname = "daw.apply_mixer_insert_preset"
    bl_label = "Aplicar Preset de Insert"
    bl_description = "Aplica um preset salvo aos parâmetros deste insert"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)
    preset_name: StringProperty(default="")

    def execute(self, context):
        track = _track_for(context, self.track_index)
        if track is None:
            return {'CANCELLED'}
        index = self.slot_index if self.slot_index >= 0 else track.active_insert_index
        if not (0 <= index < len(track.inserts)):
            return {'CANCELLED'}

        slot = track.inserts[index]
        params = presets_module.resolve_insert_params(slot.effect_type, self.preset_name)
        presets_module.apply_params_to_insert_slot(slot, params)
        self.report({'INFO'}, f"Preset '{self.preset_name}' aplicado")
        return {'FINISHED'}


class DAW_OT_SaveMixerInsertPreset(Operator):
    bl_idname = "daw.save_mixer_insert_preset"
    bl_label = "Salvar Preset de Insert"
    bl_description = "Salva os parâmetros atuais deste insert como um novo preset"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    slot_index: IntProperty(default=-1)
    preset_name: StringProperty(name="Nome do Preset", default="Meu Preset")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "preset_name")

    def execute(self, context):
        track = _track_for(context, self.track_index)
        if track is None:
            return {'CANCELLED'}
        index = self.slot_index if self.slot_index >= 0 else track.active_insert_index
        if not (0 <= index < len(track.inserts)):
            return {'CANCELLED'}

        slot = track.inserts[index]
        params = presets_module.insert_slot_params_to_dict(slot)
        ok = presets_module.save_user_insert_preset(slot.effect_type, self.preset_name, params)
        if ok:
            self.report({'INFO'}, f"Preset '{self.preset_name}' salvo")
        else:
            self.report({'ERROR'}, "Não foi possível salvar o preset")
        return {'FINISHED'} if ok else {'CANCELLED'}


# ---------------------------------------------------------------------- #
# Sends
# ---------------------------------------------------------------------- #
class DAW_OT_AddMixerSend(Operator):
    bl_idname = "daw.add_mixer_send"
    bl_label = "Adicionar Send"
    bl_description = "Adiciona um envio auxiliar da faixa para um bus"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    bus_name: StringProperty(default="")
    level: FloatProperty(default=0.0, min=0.0, max=1.0)

    def execute(self, context):
        mixer = _mixer(context)
        track = _track_for(context, self.track_index)
        if track is None:
            return {'CANCELLED'}

        if self.bus_name not in bus_names(mixer.buses):
            self.report({'ERROR'}, f"Bus '{self.bus_name}' não existe")
            return {'CANCELLED'}
        if not track.can_add_send():
            self.report({'WARNING'}, "Limite de sends por faixa atingido")
            return {'CANCELLED'}
        if track.get_send(self.bus_name) is not None:
            self.report({'WARNING'}, f"Já existe um envio para '{self.bus_name}'")
            return {'CANCELLED'}

        send = track.sends.add()
        send.bus_name = self.bus_name
        send.level = self.level
        track.active_send_index = len(track.sends) - 1
        return {'FINISHED'}


class DAW_OT_RemoveMixerSend(Operator):
    bl_idname = "daw.remove_mixer_send"
    bl_label = "Remover Send"
    bl_description = "Remove o envio selecionado da faixa"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    send_index: IntProperty(default=-1)

    def execute(self, context):
        track = _track_for(context, self.track_index)
        if track is None:
            return {'CANCELLED'}
        index = self.send_index if self.send_index >= 0 else track.active_send_index
        if not (0 <= index < len(track.sends)):
            return {'CANCELLED'}

        track.sends.remove(index)
        track.active_send_index = clamp_index(track.active_send_index, len(track.sends))
        return {'FINISHED'}


class DAW_OT_ToggleMixerSendPreFader(Operator):
    bl_idname = "daw.toggle_mixer_send_pre_fader"
    bl_label = "Pré-Fader"
    bl_description = "Alterna entre envio pré-fader e pós-fader"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    send_index: IntProperty(default=-1)

    def execute(self, context):
        track = _track_for(context, self.track_index)
        if track is None:
            return {'CANCELLED'}
        index = self.send_index if self.send_index >= 0 else track.active_send_index
        if not (0 <= index < len(track.sends)):
            return {'CANCELLED'}
        track.sends[index].pre_fader = not track.sends[index].pre_fader
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Presets de Channel Strip (faixa inteira)
# ---------------------------------------------------------------------- #
class DAW_OT_ApplyMixerStripPreset(Operator):
    bl_idname = "daw.apply_mixer_strip_preset"
    bl_label = "Aplicar Preset de Faixa"
    bl_description = "Aplica um preset de channel strip salvo à faixa selecionada"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    preset_name: StringProperty(default="")

    def execute(self, context):
        track = _track_for(context, self.track_index)
        if track is None:
            return {'CANCELLED'}
        ok = presets_module.apply_strip_preset(self.preset_name, track)
        if ok:
            self.report({'INFO'}, f"Preset '{self.preset_name}' aplicado")
        else:
            self.report({'ERROR'}, f"Preset '{self.preset_name}' não encontrado")
        return {'FINISHED'} if ok else {'CANCELLED'}


class DAW_OT_SaveMixerStripPreset(Operator):
    bl_idname = "daw.save_mixer_strip_preset"
    bl_label = "Salvar Preset de Faixa"
    bl_description = "Salva a faixa selecionada (volume, pan, inserts e sends) como preset"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(default=-1)
    preset_name: StringProperty(name="Nome do Preset", default="Minha Faixa")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "preset_name")

    def execute(self, context):
        track = _track_for(context, self.track_index)
        if track is None:
            return {'CANCELLED'}
        ok = presets_module.save_strip_preset(self.preset_name, track)
        if ok:
            self.report({'INFO'}, f"Preset '{self.preset_name}' salvo")
        else:
            self.report({'ERROR'}, "Não foi possível salvar o preset")
        return {'FINISHED'} if ok else {'CANCELLED'}


classes = [
    # Faixas
    DAW_OT_AddMixerTrack,
    DAW_OT_RemoveMixerTrack,
    DAW_OT_DuplicateMixerTrack,
    DAW_OT_MoveMixerTrack,
    DAW_OT_ToggleMixerTrackMute,
    DAW_OT_ToggleMixerTrackSolo,
    DAW_OT_ResetMixerTrack,
    DAW_OT_SetMixerTrackOutput,
    DAW_OT_ClearMixer,
    # Buses
    DAW_OT_AddMixerBus,
    DAW_OT_RemoveMixerBus,
    DAW_OT_ToggleMixerBusMute,
    # Inserts
    DAW_OT_AddMixerInsert,
    DAW_OT_RemoveMixerInsert,
    DAW_OT_MoveMixerInsert,
    DAW_OT_ToggleMixerInsertBypass,
    DAW_OT_ResetMixerInsert,
    DAW_OT_ApplyMixerInsertPreset,
    DAW_OT_SaveMixerInsertPreset,
    # Sends
    DAW_OT_AddMixerSend,
    DAW_OT_RemoveMixerSend,
    DAW_OT_ToggleMixerSendPreFader,
    # Presets de channel strip
    DAW_OT_ApplyMixerStripPreset,
    DAW_OT_SaveMixerStripPreset,
]