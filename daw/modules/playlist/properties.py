# modules/playlist/properties.py
"""
Propriedades RNA do Blender para o módulo Playlist.

Responsabilidade:
    Espelhar em PropertyGroups o estado da playlist: tracks, clips,
    marcadores, playback e configurações de snap/visualização.
    Fica em context.scene.daw_playlist.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .snapping import SNAP_ITEMS


# ------------------------------------------------------------------ #
# Track da playlist
# ------------------------------------------------------------------ #
class PlaylistTrackProperties(PropertyGroup):
    """Uma faixa da playlist — espelho RNA de tracks.PlaylistTrack."""

    name: StringProperty(name="Nome", default="Track 1")
    mixer_track_index: IntProperty(name="Mixer Track", default=0, min=0)
    color: FloatVectorProperty(
        name="Cor", subtype='COLOR', size=3,
        min=0.0, max=1.0, default=(0.6, 0.6, 0.6),
    )
    muted: BoolProperty(name="Mudo", default=False)
    solo: BoolProperty(name="Solo", default=False)
    locked: BoolProperty(name="Travado", default=False)
    height: IntProperty(name="Altura", default=40, min=20, max=200)


# ------------------------------------------------------------------ #
# Clip na playlist
# ------------------------------------------------------------------ #
class PlaylistClipProperties(PropertyGroup):
    """Um clip na timeline — espelho RNA de clips.PlaylistClip."""

    name: StringProperty(name="Nome", default="Clip")
    clip_type: EnumProperty(
        name="Tipo",
        items=(
            ("PATTERN", "Pattern", "Clip de pattern"),
            ("AUDIO", "Áudio", "Clip de áudio"),
            ("AUTOMATION", "Automação", "Clip de automação"),
        ),
        default="PATTERN",
    )

    track_index: IntProperty(name="Faixa", default=0, min=0)
    start_beat: FloatProperty(name="Início", default=0.0, min=0.0)
    duration_beats: FloatProperty(name="Duração", default=4.0, min=0.25)

    pattern_name: StringProperty(name="Pattern", default="")
    audio_path: StringProperty(name="Arquivo de Áudio", default="", subtype='FILE_PATH')
    automation_param: StringProperty(name="Parâmetro", default="")

    content_offset_beats: FloatProperty(name="Offset", default=0.0, min=0.0)

    muted: BoolProperty(name="Mudo", default=False)
    locked: BoolProperty(name="Travado", default=False)
    selected: BoolProperty(name="Selecionado", default=False)
    use_color_override: BoolProperty(name="Sobrescrever Cor", default=False)
    color_override: FloatVectorProperty(
        name="Cor Customizada", subtype='COLOR', size=3,
        min=0.0, max=1.0, default=(0.8, 0.8, 0.8),
    )

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.duration_beats


# ------------------------------------------------------------------ #
# Marcador
# ------------------------------------------------------------------ #
class TimelineMarkerProperties(PropertyGroup):
    """Um marcador na timeline."""

    name: StringProperty(name="Nome", default="Marcador")
    beat: FloatProperty(name="Posição (beats)", default=0.0, min=0.0)
    color: FloatVectorProperty(
        name="Cor", subtype='COLOR', size=3,
        min=0.0, max=1.0, default=(0.9, 0.3, 0.3),
    )


# ------------------------------------------------------------------ #
# Playback / Transporte
# ------------------------------------------------------------------ #
class PlaybackProperties(PropertyGroup):
    """Estado do transporte/playback."""

    is_playing: BoolProperty(name="Tocando", default=False)
    is_recording: BoolProperty(name="Gravando", default=False)

    current_beat: FloatProperty(name="Posição Atual", default=0.0, min=0.0)
    current_bpm: FloatProperty(name="BPM", default=120.0, min=1.0, max=999.0)

    time_signature_num: IntProperty(name="Compasso (num)", default=4, min=1, max=32)
    time_signature_den: IntProperty(name="Compasso (den)", default=4, min=1, max=32)

    loop_enabled: BoolProperty(name="Loop", default=False)
    loop_start_beat: FloatProperty(name="Loop Início", default=0.0, min=0.0)
    loop_end_beat: FloatProperty(name="Loop Fim", default=16.0, min=0.25)

    metronome_enabled: BoolProperty(name="Metrônomo", default=False)
    pre_roll_beats: FloatProperty(name="Pré-roll", default=0.0, min=0.0)


# ------------------------------------------------------------------ #
# Configurações de visualização
# ------------------------------------------------------------------ #
class PlaylistViewProperties(PropertyGroup):
    """Configurações de zoom e scroll da playlist."""

    zoom_x: FloatProperty(name="Zoom Horizontal", default=1.0, min=0.1, max=20.0)
    zoom_y: FloatProperty(name="Zoom Vertical", default=1.0, min=0.1, max=5.0)
    scroll_x: FloatProperty(name="Scroll X", default=0.0)
    scroll_y: FloatProperty(name="Scroll Y", default=0.0)

    snap_enabled: BoolProperty(name="Snap", default=True)
    snap_division: EnumProperty(name="Divisão", items=SNAP_ITEMS, default="BEAT")
    snap_to_clips: BoolProperty(name="Snap aos Clips", default=True)
    snap_to_markers: BoolProperty(name="Snap aos Marcadores", default=True)

    show_track_names: BoolProperty(name="Nomes das Faixas", default=True)
    show_waveforms: BoolProperty(name="Waveforms", default=False)
    show_grid: BoolProperty(name="Grid", default=True)


# ------------------------------------------------------------------ #
# Estado global da Playlist
# ------------------------------------------------------------------ #
class PlaylistProperties(PropertyGroup):
    """Estado completo da Playlist para uma cena."""

    tracks: CollectionProperty(type=PlaylistTrackProperties)
    active_track_index: IntProperty(name="Faixa Ativa", default=0, min=0)

    clips: CollectionProperty(type=PlaylistClipProperties)
    active_clip_index: IntProperty(name="Clip Ativo", default=0, min=0)

    markers: CollectionProperty(type=TimelineMarkerProperties)
    active_marker_index: IntProperty(name="Marcador Ativo", default=0, min=0)

    playback: PointerProperty(type=PlaybackProperties)
    view: PointerProperty(type=PlaylistViewProperties)

    # ------------------------------------------------------------------
    # Conveniências
    # ------------------------------------------------------------------
    @property
    def active_track(self):
        if 0 <= self.active_track_index < len(self.tracks):
            return self.tracks[self.active_track_index]
        return None

    @property
    def active_clip(self):
        if 0 <= self.active_clip_index < len(self.clips):
            return self.clips[self.active_clip_index]
        return None

    @property
    def active_marker(self):
        if 0 <= self.active_marker_index < len(self.markers):
            return self.markers[self.active_marker_index]
        return None

    @property
    def selected_clips(self):
        return [c for c in self.clips if c.selected]

    def get_clips_on_track(self, track_index: int):
        return [c for c in self.clips if c.track_index == track_index]

    def get_clips_in_range(self, beat_start: float, beat_end: float):
        return [
            c for c in self.clips
            if not (c.end_beat <= beat_start or c.start_beat >= beat_end)
        ]


_ALL_CLASSES = [
    PlaylistTrackProperties,
    PlaylistClipProperties,
    TimelineMarkerProperties,
    PlaybackProperties,
    PlaylistViewProperties,
    PlaylistProperties,
]


def register() -> None:
    for cls in _ALL_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_playlist = bpy.props.PointerProperty(type=PlaylistProperties)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "daw_playlist"):
        del bpy.types.Scene.daw_playlist
    for cls in reversed(_ALL_CLASSES):
        bpy.utils.unregister_class(cls)