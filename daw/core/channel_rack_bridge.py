# daw_engine/core/channel_rack_bridge.py
"""
Ponte entre o Channel Rack + Patterns (módulos de UI em
daw/modules/channel_rack/ e daw/modules/patterns/) e o motor de áudio
de verdade (Engine.mixer, daw_engine/mixer/). Sem esta ponte, nenhuma
das pontas sabe que a outra existe:

  - `channel_rack.ChannelProperties.steps` (BoolVectorProperty) guarda
    quais passos do step sequencer estão ligados por canal -- grid
    simples de liga/desliga, sem pitch/velocity/duração por nota.
  - `scene.daw_patterns` (PatternsProperties) guarda patterns de
    verdade -- notas com pitch, velocity, posição e duração em beats,
    organizadas em clips posicionados na timeline (`PatternClipProperties.
    track_index` mapeia pro índice do canal do Channel Rack, mesma
    convenção 1:1 usada pro grid de steps) -- só que nada tocava esses
    patterns de verdade durante a reprodução, só o grid simples.
  - `channel_rack.vse_sync.py` já liga volume/pan/mute/solo às strips
    de som reais do VSE (canais SAMPLER/AUDIO/DRUM) -- esta ponte cobre
    o outro lado: canais SYNTH/MIDI tocando via Synth interno, e o
    medidor de nível de TODOS os tipos de canal.
  - `Engine.mixer` sabe gerar áudio real via Synth, mas não tinha ideia
    de quando disparar uma nota nem de qual canal ela deveria vir.
  - `ChannelProperties.meter_level` só era escrito por preview manual
    de amostra ou monitor de entrada (ver channel_rack/register.py) --
    nunca pelo que estava realmente tocando.

Chamado por `Engine._update()` a cada `frame_change_post`, só enquanto
`bpy.context.screen.is_animation_playing` é True.

Convenções adotadas (documentadas aqui por não haver campos explícitos
no modelo de dados):
  - Grid de steps: 4 steps = 1 beat (fusa/16th note), padrão de facto
    de step sequencers estilo FL Studio (16 steps = 1 compasso de 4/4).
  - Patterns: `steps_per_beat = pattern.length_steps / time_signature_num`
    (assume que `length_steps` cobre exatamente um compasso).
  - `PatternClipProperties.track_index` mapeia 1:1 pro índice de
    `rack.channels` -- mesma convenção do grid de steps.
"""
from __future__ import annotations

import wave
from typing import Dict, Optional

import bpy

STEPS_PER_BEAT = 4

# Nota fixa usada pro "trigger" do grid de steps (percussivo/one-shot,
# sem pitch próprio) -- os Patterns (abaixo) já usam o pitch real de
# cada nota.
DEFAULT_TRIGGER_NOTE = 60
DEFAULT_VELOCITY = 100
NOTE_OFF_DELAY = 0.12  # segundos -- dá um "tap" percussivo padrão

MAX_PATTERN_REPS_PER_TICK = 64  # trava de segurança contra loop infinito

# Tipos de canal cujo som vem do Synth interno (grid de steps OU
# patterns) -- os outros tipos (SAMPLER/AUDIO/DRUM) tocam pela engine
# nativa de áudio do VSE do Blender, controlados por vse_sync.py.
SYNTH_DRIVEN_TYPES = {"SYNTH", "MIDI"}
SAMPLE_DRIVEN_TYPES = {"SAMPLER", "AUDIO", "DRUM"}

_state_by_scene: Dict[str, dict] = {}

METER_DECAY = 0.75

_wav_cache: Dict[str, "wave.Wave_read"] = {}
READ_WINDOW_FRAMES = 512  # ~10ms @ 48kHz -- suficiente pra um pico "instantâneo"


def _get_state(scene) -> dict:
    return _state_by_scene.setdefault(scene.name, {"last_abs_step": None, "last_beat": None})


def _sync_mixer_channels(engine, rack) -> None:
    """Garante que `engine.mixer` tem exatamente um Channel por canal
    do Channel Rack, na mesma ordem, e copia volume/pan/mute/solo pra
    lá -- assim o que você mexe no card do mixer afeta o áudio de verdade."""
    mixer = engine.mixer
    wanted = len(rack.channels)

    # Canal 0 do Mixer é reservado -- os canais do Channel Rack ocupam
    # os índices 1..N.
    while mixer.channel_count - 1 < wanted:
        mixer.add_channel(name=f"Channel Rack {mixer.channel_count}")

    while mixer.channel_count - 1 > wanted:
        mixer.remove_channel(mixer.channel_count - 1)

    for i, ch in enumerate(rack.channels):
        mixer_idx = i + 1
        mixer.set_volume(mixer_idx, getattr(ch, "volume", 0.78))
        mixer.set_pan(mixer_idx, getattr(ch, "pan", 0.0))
        mixer.set_mute(mixer_idx, bool(ch.mute))
        mixer.set_solo(mixer_idx, bool(ch.solo))


def _update_synth_meters(engine, rack) -> None:
    """Escreve o nível real (pós-fader) de cada canal SYNTH/MIDI do
    Mixer de volta em `ChannelProperties.meter_level`."""
    for i, ch in enumerate(rack.channels):
        if ch.instrument_type not in SYNTH_DRIVEN_TYPES:
            continue
        mixer_ch = engine.mixer.get_channel(i + 1)
        if mixer_ch is None:
            continue
        real_peak = max(0.0, min(1.0, mixer_ch.last_peak))
        if real_peak > ch.meter_level:
            ch.meter_level = real_peak
        else:
            ch.meter_level = ch.meter_level * METER_DECAY


# ------------------------------------------------------------------ #
#  Medidor pra canais SAMPLER/AUDIO/DRUM -- lê o nível REAL direto do
#  arquivo de áudio, na posição exata do playhead (mesmo PCM que está
#  audível naquele instante). Só .wav por enquanto (stdlib `wave`).
# ------------------------------------------------------------------ #

def _get_wav_reader(filepath: str) -> Optional["wave.Wave_read"]:
    reader = _wav_cache.get(filepath)
    if reader is not None:
        return reader
    if not filepath.lower().endswith(".wav"):
        return None
    try:
        reader = wave.open(filepath, "rb")
    except Exception:
        return None
    _wav_cache[filepath] = reader
    return reader


def _find_sound_strip(scene, vse_channel: int, frame: int):
    seq_editor = getattr(scene, "sequence_editor", None)
    if seq_editor is None:
        return None
    for strip in seq_editor.sequences_all:
        if strip.type != 'SOUND':
            continue
        if strip.channel != vse_channel:
            continue
        if strip.frame_final_start <= frame < strip.frame_final_end:
            return strip
    return None


def _read_peak_from_wav(filepath: str, seconds_into_strip: float) -> float:
    reader = _get_wav_reader(filepath)
    if reader is None:
        return 0.0
    try:
        sr = reader.getframerate()
        sampwidth = reader.getsampwidth()
        n_channels = reader.getnchannels()
        n_frames = reader.getnframes()

        start_frame = max(0, int(seconds_into_strip * sr))
        if start_frame >= n_frames:
            return 0.0

        reader.setpos(start_frame)
        raw = reader.readframes(READ_WINDOW_FRAMES)
        if not raw:
            return 0.0

        import numpy as np
        if sampwidth == 2:
            data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 1:
            data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        elif sampwidth == 4:
            data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            return 0.0

        if n_channels > 1:
            data = data.reshape(-1, n_channels)

        return float(np.max(np.abs(data))) if data.size else 0.0
    except Exception:
        return 0.0


def _update_sample_meters(scene, rack) -> None:
    fps = scene.render.fps / max(scene.render.fps_base, 0.0001)
    if fps <= 0:
        return

    for ch in rack.channels:
        if ch.instrument_type not in SAMPLE_DRIVEN_TYPES:
            continue

        if ch.mute:
            ch.meter_level *= METER_DECAY
            continue

        strip = _find_sound_strip(scene, getattr(ch, "vse_channel", 1), scene.frame_current)
        if strip is None or not getattr(strip, "sound", None):
            ch.meter_level *= METER_DECAY
            continue

        filepath = bpy.path.abspath(strip.sound.filepath)
        strip_local_frame = scene.frame_current - strip.frame_final_start
        seconds_into_strip = (strip_local_frame / fps) + (getattr(strip, "frame_offset_start", 0) / fps)

        peak = _read_peak_from_wav(filepath, seconds_into_strip) * max(0.0, getattr(ch, "volume", 1.0))
        peak = max(0.0, min(1.0, peak))
        if peak > ch.meter_level:
            ch.meter_level = peak
        else:
            ch.meter_level = ch.meter_level * METER_DECAY


# ------------------------------------------------------------------ #
#  Grid de steps do Channel Rack -- percussivo, sem pitch próprio.
# ------------------------------------------------------------------ #
def _process_step_grid(engine, rack, last_abs_step: int, abs_step: int) -> None:
    for step in range(last_abs_step + 1, abs_step + 1):
        for i, ch in enumerate(rack.channels):
            if ch.instrument_type not in SYNTH_DRIVEN_TYPES:
                continue
            step_count = max(1, ch.step_count)
            local_step = step % step_count
            if ch.mute:
                continue
            try:
                active = bool(ch.steps[local_step])
            except IndexError:
                continue
            if not active:
                continue
            mixer_idx = i + 1
            engine.mixer.note_on(DEFAULT_TRIGGER_NOTE, DEFAULT_VELOCITY, mixer_idx)
            engine.scheduler.schedule(
                NOTE_OFF_DELAY, engine.mixer.note_off, DEFAULT_TRIGGER_NOTE, mixer_idx,
            )


# ------------------------------------------------------------------ #
#  Patterns (Piano Roll de verdade -- pitch/velocity/duração por nota,
#  clips posicionados em beats na timeline). Cobre notas melódicas de
#  verdade, ao contrário do grid de steps (que só liga/desliga um
#  "tap" percussivo fixo).
# ------------------------------------------------------------------ #
def _process_pattern_clips(engine, scene, rack, prev_beat: float, current_beat: float) -> None:
    patterns_props = getattr(scene, "daw_patterns", None)
    if patterns_props is None or current_beat <= prev_beat:
        return

    for clip in patterns_props.clips:
        if not clip.enabled:
            continue

        track_index = clip.track_index
        if track_index < 0 or track_index >= len(rack.channels):
            continue
        ch = rack.channels[track_index]
        if ch.instrument_type not in SYNTH_DRIVEN_TYPES or ch.mute:
            continue

        pattern = patterns_props.get_pattern_by_name(clip.pattern_name)
        if pattern is None or pattern.note_count == 0:
            continue

        clip_local_prev = prev_beat - clip.start_beat
        clip_local_cur = current_beat - clip.start_beat
        if clip_local_cur < 0:
            continue  # clip ainda não começou
        if not pattern.is_looping and clip_local_prev >= clip.duration_beats:
            continue  # clip já terminou e não repete

        steps_per_beat = pattern.length_steps / max(1, pattern.time_signature_num)
        if steps_per_beat <= 0:
            continue
        pattern_len_beats = pattern.length_steps / steps_per_beat  # == time_signature_num

        n_reps = 1
        if pattern.is_looping and pattern_len_beats > 0:
            n_reps = min(MAX_PATTERN_REPS_PER_TICK, int(clip_local_cur / pattern_len_beats) + 2)

        mixer_idx = track_index + 1

        for rep in range(max(1, n_reps)):
            rep_offset = rep * pattern_len_beats if pattern.is_looping else 0.0
            for note in pattern.notes:
                if not note.enabled:
                    continue

                note_beat_start = rep_offset + note.start_step / steps_per_beat
                note_beat_end = note_beat_start + note.duration_steps / steps_per_beat

                # corta no fim do clip (não deixa a última nota "vazar"
                # pra além de onde o clip termina na timeline)
                if note_beat_start >= clip.duration_beats:
                    continue
                note_beat_end = min(note_beat_end, clip.duration_beats)

                velocity = int(max(1, min(127, round(note.velocity * 127))))

                if clip_local_prev <= note_beat_start < clip_local_cur:
                    engine.mixer.note_on(note.pitch, velocity, mixer_idx)

                if clip_local_prev <= note_beat_end < clip_local_cur:
                    engine.mixer.note_off(note.pitch, mixer_idx)


def tick(engine, scene) -> None:
    rack = getattr(scene, "daw_channel_rack", None)
    if rack is None or len(rack.channels) == 0:
        return

    _sync_mixer_channels(engine, rack)

    transport_props = getattr(scene, "daw_transport", None)
    bpm = float(transport_props.bpm) if transport_props else 120.0
    bpm = max(1.0, bpm)

    fps = scene.render.fps / max(scene.render.fps_base, 0.0001)
    if fps <= 0:
        return
    seconds = scene.frame_current / fps
    beats = seconds * (bpm / 60.0)
    abs_step = int(beats * STEPS_PER_BEAT)

    state = _get_state(scene)
    last_abs_step = state["last_abs_step"]
    last_beat = state["last_beat"]

    if last_abs_step is None or last_beat is None:
        # primeiro tick depois de apertar play -- não dispara nada
        # retroativo, só estabelece a referência
        state["last_abs_step"] = abs_step
        state["last_beat"] = beats
    else:
        if abs_step < last_abs_step or beats < last_beat:
            # o playhead voltou (loop, ou o usuário reposicionou
            # enquanto tocava) -- reseta sem disparar nada
            state["last_abs_step"] = abs_step
            state["last_beat"] = beats
        else:
            if abs_step != last_abs_step:
                _process_step_grid(engine, rack, last_abs_step, abs_step)
                if rack.channels:
                    rack.current_step = abs_step % max(1, rack.channels[0].step_count)
                state["last_abs_step"] = abs_step

            _process_pattern_clips(engine, scene, rack, last_beat, beats)
            state["last_beat"] = beats

    _update_synth_meters(engine, rack)
    _update_sample_meters(scene, rack)


def reset(scene=None) -> None:
    """Limpa o estado de reprodução -- chame ao parar/rebobinar."""
    if scene is None:
        _state_by_scene.clear()
    else:
        _state_by_scene.pop(scene.name, None)


def close_wav_cache() -> None:
    """Fecha todos os arquivos WAV abertos pelo cache de leitura de nível."""
    for reader in _wav_cache.values():
        try:
            reader.close()
        except Exception:
            pass
    _wav_cache.clear()