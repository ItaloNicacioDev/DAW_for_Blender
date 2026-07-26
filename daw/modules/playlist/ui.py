# modules/playlist/ui.py
"""
Painéis de UI do Blender para o módulo Playlist.

Segue o padrão:
    - bl_space_type = 'SEQUENCE_EDITOR'
    - bl_category   = "DAW"
"""
from __future__ import annotations

import bpy
from bpy.types import Menu, Panel, UIList

from .utils import format_beat, format_time


# ---------------------------------------------------------------------- #
# Listas
# ---------------------------------------------------------------------- #
class DAW_UL_PlaylistTrackList(UIList):
    """Lista de faixas da playlist."""
    bl_idname = "DAW_UL_playlist_track_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        track = item
        row = layout.row(align=True)

        sub = row.row()
        sub.scale_x = 0.35
        sub.prop(track, "color", text="")

        row.prop(track, "name", text="", emboss=False)
        row.label(text=f"M{track.mixer_track_index}", icon='SPEAKER')
        row.prop(track, "muted", text="", icon='HIDE_ON' if track.muted else 'HIDE_OFF', emboss=False)
        row.prop(track, "solo", text="", icon='SOLO_ON' if track.solo else 'SOLO_OFF', emboss=False)


class DAW_UL_PlaylistClipList(UIList):
    """Lista de clips na timeline."""
    bl_idname = "DAW_UL_playlist_clip_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        clip = item
        row = layout.row(align=True)

        row.prop(clip, "selected", text="", icon='CHECKBOX_HLT' if clip.selected else 'CHECKBOX_DEHLT', emboss=False)
        row.label(text=clip.name, icon='SEQ_STRIP_DUPLICATE')
        row.label(text=f"T{clip.track_index}")
        row.label(text=f"@{clip.start_beat:.1f}")
        row.label(text=f"{clip.duration_beats:.1f}b")


class DAW_UL_PlaylistMarkerList(UIList):
    """Lista de marcadores."""
    bl_idname = "DAW_UL_playlist_marker_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        marker = item
        row = layout.row(align=True)

        sub = row.row()
        sub.scale_x = 0.35
        sub.prop(marker, "color", text="")

        row.prop(marker, "name", text="", emboss=False)
        row.label(text=f"{marker.beat:.1f}b", icon='MARKER')


# ---------------------------------------------------------------------- #
# Menus
# ---------------------------------------------------------------------- #
class DAW_MT_PLClipType(Menu):
    """Menu para escolher o tipo de clip."""
    bl_idname = "DAW_MT_pl_clip_type"
    bl_label = "Tipo de Clip"

    def draw(self, context):
        layout = self.layout
        for identifier, label, _desc in (("PATTERN", "Pattern", ""), ("AUDIO", "Áudio", ""), ("AUTOMATION", "Automação", "")):
            op = layout.operator("daw.pl_add_clip", text=label)
            op.clip_type = identifier


class DAW_MT_PLPlayback(Menu):
    """Menu de controle de playback."""
    bl_idname = "DAW_MT_pl_playback"
    bl_label = "Playback"

    def draw(self, context):
        layout = self.layout
        pb = context.scene.daw_playlist.playback

        row = layout.row(align=True)
        row.operator("daw.pl_play", text="Play", icon='PLAY')
        row.operator("daw.pl_pause", text="Pause", icon='PAUSE')
        row.operator("daw.pl_stop", text="Stop", icon='SNAP_FACE_CENTER')
        layout.separator()
        row = layout.row(align=True)
        row.operator("daw.pl_toggle_record", text="Record", icon='REC')
        row.prop(pb, "metronome_enabled", text="Metrônomo", icon='TIME')
        layout.separator()
        layout.prop(pb, "current_bpm")
        layout.prop(pb, "loop_enabled")
        if pb.loop_enabled:
            row = layout.row(align=True)
            row.prop(pb, "loop_start_beat", text="Início")
            row.prop(pb, "loop_end_beat", text="Fim")


# ---------------------------------------------------------------------- #
# Painéis
# ---------------------------------------------------------------------- #
class DAW_PT_Playlist(Panel):
    bl_label = "Playlist"
    bl_idname = "DAW_PT_playlist"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 7

    def draw(self, context):
        layout = self.layout
        pl = context.scene.daw_playlist
        pb = pl.playback

        # Transporte
        box = layout.box()
        row = box.row(align=True)
        row.operator("daw.pl_toggle_play", text="▶" if not pb.is_playing else "⏸", icon='PLAY' if not pb.is_playing else 'PAUSE')
        row.operator("daw.pl_stop", text="⏹", icon='SNAP_FACE_CENTER')
        row.operator("daw.pl_toggle_record", text="●", icon='REC')
        row.prop(pb, "metronome_enabled", text="", icon='TIME')

        row = box.row(align=True)
        row.label(text=f"{format_beat(pb.current_beat)}")
        row.label(text=f"{format_time(pb.current_beat, pb.current_bpm)}")

        row = box.row()
        row.prop(pb, "current_beat", text="Posição")
        row = box.row()
        row.prop(pb, "current_bpm", text="BPM")

        row = box.row(align=True)
        row.prop(pb, "loop_enabled", text="Loop", toggle=True)
        if pb.loop_enabled:
            row = box.row(align=True)
            row.prop(pb, "loop_start_beat", text="In")
            row.prop(pb, "loop_end_beat", text="Out")


class DAW_PT_PlaylistTracks(Panel):
    bl_label = "Faixas"
    bl_idname = "DAW_PT_playlist_tracks"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_playlist"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        pl = context.scene.daw_playlist

        row = layout.row()
        row.template_list(
            "DAW_UL_playlist_track_list", "",
            pl, "tracks",
            pl, "active_track_index",
            rows=4,
        )

        col = row.column(align=True)
        col.operator("daw.pl_add_track", text="", icon='ADD')
        col.operator("daw.pl_remove_track", text="", icon='REMOVE')
        col.separator()
        col.operator("daw.pl_move_track", text="", icon='TRIA_UP').direction = "UP"
        col.operator("daw.pl_move_track", text="", icon='TRIA_DOWN').direction = "DOWN"

        track = pl.active_track
        if track is not None:
            box = layout.box()
            box.prop(track, "mixer_track_index")
            box.prop(track, "height")
            box.prop(track, "locked")


class DAW_PT_PlaylistClips(Panel):
    bl_label = "Clips"
    bl_idname = "DAW_PT_playlist_clips"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_playlist"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        pl = context.scene.daw_playlist

        row = layout.row()
        row.template_list(
            "DAW_UL_playlist_clip_list", "",
            pl, "clips",
            pl, "active_clip_index",
            rows=5,
        )

        col = row.column(align=True)
        col.menu("DAW_MT_pl_clip_type", text="", icon='ADD')
        col.operator("daw.pl_remove_clip", text="", icon='REMOVE')
        col.separator()
        col.operator("daw.pl_split_clip", text="", icon='MOD_ARRAY')
        col.separator()
        col.operator("daw.pl_clear_clips", text="", icon='TRASH')

        # Seleção
        row = layout.row(align=True)
        row.operator("daw.pl_select_all_clips", text="Tudo")
        row.operator("daw.pl_deselect_all_clips", text="Nada")
        row.operator("daw.pl_delete_selected_clips", text="Excluir", icon='X')

        clip = pl.active_clip
        if clip is not None:
            box = layout.box()
            box.prop(clip, "name")
            box.prop(clip, "clip_type")
            row = box.row(align=True)
            row.prop(clip, "track_index")
            row.prop(clip, "start_beat")
            row.prop(clip, "duration_beats")
            box.prop(clip, "pattern_name")
            box.prop(clip, "audio_path")
            box.prop(clip, "muted")
            box.prop(clip, "locked")
            box.prop(clip, "use_color_override")
            if clip.use_color_override:
                box.prop(clip, "color_override")


class DAW_PT_PlaylistMarkers(Panel):
    bl_label = "Marcadores"
    bl_idname = "DAW_PT_playlist_markers"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_playlist"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        pl = context.scene.daw_playlist

        row = layout.row()
        row.template_list(
            "DAW_UL_playlist_marker_list", "",
            pl, "markers",
            pl, "active_marker_index",
            rows=4,
        )

        col = row.column(align=True)
        op = col.operator("daw.pl_add_marker", text="", icon='ADD')
        op.beat = pl.playback.current_beat
        col.operator("daw.pl_remove_marker", text="", icon='REMOVE')
        col.separator()
        col.operator("daw.pl_clear_markers", text="", icon='TRASH')

        marker = pl.active_marker
        if marker is not None:
            box = layout.box()
            box.prop(marker, "beat")


class DAW_PT_PlaylistView(Panel):
    bl_label = "Visualização"
    bl_idname = "DAW_PT_playlist_view"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_playlist"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        view = context.scene.daw_playlist.view

        box = layout.box()
        box.label(text="Zoom & Scroll", icon='VIEWZOOM')
        box.prop(view, "zoom_x")
        box.prop(view, "zoom_y")
        box.prop(view, "scroll_x")
        box.prop(view, "scroll_y")

        box = layout.box()
        box.label(text="Snap", icon='SNAP_GRID')
        box.prop(view, "snap_enabled")
        row = box.row()
        row.enabled = view.snap_enabled
        row.prop(view, "snap_division")
        row = box.row()
        row.enabled = view.snap_enabled
        row.prop(view, "snap_to_clips")
        row.prop(view, "snap_to_markers")

        box = layout.box()
        box.label(text="Opções", icon='SETTINGS')
        box.prop(view, "show_track_names")
        box.prop(view, "show_waveforms")
        box.prop(view, "show_grid")


classes = [
    DAW_UL_PlaylistTrackList,
    DAW_UL_PlaylistClipList,
    DAW_UL_PlaylistMarkerList,
    DAW_MT_PLClipType,
    DAW_MT_PLPlayback,
    DAW_PT_Playlist,
    DAW_PT_PlaylistTracks,
    DAW_PT_PlaylistClips,
    DAW_PT_PlaylistMarkers,
    DAW_PT_PlaylistView,
]