# modules/playlist/operators.py
"""
Operators do Blender para o módulo Playlist.

Responsabilidade:
    Ações de edição: gerenciar tracks, clips, marcadores,
    controle de playback (play/pause/stop/record/seek), e seleção.
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator

from .utils import clamp_index, unique_clip_name, format_beat


def _pl(context):
    return context.scene.daw_playlist


def _track_for(context, index: int = -1):
    pl = _pl(context)
    i = index if index >= 0 else pl.active_track_index
    if not (0 <= i < len(pl.tracks)):
        return None
    return pl.tracks[i]


def _clip_for(context, index: int = -1):
    pl = _pl(context)
    i = index if index >= 0 else pl.active_clip_index
    if not (0 <= i < len(pl.clips)):
        return None
    return pl.clips[i]


def _marker_for(context, index: int = -1):
    pl = _pl(context)
    i = index if index >= 0 else pl.active_marker_index
    if not (0 <= i < len(pl.markers)):
        return None
    return pl.markers[i]


# ---------------------------------------------------------------------- #
# Tracks
# ---------------------------------------------------------------------- #
class DAW_OT_PLAddTrack(Operator):
    bl_idname = "daw.pl_add_track"
    bl_label = "Adicionar Faixa"
    bl_description = "Adiciona uma nova faixa à playlist"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="Track")
    mixer_track_index: IntProperty(default=0, min=0)

    def execute(self, context):
        pl = _pl(context)
        track = pl.tracks.add()
        track.name = self.name
        track.mixer_track_index = self.mixer_track_index
        pl.active_track_index = len(pl.tracks) - 1
        return {'FINISHED'}


class DAW_OT_PLRemoveTrack(Operator):
    bl_idname = "daw.pl_remove_track"
    bl_label = "Remover Faixa"
    bl_description = "Remove a faixa selecionada e seus clips"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        pl = _pl(context)
        index = self.index if self.index >= 0 else pl.active_track_index
        if not (0 <= index < len(pl.tracks)):
            return {'CANCELLED'}

        # Remove clips desta track
        for i in reversed(range(len(pl.clips))):
            if pl.clips[i].track_index == index:
                pl.clips.remove(i)
            elif pl.clips[i].track_index > index:
                pl.clips[i].track_index -= 1

        pl.tracks.remove(index)
        pl.active_track_index = clamp_index(pl.active_track_index, len(pl.tracks))
        pl.active_clip_index = clamp_index(pl.active_clip_index, len(pl.clips))
        return {'FINISHED'}


class DAW_OT_PLMoveTrack(Operator):
    bl_idname = "daw.pl_move_track"
    bl_label = "Mover Faixa"
    bl_description = "Move a faixa para cima ou para baixo"
    bl_options = {'REGISTER', 'UNDO'}

    direction: StringProperty(default="UP")

    def execute(self, context):
        pl = _pl(context)
        index = pl.active_track_index
        target = index - 1 if self.direction == "UP" else index + 1
        if not (0 <= index < len(pl.tracks)) or not (0 <= target < len(pl.tracks)):
            return {'CANCELLED'}
        pl.tracks.move(index, target)
        pl.active_track_index = target
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Clips
# ---------------------------------------------------------------------- #
class DAW_OT_PLAddClip(Operator):
    bl_idname = "daw.pl_add_clip"
    bl_label = "Adicionar Clip"
    bl_description = "Adiciona um clip na timeline"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="Clip")
    clip_type: StringProperty(default="PATTERN")
    track_index: IntProperty(default=-1)
    start_beat: FloatProperty(default=0.0, min=0.0)
    duration_beats: FloatProperty(default=4.0, min=0.25)
    pattern_name: StringProperty(default="")

    def execute(self, context):
        pl = _pl(context)
        track_i = self.track_index if self.track_index >= 0 else pl.active_track_index
        if not (0 <= track_i < len(pl.tracks)):
            self.report({'WARNING'}, "Nenhuma faixa válida")
            return {'CANCELLED'}

        existing = {c.name for c in pl.clips}
        clip = pl.clips.add()
        clip.name = unique_clip_name(list(existing), self.name)
        clip.clip_type = self.clip_type
        clip.track_index = track_i
        clip.start_beat = self.start_beat
        clip.duration_beats = self.duration_beats
        clip.pattern_name = self.pattern_name
        pl.active_clip_index = len(pl.clips) - 1
        return {'FINISHED'}


class DAW_OT_PLRemoveClip(Operator):
    bl_idname = "daw.pl_remove_clip"
    bl_label = "Remover Clip"
    bl_description = "Remove o clip selecionado"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        pl = _pl(context)
        index = self.index if self.index >= 0 else pl.active_clip_index
        if not (0 <= index < len(pl.clips)):
            return {'CANCELLED'}
        pl.clips.remove(index)
        pl.active_clip_index = clamp_index(pl.active_clip_index, len(pl.clips))
        return {'FINISHED'}


class DAW_OT_PLMoveClip(Operator):
    bl_idname = "daw.pl_move_clip"
    bl_label = "Mover Clip"
    bl_description = "Move o clip para nova posição"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)
    new_start_beat: FloatProperty(default=0.0, min=0.0)
    new_track_index: IntProperty(default=-1, min=0)

    def execute(self, context):
        clip = _clip_for(context, self.index)
        if clip is None:
            return {'CANCELLED'}
        clip.start_beat = self.new_start_beat
        if self.new_track_index >= 0:
            clip.track_index = self.new_track_index
        return {'FINISHED'}


class DAW_OT_PLResizeClip(Operator):
    bl_idname = "daw.pl_resize_clip"
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


class DAW_OT_PLSplitClip(Operator):
    bl_idname = "daw.pl_split_clip"
    bl_label = "Dividir Clip"
    bl_description = "Divide o clip em dois no beat informado"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)
    at_beat: FloatProperty(default=0.0, min=0.0)

    def execute(self, context):
        pl = _pl(context)
        clip = _clip_for(context, self.index)
        if clip is None:
            return {'CANCELLED'}

        end_beat = clip.start_beat + clip.duration_beats
        if self.at_beat <= clip.start_beat or self.at_beat >= end_beat:
            self.report({'WARNING'}, "Ponto fora do clip")
            return {'CANCELLED'}

        first_dur = self.at_beat - clip.start_beat
        second_offset = clip.content_offset_beats + first_dur
        second_dur = end_beat - self.at_beat

        clip.duration_beats = first_dur

        new_clip = pl.clips.add()
        new_clip.name = f"{clip.name} (split)"
        new_clip.clip_type = clip.clip_type
        new_clip.track_index = clip.track_index
        new_clip.start_beat = self.at_beat
        new_clip.duration_beats = second_dur
        new_clip.pattern_name = clip.pattern_name
        new_clip.audio_path = clip.audio_path
        new_clip.automation_param = clip.automation_param
        new_clip.content_offset_beats = second_offset
        new_clip.color_override = tuple(clip.color_override) if clip.use_color_override else None

        pl.active_clip_index = len(pl.clips) - 1
        self.report({'INFO'}, "Clip dividido")
        return {'FINISHED'}


class DAW_OT_PLClearClips(Operator):
    bl_idname = "daw.pl_clear_clips"
    bl_label = "Limpar Clips"
    bl_description = "Remove todos os clips da playlist"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _pl(context).clips.clear()
        _pl(context).active_clip_index = 0
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Marcadores
# ---------------------------------------------------------------------- #
class DAW_OT_PLAddMarker(Operator):
    bl_idname = "daw.pl_add_marker"
    bl_label = "Adicionar Marcador"
    bl_description = "Adiciona um marcador na posição atual"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(default="Marcador")
    beat: FloatProperty(default=0.0, min=0.0)

    def execute(self, context):
        pl = _pl(context)
        marker = pl.markers.add()
        marker.name = self.name
        marker.beat = self.beat
        pl.active_marker_index = len(pl.markers) - 1
        return {'FINISHED'}


class DAW_OT_PLRemoveMarker(Operator):
    bl_idname = "daw.pl_remove_marker"
    bl_label = "Remover Marcador"
    bl_description = "Remove o marcador selecionado"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        pl = _pl(context)
        index = self.index if self.index >= 0 else pl.active_marker_index
        if not (0 <= index < len(pl.markers)):
            return {'CANCELLED'}
        pl.markers.remove(index)
        pl.active_marker_index = clamp_index(pl.active_marker_index, len(pl.markers))
        return {'FINISHED'}


class DAW_OT_PLClearMarkers(Operator):
    bl_idname = "daw.pl_clear_markers"
    bl_label = "Limpar Marcadores"
    bl_description = "Remove todos os marcadores"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _pl(context).markers.clear()
        _pl(context).active_marker_index = 0
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Playback / Transporte
# ---------------------------------------------------------------------- #
class DAW_OT_PLPlay(Operator):
    bl_idname = "daw.pl_play"
    bl_label = "Play"
    bl_description = "Inicia a reprodução"
    bl_options = {'REGISTER'}

    def execute(self, context):
        _pl(context).playback.is_playing = True
        return {'FINISHED'}


class DAW_OT_PLPause(Operator):
    bl_idname = "daw.pl_pause"
    bl_label = "Pause"
    bl_description = "Pausa a reprodução"
    bl_options = {'REGISTER'}

    def execute(self, context):
        _pl(context).playback.is_playing = False
        return {'FINISHED'}


class DAW_OT_PLStop(Operator):
    bl_idname = "daw.pl_stop"
    bl_label = "Stop"
    bl_description = "Para a reprodução e volta ao início"
    bl_options = {'REGISTER'}

    def execute(self, context):
        pb = _pl(context).playback
        pb.is_playing = False
        pb.is_recording = False
        pb.current_beat = 0.0
        return {'FINISHED'}


class DAW_OT_PLTogglePlay(Operator):
    bl_idname = "daw.pl_toggle_play"
    bl_label = "Play/Pause"
    bl_description = "Alterna entre play e pause"
    bl_options = {'REGISTER'}

    def execute(self, context):
        pb = _pl(context).playback
        pb.is_playing = not pb.is_playing
        return {'FINISHED'}


class DAW_OT_PLToggleRecord(Operator):
    bl_idname = "daw.pl_toggle_record"
    bl_label = "Record"
    bl_description = "Alterna gravação"
    bl_options = {'REGISTER'}

    def execute(self, context):
        pb = _pl(context).playback
        pb.is_recording = not pb.is_recording
        if pb.is_recording:
            pb.is_playing = True
        return {'FINISHED'}


class DAW_OT_PLSeek(Operator):
    bl_idname = "daw.pl_seek"
    bl_label = "Seek"
    bl_description = "Move o playhead para a posição informada"
    bl_options = {'REGISTER'}

    beat: FloatProperty(default=0.0, min=0.0)

    def execute(self, context):
        _pl(context).playback.current_beat = self.beat
        return {'FINISHED'}


class DAW_OT_PLSetLoop(Operator):
    bl_idname = "daw.pl_set_loop"
    bl_label = "Definir Loop"
    bl_description = "Define a região de loop"
    bl_options = {'REGISTER', 'UNDO'}

    start_beat: FloatProperty(default=0.0, min=0.0)
    end_beat: FloatProperty(default=16.0, min=0.25)

    def execute(self, context):
        pb = _pl(context).playback
        pb.loop_start_beat = self.start_beat
        pb.loop_end_beat = max(self.start_beat + 0.25, self.end_beat)
        pb.loop_enabled = True
        return {'FINISHED'}


class DAW_OT_PLToggleLoop(Operator):
    bl_idname = "daw.pl_toggle_loop"
    bl_label = "Loop"
    bl_description = "Ativa/desativa o loop"
    bl_options = {'REGISTER'}

    def execute(self, context):
        pb = _pl(context).playback
        pb.loop_enabled = not pb.loop_enabled
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Seleção
# ---------------------------------------------------------------------- #
class DAW_OT_PLSelectAllClips(Operator):
    bl_idname = "daw.pl_select_all_clips"
    bl_label = "Selecionar Todos"
    bl_description = "Seleciona todos os clips"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for clip in _pl(context).clips:
            clip.selected = True
        return {'FINISHED'}


class DAW_OT_PLDeselectAllClips(Operator):
    bl_idname = "daw.pl_deselect_all_clips"
    bl_label = "Desselecionar Todos"
    bl_description = "Desseleciona todos os clips"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for clip in _pl(context).clips:
            clip.selected = False
        return {'FINISHED'}


class DAW_OT_PLDeleteSelectedClips(Operator):
    bl_idname = "daw.pl_delete_selected_clips"
    bl_label = "Excluir Selecionados"
    bl_description = "Remove os clips selecionados"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pl = _pl(context)
        pl.clips = [c for c in pl.clips if not c.selected]
        pl.active_clip_index = clamp_index(pl.active_clip_index, len(pl.clips))
        return {'FINISHED'}


classes = [
    # Tracks
    DAW_OT_PLAddTrack,
    DAW_OT_PLRemoveTrack,
    DAW_OT_PLMoveTrack,
    # Clips
    DAW_OT_PLAddClip,
    DAW_OT_PLRemoveClip,
    DAW_OT_PLMoveClip,
    DAW_OT_PLResizeClip,
    DAW_OT_PLSplitClip,
    DAW_OT_PLClearClips,
    # Marcadores
    DAW_OT_PLAddMarker,
    DAW_OT_PLRemoveMarker,
    DAW_OT_PLClearMarkers,
    # Playback
    DAW_OT_PLPlay,
    DAW_OT_PLPause,
    DAW_OT_PLStop,
    DAW_OT_PLTogglePlay,
    DAW_OT_PLToggleRecord,
    DAW_OT_PLSeek,
    DAW_OT_PLSetLoop,
    DAW_OT_PLToggleLoop,
    # Seleção
    DAW_OT_PLSelectAllClips,
    DAW_OT_PLDeselectAllClips,
    DAW_OT_PLDeleteSelectedClips,
]