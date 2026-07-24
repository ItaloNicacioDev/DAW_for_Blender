# modules/playlist/selection.py
"""
Seleção de Clips na Playlist — sem dependência de bpy.

Responsabilidade:
    Gerenciar quais clips estão selecionados na timeline,
    permitir seleção por retângulo e operações em lote.
"""
from __future__ import annotations

from typing import List

from .clips import PlaylistClip


def select_all(clips: List[PlaylistClip]) -> None:
    for c in clips:
        c.selected = True


def deselect_all(clips: List[PlaylistClip]) -> None:
    for c in clips:
        c.selected = False


def invert_selection(clips: List[PlaylistClip]) -> None:
    for c in clips:
        c.selected = not c.selected


def select_in_range(clips: List[PlaylistClip],
                    beat_start: float, beat_end: float,
                    track_start: int = 0, track_end: int = 999,
                    add_to_selection: bool = False) -> None:
    """Seleciona clips dentro de um retângulo tempo x track."""
    if not add_to_selection:
        deselect_all(clips)
    for c in clips:
        if (beat_start <= c.start_beat < beat_end or
            beat_start < c.end_beat <= beat_end or
            (c.start_beat <= beat_start and c.end_beat >= beat_end)):
            if track_start <= c.track_index <= track_end:
                c.selected = True


def get_selected(clips: List[PlaylistClip]) -> List[PlaylistClip]:
    return [c for c in clips if c.selected]


def delete_selected(clips: List[PlaylistClip]) -> None:
    clips[:] = [c for c in clips if not c.selected]


def duplicate_selected(clips: List[PlaylistClip],
                       offset_beats: float = 4.0) -> List[PlaylistClip]:
    """Duplica os clips selecionados, retornando as cópias."""
    selected = get_selected(clips)
    new_clips = []
    for c in selected:
        dup = PlaylistClip(
            name=f"{c.name} (cópia)",
            clip_type=c.clip_type,
            track_index=c.track_index,
            start_beat=c.start_beat + offset_beats,
            duration_beats=c.duration_beats,
            pattern_name=c.pattern_name,
            audio_path=c.audio_path,
            automation_param=c.automation_param,
            content_offset_beats=c.content_offset_beats,
            color_override=c.color_override,
        )
        dup.selected = True
        c.selected = False
        new_clips.append(dup)
    return new_clips


def move_selected(clips: List[PlaylistClip],
                  delta_beats: float, delta_tracks: int) -> None:
    for c in clips:
        if c.selected and not c.locked:
            c.start_beat = max(0.0, c.start_beat + delta_beats)
            c.track_index = max(0, c.track_index + delta_tracks)