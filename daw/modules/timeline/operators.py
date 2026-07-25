"""
timeline/operators.py
Operadores Blender (bpy.types.Operator) da timeline:
  - CRUD de tracks e clips
  - Mover / redimensionar clips (modal)
  - Transport (play / stop / record)
  - Zoom e scroll
  - Marcadores
  - Snapping toggle
"""

import bpy
from bpy.types import Operator
from bpy.props import IntProperty, FloatProperty, StringProperty, BoolProperty, EnumProperty

from .utils    import get_timeline, px_to_beat, beat_to_px, get_track_y_positions, track_at_y, get_track_color
from .cursor   import set_cursor_beat, begin_cursor_drag, update_cursor_drag, end_cursor_drag
from .markers  import add_marker, remove_marker, go_to_next_marker, go_to_prev_marker
from .snapping import apply_snap, snap_to_grid
from .playback import play, pause, stop, toggle_play, record, rewind_to_start, skip_forward, skip_backward
from .zoom     import zoom_in, zoom_out, zoom_to_fit, scroll_by_px, scroll_y_by, handle_wheel_zoom, handle_wheel_scroll


# ---------------------------------------------------------------------------
# Track operators
# ---------------------------------------------------------------------------

class DAW_OT_timeline_add_track(Operator):
    """Adiciona uma nova track à timeline"""
    bl_idname  = "daw.timeline_add_track"
    bl_label   = "Adicionar Track"
    bl_options = {"REGISTER", "UNDO"}

    track_type: EnumProperty(
        name="Tipo",
        items=[
            ("AUDIO", "Áudio", ""),
            ("MIDI",  "MIDI",  ""),
        ],
        default="AUDIO",
    )
    name: StringProperty(name="Nome", default="")

    def execute(self, context):
        tl = get_timeline(context)
        track = tl.tracks.add()
        idx   = len(tl.tracks) - 1
        track.name       = self.name or f"Track {idx + 1}"
        track.track_type = self.track_type
        track.color      = get_track_color(idx)
        tl.active_track_index = idx
        self.report({"INFO"}, f"Track '{track.name}' criada")
        return {"FINISHED"}


class DAW_OT_timeline_remove_track(Operator):
    """Remove a track ativa"""
    bl_idname  = "daw.timeline_remove_track"
    bl_label   = "Remover Track"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tl  = get_timeline(context)
        idx = tl.active_track_index
        if 0 <= idx < len(tl.tracks):
            tl.tracks.remove(idx)
            tl.active_track_index = max(0, idx - 1)
        return {"FINISHED"}


class DAW_OT_timeline_move_track(Operator):
    """Move a track ativa para cima ou para baixo"""
    bl_idname  = "daw.timeline_move_track"
    bl_label   = "Mover Track"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(
        name="Direção",
        items=[("UP", "Cima", ""), ("DOWN", "Baixo", "")],
        default="UP",
    )

    def execute(self, context):
        tl  = get_timeline(context)
        idx = tl.active_track_index
        if self.direction == "UP" and idx > 0:
            tl.tracks.move(idx, idx - 1)
            tl.active_track_index -= 1
        elif self.direction == "DOWN" and idx < len(tl.tracks) - 1:
            tl.tracks.move(idx, idx + 1)
            tl.active_track_index += 1
        return {"FINISHED"}


class DAW_OT_timeline_toggle_mute_track(Operator):
    """Mudo/desmudo a track ativa"""
    bl_idname  = "daw.timeline_toggle_mute_track"
    bl_label   = "Mutar Track"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tl    = get_timeline(context)
        idx   = tl.active_track_index
        if 0 <= idx < len(tl.tracks):
            tl.tracks[idx].muted = not tl.tracks[idx].muted
        return {"FINISHED"}


class DAW_OT_timeline_toggle_solo_track(Operator):
    """Solo na track ativa"""
    bl_idname  = "daw.timeline_toggle_solo_track"
    bl_label   = "Solo Track"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tl  = get_timeline(context)
        idx = tl.active_track_index
        if 0 <= idx < len(tl.tracks):
            tl.tracks[idx].solo = not tl.tracks[idx].solo
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Clip operators
# ---------------------------------------------------------------------------

class DAW_OT_timeline_add_clip(Operator):
    """Adiciona um clip na track ativa na posição do cursor"""
    bl_idname  = "daw.timeline_add_clip"
    bl_label   = "Adicionar Clip"
    bl_options = {"REGISTER", "UNDO"}

    length_beats: FloatProperty(name="Duração (beats)", default=4.0, min=0.25)
    clip_type:    EnumProperty(
        name="Tipo",
        items=[("AUDIO", "Áudio", ""), ("MIDI", "MIDI", "")],
        default="AUDIO",
    )

    def execute(self, context):
        tl  = get_timeline(context)
        idx = tl.active_track_index
        if not (0 <= idx < len(tl.tracks)):
            self.report({"WARNING"}, "Nenhuma track selecionada")
            return {"CANCELLED"}

        track = tl.tracks[idx]
        clip  = track.clips.add()
        clip.start_beat   = apply_snap(tl.cursor_beat, context)
        clip.length_beats = self.length_beats
        clip.clip_type    = self.clip_type
        clip.name         = f"Clip {len(track.clips)}"
        clip.color        = (*track.color[:3], 1.0)
        return {"FINISHED"}


class DAW_OT_timeline_remove_clip(Operator):
    """Remove o clip ativo da track"""
    bl_idname  = "daw.timeline_remove_clip"
    bl_label   = "Remover Clip"
    bl_options = {"REGISTER", "UNDO"}

    track_index: IntProperty(default=-1)
    clip_index:  IntProperty(default=-1)

    def execute(self, context):
        tl = get_timeline(context)
        ti = self.track_index if self.track_index >= 0 else tl.active_track_index
        if not (0 <= ti < len(tl.tracks)):
            return {"CANCELLED"}
        track = tl.tracks[ti]
        ci    = self.clip_index if self.clip_index >= 0 else track.active_clip_index
        if 0 <= ci < len(track.clips):
            track.clips.remove(ci)
            track.active_clip_index = max(0, ci - 1)
        return {"FINISHED"}


class DAW_OT_timeline_duplicate_clip(Operator):
    """Duplica clip selecionado logo após o original"""
    bl_idname  = "daw.timeline_duplicate_clip"
    bl_label   = "Duplicar Clip"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tl = get_timeline(context)
        for track in tl.tracks:
            for i, clip in enumerate(track.clips):
                if clip.selected:
                    new_clip = track.clips.add()
                    new_clip.name         = clip.name + " (cópia)"
                    new_clip.start_beat   = clip.start_beat + clip.length_beats
                    new_clip.length_beats = clip.length_beats
                    new_clip.clip_type    = clip.clip_type
                    new_clip.source_path  = clip.source_path
                    new_clip.color        = clip.color
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Modal: mover clip com o mouse
# ---------------------------------------------------------------------------

class DAW_OT_timeline_move_clip(Operator):
    """Move clip arrastando com o mouse (modal)"""
    bl_idname  = "daw.timeline_move_clip"
    bl_label   = "Mover Clip"
    bl_options = {"REGISTER", "UNDO"}

    track_index: IntProperty(default=0)
    clip_index:  IntProperty(default=0)

    def invoke(self, context, event):
        self._tl          = get_timeline(context)
        self._track_index = self.track_index
        self._clip_index  = self.clip_index
        track = self._tl.tracks[self.track_index]
        clip  = track.clips[self.clip_index]
        self._start_beat  = clip.start_beat
        self._mouse_start = event.mouse_x
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        tl    = self._tl
        pxb   = tl.pixels_per_beat * tl.zoom_level

        if event.type == "MOUSEMOVE":
            delta_px   = event.mouse_x - self._mouse_start
            delta_beat = delta_px / pxb if pxb > 0 else 0
            new_beat   = max(0.0, self._start_beat + delta_beat)
            new_beat   = apply_snap(new_beat, context)
            track = tl.tracks[self._track_index]
            clip  = track.clips[self._clip_index]
            clip.start_beat = new_beat
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
            return {"FINISHED"}

        elif event.type in {"RIGHTMOUSE", "ESC"}:
            # Cancela: restaura posição original
            track = tl.tracks[self._track_index]
            clip  = track.clips[self._clip_index]
            clip.start_beat = self._start_beat
            context.area.tag_redraw()
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}


# ---------------------------------------------------------------------------
# Modal: cursor drag
# ---------------------------------------------------------------------------

class DAW_OT_timeline_set_cursor(Operator):
    """Move o playhead clicando na régua (modal)"""
    bl_idname = "daw.timeline_set_cursor"
    bl_label  = "Mover Cursor"

    def invoke(self, context, event):
        tl     = get_timeline(context)
        beat   = px_to_beat(event.mouse_region_x - tl.track_header_width, tl)
        begin_cursor_drag(beat)
        set_cursor_beat(beat, context)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        tl = get_timeline(context)
        if event.type == "MOUSEMOVE":
            beat = px_to_beat(event.mouse_region_x - tl.track_header_width, tl)
            update_cursor_drag(beat, context)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        elif event.type == "LEFTMOUSE" and event.value == "RELEASE":
            end_cursor_drag()
            return {"FINISHED"}
        elif event.type in {"RIGHTMOUSE", "ESC"}:
            end_cursor_drag()
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}


# ---------------------------------------------------------------------------
# Transport operators
# ---------------------------------------------------------------------------

class DAW_OT_timeline_play(Operator):
    bl_idname = "daw.timeline_play"
    bl_label  = "Play"
    def execute(self, context):
        play(context); return {"FINISHED"}


class DAW_OT_timeline_pause(Operator):
    bl_idname = "daw.timeline_pause"
    bl_label  = "Pause"
    def execute(self, context):
        pause(context); return {"FINISHED"}


class DAW_OT_timeline_stop(Operator):
    bl_idname = "daw.timeline_stop"
    bl_label  = "Stop"
    def execute(self, context):
        stop(context); return {"FINISHED"}


class DAW_OT_timeline_toggle_play(Operator):
    bl_idname = "daw.timeline_toggle_play"
    bl_label  = "Play/Pause"
    def execute(self, context):
        toggle_play(context); return {"FINISHED"}


class DAW_OT_timeline_record(Operator):
    bl_idname = "daw.timeline_record"
    bl_label  = "Gravar"
    def execute(self, context):
        record(context); return {"FINISHED"}


class DAW_OT_timeline_rewind(Operator):
    bl_idname = "daw.timeline_rewind"
    bl_label  = "Rebobinar"
    def execute(self, context):
        rewind_to_start(context); return {"FINISHED"}


class DAW_OT_timeline_skip_forward(Operator):
    bl_idname   = "daw.timeline_skip_forward"
    bl_label    = "Avançar"
    beats: FloatProperty(default=4.0)
    def execute(self, context):
        skip_forward(self.beats, context); return {"FINISHED"}


class DAW_OT_timeline_skip_backward(Operator):
    bl_idname   = "daw.timeline_skip_backward"
    bl_label    = "Recuar"
    beats: FloatProperty(default=4.0)
    def execute(self, context):
        skip_backward(self.beats, context); return {"FINISHED"}


# ---------------------------------------------------------------------------
# Zoom operators
# ---------------------------------------------------------------------------

class DAW_OT_timeline_zoom_in(Operator):
    bl_idname = "daw.timeline_zoom_in"
    bl_label  = "Zoom +"
    def execute(self, context):
        zoom_in(context=context); return {"FINISHED"}


class DAW_OT_timeline_zoom_out(Operator):
    bl_idname = "daw.timeline_zoom_out"
    bl_label  = "Zoom -"
    def execute(self, context):
        zoom_out(context=context); return {"FINISHED"}


class DAW_OT_timeline_zoom_fit(Operator):
    bl_idname = "daw.timeline_zoom_fit"
    bl_label  = "Encaixar Tudo"
    def execute(self, context):
        zoom_to_fit(context=context); return {"FINISHED"}


# ---------------------------------------------------------------------------
# Marker operators
# ---------------------------------------------------------------------------

class DAW_OT_timeline_add_marker(Operator):
    bl_idname  = "daw.timeline_add_marker"
    bl_label   = "Adicionar Marcador"
    bl_options = {"REGISTER", "UNDO"}
    name: StringProperty(name="Nome", default="")
    def execute(self, context):
        add_marker(self.name, context=context)
        return {"FINISHED"}


class DAW_OT_timeline_remove_marker(Operator):
    bl_idname  = "daw.timeline_remove_marker"
    bl_label   = "Remover Marcador"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, context):
        remove_marker(context=context)
        return {"FINISHED"}


class DAW_OT_timeline_next_marker(Operator):
    bl_idname = "daw.timeline_next_marker"
    bl_label  = "Próximo Marcador"
    def execute(self, context):
        go_to_next_marker(context); return {"FINISHED"}


class DAW_OT_timeline_prev_marker(Operator):
    bl_idname = "daw.timeline_prev_marker"
    bl_label  = "Marcador Anterior"
    def execute(self, context):
        go_to_prev_marker(context); return {"FINISHED"}


# ---------------------------------------------------------------------------
# Snap toggle
# ---------------------------------------------------------------------------

class DAW_OT_timeline_toggle_snap(Operator):
    bl_idname  = "daw.timeline_toggle_snap"
    bl_label   = "Ativar/Desativar Snap"
    bl_options = {"REGISTER"}
    def execute(self, context):
        tl = get_timeline(context)
        tl.snap_enabled = not tl.snap_enabled
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------

CLASSES = [
    DAW_OT_timeline_add_track,
    DAW_OT_timeline_remove_track,
    DAW_OT_timeline_move_track,
    DAW_OT_timeline_toggle_mute_track,
    DAW_OT_timeline_toggle_solo_track,
    DAW_OT_timeline_add_clip,
    DAW_OT_timeline_remove_clip,
    DAW_OT_timeline_duplicate_clip,
    DAW_OT_timeline_move_clip,
    DAW_OT_timeline_set_cursor,
    DAW_OT_timeline_play,
    DAW_OT_timeline_pause,
    DAW_OT_timeline_stop,
    DAW_OT_timeline_toggle_play,
    DAW_OT_timeline_record,
    DAW_OT_timeline_rewind,
    DAW_OT_timeline_skip_forward,
    DAW_OT_timeline_skip_backward,
    DAW_OT_timeline_zoom_in,
    DAW_OT_timeline_zoom_out,
    DAW_OT_timeline_zoom_fit,
    DAW_OT_timeline_add_marker,
    DAW_OT_timeline_remove_marker,
    DAW_OT_timeline_next_marker,
    DAW_OT_timeline_prev_marker,
    DAW_OT_timeline_toggle_snap,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)