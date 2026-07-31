# modules/vst/timeline_bridge.py
"""
Ponte entre o processamento de VST (dawdreamer) e a timeline nativa do
Blender (VSE — Video Sequence Editor).

Por que este arquivo existe:
    O Blender não expõe um callback de buffer de áudio em tempo real para
    plugins Python injetarem DSP durante o play — o motor de reprodução
    real é o `aud` (audaspace) tocando strips de som no Sequencer. Então,
    em vez de processar "ao vivo", este módulo faz o processamento do VST
    OFFLINE (bounce) e escreve o resultado como um arquivo .wav, que é
    inserido/atualizado como uma SOUND strip na timeline — exatamente como
    o resto do addon já faz (ver `ui/piano_roll.py`, `DAW_OT_RenderNotesToStrip`).

    A partir daí, quem toca o áudio é 100% o motor nativo do Blender.
    Isso precisa ser re-executado sempre que os parâmetros do VST, os
    presets, ou as notas MIDI mudarem — não é "ao vivo" no sentido de um
    plugin de DAW tradicional, é um bounce automático disparado por botão
    (ou, futuramente, por um handler de mudança de propriedade).

Convenções seguidas (iguais ao resto do projeto):
    - Diretório de renders: //daw_renders/vst/
    - Detecção de API do Sequencer (strips/strips_all vs sequences/sequences_all)
      compatível com Blender < 4.4 e >= 4.4.
"""
from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import bpy


# ═══════════════════════════════════════════════════════════════
#  BPM / TEMPO <-> FRAMES DO BLENDER
# ═══════════════════════════════════════════════════════════════

def get_bpm(scene) -> float:
    daw_props = getattr(scene, "daw", None)
    return float(daw_props.bpm) if daw_props else 120.0


def get_bpm_legacy_piano_roll(scene) -> float:
    """
    BPM conforme o Piano Roll "de verdade" do projeto (`ui/piano_roll.py`)
    o lê: `scene.beat_grid.bpm`. Essa propriedade NÃO é sincronizada com
    `scene.daw.bpm` em lugar nenhum do addon original — são duas fontes de
    BPM independentes. Para o bounce de instrumento VST bater com a
    posição/tempo que o usuário vê desenhado no Piano Roll, é esta função
    (e não `get_bpm`) que deve ser usada.
    """
    try:
        return float(scene.beat_grid.bpm)
    except Exception:
        return 120.0


def beat_to_frame(scene, beat: float) -> int:
    """Converte uma posição em beats para o frame correspondente do Blender."""
    bpm = get_bpm(scene)
    fps = scene.render.fps / max(scene.render.fps_base, 0.0001)
    seconds = beat * (60.0 / bpm)
    return scene.frame_start + int(round(seconds * fps))


def frame_to_beat(scene, frame: int) -> float:
    bpm = get_bpm(scene)
    fps = scene.render.fps / max(scene.render.fps_base, 0.0001)
    seconds = (frame - scene.frame_start) / fps
    return seconds * (bpm / 60.0)


# ═══════════════════════════════════════════════════════════════
#  LEITURA DE ÁUDIO (via `aud`, o motor nativo do Blender)
# ═══════════════════════════════════════════════════════════════

def read_audio_stereo(filepath: str, target_sample_rate: int = 44100):
    """
    Lê um arquivo de áudio (qualquer formato que o `aud`/Blender suporte —
    wav, mp3, ogg, flac...) usando o motor de áudio nativo do Blender, e
    devolve um numpy array estéreo (2, N) float32 na sample rate pedida.

    Levanta RuntimeError com mensagem amigável se `aud` não conseguir ler.
    """
    import numpy as np
    import aud

    try:
        sound = aud.Sound(filepath)
    except Exception as e:
        raise RuntimeError(f"Não foi possível abrir '{filepath}' via aud: {e}")

    try:
        rate, channels = sound.specs
    except Exception:
        rate, channels = target_sample_rate, 2

    if int(rate) != int(target_sample_rate) and hasattr(sound, "resample"):
        try:
            sound = sound.resample(target_sample_rate, True)
        except Exception:
            pass

    try:
        data = np.asarray(sound.data(), dtype=np.float32)
    except Exception as e:
        raise RuntimeError(
            f"Falha ao ler amostras de '{filepath}' via aud.Sound.data(): {e}"
        )

    # `aud.Sound.data()` retorna shape (n_amostras, n_canais).
    if data.ndim == 1:
        stereo = np.stack([data, data])
    else:
        if data.shape[1] == 1:
            mono = data[:, 0]
            stereo = np.stack([mono, mono])
        else:
            stereo = data[:, :2].T  # (2, N)

    return np.ascontiguousarray(stereo, dtype=np.float32)


# ═══════════════════════════════════════════════════════════════
#  ESCRITA DE WAV (PCM 16-bit estéreo, sem dependências externas)
# ═══════════════════════════════════════════════════════════════

def write_wav_stereo(path: str, audio, sample_rate: int = 44100) -> None:
    """
    Escreve um numpy array estéreo (2, N) ou (N, 2) float32 (-1.0..1.0)
    como .wav PCM 16-bit, no mesmo estilo do `_write_wav` já usado em
    `ui/piano_roll.py`, mas em estéreo.
    """
    import numpy as np

    arr = np.asarray(audio, dtype=np.float32)
    if arr.ndim == 1:
        arr = np.stack([arr, arr])
    if arr.shape[0] != 2 and arr.shape[-1] == 2:
        arr = arr.T

    left, right = arr[0], arr[1]
    n = min(len(left), len(right))
    interleaved = np.empty(n * 2, dtype=np.float32)
    interleaved[0::2] = left[:n]
    interleaved[1::2] = right[:n]

    clipped = np.clip(interleaved, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    data = pcm.tobytes()

    ds = len(data)
    hdr = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + ds, b'WAVE', b'fmt ', 16,
        1, 2, sample_rate, sample_rate * 4, 4, 16, b'data', ds,
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(hdr)
        f.write(data)


# ═══════════════════════════════════════════════════════════════
#  SEQUENCER — criação/atualização de SOUND strips
# ═══════════════════════════════════════════════════════════════

def get_all_strips(seq):
    """Compatível com Blender < 4.4 (`sequences_all`) e >= 4.4 (`strips_all`)."""
    if seq is None:
        return []
    strips = getattr(seq, 'strips_all', None)
    if strips is not None:
        return strips
    return getattr(seq, 'sequences_all', [])


def find_free_channel(seq, min_channel: int = 1) -> int:
    used = {s.channel for s in get_all_strips(seq)}
    ch = min_channel
    while ch in used:
        ch += 1
    return ch


def upsert_sound_strip(scene, name: str, filepath: str, channel: int, frame_start: int):
    """
    Cria uma SOUND strip com este `name` no Sequencer, removendo uma
    anterior com o mesmo nome se existir (para permitir re-bounce).
    """
    seq = scene.sequence_editor_create()

    for s in list(get_all_strips(seq)):
        if s.name == name:
            try:
                seq.strips.remove(s)
            except Exception:
                try:
                    seq.sequences.remove(s)
                except Exception:
                    pass

    try:
        return seq.strips.new_sound(name=name, filepath=filepath, channel=channel, frame_start=frame_start)
    except AttributeError:
        return seq.sequences.new_sound(name=name, filepath=filepath, channel=channel, frame_start=frame_start)


def find_strip_by_name(scene, name: str):
    seq = scene.sequence_editor
    for s in get_all_strips(seq):
        if s.name == name:
            return s
    return None


# ═══════════════════════════════════════════════════════════════
#  BOUNCE — INSTRUMENTO (notas MIDI -> áudio -> strip)
# ═══════════════════════════════════════════════════════════════

def render_instrument_notes(
    live_vst,
    notes: Sequence[Tuple[int, float, float, int]],
    duration: float,
    sample_rate: int = 44100,
):
    """
    Renderiza notas MIDI através de um VST instrumento (`live_vst`, um
    objeto `VST` já carregado) e devolve o áudio estéreo (numpy array).
    """
    if not notes:
        raise ValueError("Nenhuma nota para renderizar")
    return live_vst.render_instrument(notes, duration)


def notes_from_piano_roll(scene, sample_rate: int = 44100):
    """
    Lê as notas do editor Piano Roll modular (`scene.daw_piano_roll.notes`)
    e converte para o formato esperado por `render_instrument`:
    (pitch, start_seconds, duration_seconds, velocity_midi_0_127).

    Retorna (notes, duration_total_segundos).

    ATENÇÃO: este NÃO é o editor onde as notas normalmente são desenhadas
    neste addon — esse é `scene.piano_roll` (ver `notes_from_legacy_piano_roll`
    abaixo). Esta função existe apenas caso o módulo `modules/piano_roll`
    passe a ser o editor principal no futuro.
    """
    pr = getattr(scene, "daw_piano_roll", None)
    if pr is None or not len(pr.notes):
        return [], 0.0

    bpm = get_bpm(scene)
    sec_per_beat = 60.0 / bpm

    notes: List[Tuple[int, float, float, int]] = []
    max_end = 0.0
    for n in pr.notes:
        if n.muted:
            continue
        start_sec = n.start_beat * sec_per_beat
        dur_sec = max(n.duration_beats * sec_per_beat, 0.02)
        velocity = max(1, min(127, int(round(n.velocity * 127))))
        notes.append((n.pitch, start_sec, dur_sec, velocity))
        max_end = max(max_end, start_sec + dur_sec)

    return notes, max_end + 1.0  # +1s de cauda


def notes_from_legacy_piano_roll(scene, sample_rate: int = 44100):
    """
    Lê as notas do Piano Roll REAL do projeto (`ui/piano_roll.py`,
    `scene.piano_roll`) — o editor onde as notas são de fato desenhadas,
    tocadas e associadas a um strip do Sequencer via `state.active_strip`.

    Segue exatamente a mesma convenção de `DAW_OT_RenderNotesToStrip`
    (o bounce nativo já existente naquele arquivo): mesmas notas, mesmo
    BPM (`scene.beat_grid.bpm`), mesmo nome de strip.

    Retorna (notes, duration_total_segundos, strip_name, frame_start).
    `frame_start` é herdado do strip existente com o mesmo nome no
    Sequencer, se houver — senão cai em `scene.frame_start`, igual ao
    comportamento original.
    """
    state = getattr(scene, "piano_roll", None)
    if state is None:
        return [], 0.0, "PianoRoll", scene.frame_start

    # Mesma lógica de `_get_active_notes()` de ui/piano_roll.py.
    raw_notes = state.notes
    if state.active_strip:
        for ms in state.midi_strips:
            if ms.strip_name == state.active_strip:
                raw_notes = ms.notes
                break

    if not len(raw_notes):
        return [], 0.0, (state.active_strip or "PianoRoll"), scene.frame_start

    bpm = get_bpm_legacy_piano_roll(scene)
    sec_per_beat = 60.0 / bpm

    notes: List[Tuple[int, float, float, int]] = []
    max_end = 0.0
    for n in raw_notes:
        start_sec = n.start * sec_per_beat
        dur_sec = max(n.length * sec_per_beat, 0.03)
        velocity = max(1, min(127, int(n.velocity)))  # já é 1-127, sem reescalar
        notes.append((n.pitch, start_sec, dur_sec, velocity))
        max_end = max(max_end, start_sec + dur_sec)

    strip_name = state.active_strip or "PianoRoll"

    # Herda o frame_start do strip existente com esse nome, igual ao
    # comportamento original de DAW_OT_RenderNotesToStrip.
    seq = scene.sequence_editor
    frame_start = scene.frame_start
    for s in get_all_strips(seq):
        if s.name == strip_name:
            frame_start = s.frame_start
            break

    return notes, max_end + 1.0, strip_name, frame_start


# ═══════════════════════════════════════════════════════════════
#  BOUNCE — EFEITO (áudio de uma strip -> cadeia de VSTs -> nova strip)
# ═══════════════════════════════════════════════════════════════

def apply_effect_chain_to_audio(chain_items, get_live_vst_fn, audio, sample_rate: int = 44100):
    """
    Processa `audio` (numpy estéreo) através de todos os VSTs não-bypassed
    de `chain_items` (na ordem em que aparecem), encadeando a saída de um
    como entrada do próximo.
    """
    processed = audio
    for item in chain_items:
        if item.bypass or not item.is_loaded:
            continue
        live = get_live_vst_fn(item.vst_id)
        if live is None or not live.loaded:
            continue
        processed = live.process_effect(processed)
    return processed