# modules/recorder/utils.py
"""
Utilitários do módulo Recorder.
"""
from __future__ import annotations

import math
import struct
import bpy
import numpy as np


# ═══════════════════════════════════════════════════════════════
#  ESCRITA DE WAV (compartilhado entre o export final em operators.py
#  e a gravação incremental ao vivo em live_strip.py)
# ═══════════════════════════════════════════════════════════════

def _float_to_pcm16(data: np.ndarray) -> bytes:
    clipped = np.clip(data, -1.0, 1.0)
    ints = (clipped * 32767.0).astype('<i2')
    return ints.tobytes()


def _float_to_pcm24(data: np.ndarray) -> bytes:
    clipped = np.clip(data, -1.0, 1.0)
    ints = (clipped * 8388607.0).astype(np.int32)
    out = bytearray(len(ints) * 3)
    for i, v in enumerate(ints):
        b = int(v).to_bytes(4, byteorder='little', signed=True)
        out[i * 3:i * 3 + 3] = b[:3]
    return bytes(out)


def _float_to_pcm32f(data: np.ndarray) -> bytes:
    return data.astype('<f4').tobytes()


def bit_depth_to_fmt(bit_depth: str):
    """Devolve (fmt_tag, bits) do cabeçalho WAV pro bit_depth escolhido
    nas configurações do Recorder ('16', '24' ou '32' = float)."""
    if bit_depth == '16':
        return 1, 16
    elif bit_depth == '32':
        return 3, 32  # IEEE float
    else:
        return 1, 24


def encode_pcm(data: np.ndarray, bit_depth: str) -> bytes:
    if bit_depth == '16':
        return _float_to_pcm16(data)
    elif bit_depth == '32':
        return _float_to_pcm32f(data)
    else:
        return _float_to_pcm24(data)


def write_wav(filepath: str, data: np.ndarray, samplerate: int, bit_depth: str, channels: int = 1):
    """Escreve um arquivo WAV mono a partir de um array numpy float32 em [-1, 1].

    Suporta 16-bit PCM, 24-bit PCM e 32-bit float (IEEE), sem depender de
    bibliotecas externas como soundfile/scipy.
    """
    fmt_tag, bits = bit_depth_to_fmt(bit_depth)
    payload = encode_pcm(data, bit_depth)

    block_align = channels * (bits // 8)
    byte_rate = samplerate * block_align
    data_size = len(payload)

    with open(filepath, 'wb') as f:
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + data_size))
        f.write(b'WAVE')
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))
        f.write(struct.pack('<H', fmt_tag))
        f.write(struct.pack('<H', channels))
        f.write(struct.pack('<I', samplerate))
        f.write(struct.pack('<I', byte_rate))
        f.write(struct.pack('<H', block_align))
        f.write(struct.pack('<H', bits))
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        f.write(payload)


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
    return get_sequencer_for_scene(context.scene)


def get_sequencer_for_scene(scene):
    """Equivalente a `get_sequencer(context)`, mas recebendo `scene`
    diretamente -- usado pela gravação ao vivo (RecordingSession), que
    roda dentro de `bpy.app.handlers.frame_change_post` e só recebe
    `scene`, sem `context` completo."""
    if not scene.sequence_editor:
        scene.sequence_editor_create()
    return scene.sequence_editor


def get_strips_collection(seq):
    """A partir do Blender 4.4, `SequenceEditor.sequences` foi renomeado
    para `SequenceEditor.strips`. Este helper centraliza o fallback
    entre as duas APIs, usado em todo o módulo recorder."""
    return getattr(seq, 'strips', None) or seq.sequences


def create_sound_strip(context, filepath: str, channel: int, frame_start: int):
    """Cria uma strip de áudio no sequencer."""
    seq = get_sequencer(context)
    strips = get_strips_collection(seq)
    strip = strips.new_sound(
        name=f"Rec_{frame_start}",
        filepath=filepath,
        channel=channel,
        frame_start=frame_start,
    )
    return strip


def ensure_recording_dir_for_scene(scene) -> str:
    """Equivalente a `ensure_recording_dir(context)`, mas recebendo
    `scene` diretamente -- usado por RecordingSession.start(), que
    roda a partir de um operator que já tem `scene` isolado, e
    precisa criar os arquivos ao vivo antes mesmo do primeiro frame
    capturado."""
    import os
    from pathlib import Path

    settings = scene.daw_recorder_settings
    path = bpy.path.abspath(settings.export_path)
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def ensure_recording_dir(context) -> str:
    """Garante que o diretório de gravação exista."""
    return ensure_recording_dir_for_scene(context.scene)


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