# modules/recorder/utils.py
"""
Utilitários do módulo Recorder.
"""
from __future__ import annotations

import math
import bpy


def frames_to_timecode(frame: int, fps: float = 24.0) -> str:
    total_seconds = frame / fps
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    frames = int(frame % fps)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def peak_to_db(peak: float) -> float:
    if peak <= 0.0:
        return -120.0
    return 20.0 * math.log10(peak)


def db_to_linear(db: float) -> float:
    return math.pow(10.0, db / 20.0)


def linear_to_db(linear: float) -> float:
    if linear <= 0.0:
        return -120.0
    return 20.0 * math.log10(linear)


def get_sequencer(context):
    """Retorna o sequencer do scene, se existir."""
    if not context.scene.sequence_editor:
        context.scene.sequence_editor_create()
    return context.scene.sequence_editor


def create_sound_strip(context, filepath: str, channel: int, frame_start: int):
    """Cria uma strip de áudio no sequencer.

    A partir do Blender 4.4, `SequenceEditor.sequences` foi renomeado
    para `SequenceEditor.strips` (breaking change do VSE). Tentamos o
    nome novo primeiro e caímos para o antigo para manter compatibilidade
    com versões anteriores.
    """
    seq = get_sequencer(context)
    strips = getattr(seq, 'strips', None) or seq.sequences
    strip = strips.new_sound(
        name=f"Rec_{frame_start}",
        filepath=filepath,
        channel=channel,
        frame_start=frame_start,
    )
    return strip


def ensure_recording_dir(context) -> str:
    """Garante que o diretório de gravação exista."""
    import os
    from pathlib import Path

    settings = context.scene.daw_recorder_settings
    path = bpy.path.abspath(settings.export_path)
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def get_armed_track_indices(context) -> list[int]:
    """Retorna índices das tracks armadas."""
    rec = context.scene.daw_recorder_settings
    return [item.track_index for item in rec.armed_tracks]


def is_track_armed(context, track_index: int) -> bool:
    return track_index in get_armed_track_indices(context)


def arm_track(context, track_index: int, name: str = ""):
    rec = context.scene.daw_recorder_settings
    for item in rec.armed_tracks:
        if item.track_index == track_index:
            return
    item = rec.armed_tracks.add()
    item.track_index = track_index
    item.name = name or f"Track {track_index}"


def disarm_track(context, track_index: int):
    rec = context.scene.daw_recorder_settings
    for i, item in enumerate(rec.armed_tracks):
        if item.track_index == track_index:
            rec.armed_tracks.remove(i)
            break


def disarm_all_tracks(context):
    rec = context.scene.daw_recorder_settings
    rec.armed_tracks.clear()


classes = []


def register():
    pass


def unregister():
    pass