# modules/recorder/utils.py
"""
Utilitários do módulo Recorder.
"""
from __future__ import annotations

import math
import struct

import bpy
import numpy as np


# ---------------------------------------------------------------------------
# Exportação WAV (sem dependências externas além de numpy)
#
# Vive aqui (em vez de operators.py) porque tanto os operadores quanto a
# RecordingSession (recording.py) precisam gravar/regravar o .wav -- a
# sessão escreve o arquivo periodicamente durante a gravação, pra alimentar
# a strip "ao vivo" no VSE (ver create_or_update_live_strip abaixo).
# ---------------------------------------------------------------------------

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


def write_wav(filepath: str, data: np.ndarray, samplerate: int, bit_depth: str, channels: int = 1):
    """Escreve um arquivo WAV mono a partir de um array numpy float32 em [-1, 1].

    Suporta 16-bit PCM, 24-bit PCM e 32-bit float (IEEE), sem depender de
    bibliotecas externas como soundfile/scipy. Usado tanto pela exportação
    final quanto pelos "flushes" periódicos da gravação ao vivo -- nos dois
    casos o arquivo é reescrito do zero a partir do buffer acumulado, então
    é seguro chamar repetidamente no mesmo caminho.
    """
    if bit_depth == '16':
        fmt_tag = 1
        bits = 16
        payload = _float_to_pcm16(data)
    elif bit_depth == '24':
        fmt_tag = 1
        bits = 24
        payload = _float_to_pcm24(data)
    else:  # '32' -> float IEEE
        fmt_tag = 3
        bits = 32
        payload = _float_to_pcm32f(data)

    block_align = channels * (bits // 8)
    byte_rate = samplerate * block_align
    data_size = len(payload)

    tmp_path = filepath + ".tmp"
    with open(tmp_path, 'wb') as f:
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

    # Escreve em arquivo temporário e substitui via os.replace (atômico na
    # maioria dos SO's). Evita que o VSE tente ler o .wav no meio de uma
    # escrita durante os refreshes da strip ao vivo, o que corrompia o
    # cache de waveform ocasionalmente.
    import os
    os.replace(tmp_path, filepath)


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


def get_strips_collection(context):
    """Retorna a coleção de strips do sequencer (`.strips` ou `.sequences`)."""
    seq = get_sequencer(context)
    return getattr(seq, 'strips', None) or seq.sequences


def create_sound_strip(context, filepath: str, channel: int, frame_start: int, name: str | None = None):
    """Cria uma strip de áudio no sequencer.

    A partir do Blender 4.4, `SequenceEditor.sequences` foi renomeado
    para `SequenceEditor.strips` (breaking change do VSE). Tentamos o
    nome novo primeiro e caímos para o antigo para manter compatibilidade
    com versões anteriores.
    """
    strips = get_strips_collection(context)
    strip = strips.new_sound(
        name=name or f"Rec_{frame_start}",
        filepath=filepath,
        channel=channel,
        frame_start=frame_start,
    )
    return strip


def remove_strip_by_name(context, name: str) -> bool:
    """Remove uma strip pelo nome, se ela existir. Retorna True se removeu."""
    strips = get_strips_collection(context)
    strip = strips.get(name)
    if strip is None:
        return False
    old_sound = getattr(strip, 'sound', None)
    try:
        strips.remove(strip)
    finally:
        # Também remove o datablock de som órfão (a strip antiga é
        # recriada a cada refresh da gravação ao vivo -- ver
        # recording.py::create_or_update_live_strip -- então sem isso o
        # .blend acumularia um Sound não utilizado por refresh).
        if old_sound is not None and old_sound.users == 0:
            try:
                bpy.data.sounds.remove(old_sound)
            except Exception:
                pass
    return True


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