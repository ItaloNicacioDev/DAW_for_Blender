# daw_engine/core/channel_rack_bridge.py
"""
Ponte entre o Channel Rack (scene.daw_channel_rack, módulo de UI em
daw/modules/channel_rack/) e o motor de áudio de verdade (Engine.mixer,
daw_engine/mixer/). Antes desta ponte, nenhuma das duas pontas sabia
que a outra existia:

  - `channel_rack.ChannelProperties.steps` (BoolVectorProperty) guarda
    quais passos do step sequencer estão ligados por canal -- mas
    nada tocava esses passos de verdade durante a reprodução.
  - `Engine.mixer` (ver engine.py) agora existe e sabe gerar áudio real
    via Synth, mas não tinha ideia de quando disparar uma nota nem de
    qual canal do Channel Rack ela deveria vir.
  - `ChannelProperties.meter_level` só era escrito por preview manual
    de amostra ou monitor de entrada (ver channel_rack/register.py) --
    nunca pelo que estava realmente tocando.

Chamado por `Engine._update()` a cada `frame_change_post`, só enquanto
`bpy.context.screen.is_animation_playing` é True.

Convenção adotada (documentada aqui por não haver um campo explícito
"steps por beat" no modelo de dados): 4 steps = 1 beat (semínima
dividida em 4 = fusa/16th note), que é o padrão de facto usado por
step sequencers no estilo FL Studio (16 steps = 1 compasso de 4/4).
"""
from __future__ import annotations

import wave
from typing import Dict, Optional

import bpy

STEPS_PER_BEAT = 4

# Nota fixa usada pro "trigger" de step (percussivo/one-shot) -- ainda
# não existe no modelo de dados um campo de pitch por canal/step (isso
# é responsabilidade de um trabalho futuro: mapear
# `ChannelProperties.instrument_type`/sample pra uma nota ou sample
# real). C4 é um valor neutro que soa em qualquer preset do Synth.
DEFAULT_TRIGGER_NOTE = 60
DEFAULT_VELOCITY = 100
NOTE_OFF_DELAY = 0.12  # segundos -- dá um "tap" percussivo padrão

# Tipos de canal cujo som vem do Synth interno via steps (ver
# mixer/mixer.py) -- os outros tipos (SAMPLER/AUDIO/DRUM) tocam pela
# engine nativa de áudio do VSE do Blender (strips de som), não pelo
# Synth, então não fazem sentido receber note_on/note_off daqui.
SYNTH_DRIVEN_TYPES = {"SYNTH", "MIDI"}
SAMPLE_DRIVEN_TYPES = {"SAMPLER", "AUDIO", "DRUM"}

# Estado de reprodução por cena (não por Engine, que é singleton único
# mas pode conviver com múltiplas cenas abertas)
_state_by_scene: Dict[str, dict] = {}

# Decaimento do medidor quando não há pico novo neste tick (mesma ideia
# de METER_DECAY_PER_TICK em channel_rack/register.py, só que agora
# aplicado ao nível REAL vindo do Mixer/dos arquivos de áudio)
METER_DECAY = 0.75

# Cache de leitores de WAV abertos, por filepath -- evita reabrir o
# arquivo a cada tick (frame_change_post pode disparar 24-60x/seg)
_wav_cache: Dict[str, "wave.Wave_read"] = {}
READ_WINDOW_FRAMES = 512  # ~10ms @ 48kHz -- suficiente pra um pico "instantâneo"


def _get_state(scene) -> dict:
    return _state_by_scene.setdefault(scene.name, {"last_abs_step": None})


def _sync_mixer_channels(engine, rack) -> None:
    """Garante que `engine.mixer` tem exatamente um Channel por canal
    do Channel Rack, na mesma ordem, e copia volume/pan/mute/solo pra
    lá -- assim o que você mexe no card do mixer (ver
    modules/channel_rack/mixer_strip_*.py) afeta o áudio de verdade."""
    mixer = engine.mixer
    wanted = len(rack.channels)

    # Canal 0 do Mixer é reservado (ver mixer/mixer.py) -- os canais do
    # Channel Rack ocupam os índices 1..N. Adiciona os que faltarem.
    while mixer.channel_count - 1 < wanted:
        mixer.add_channel(name=f"Channel Rack {mixer.channel_count}")

    # Remove os que sobrarem (canal do Rack foi apagado na UI)
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
    Mixer de volta em `ChannelProperties.meter_level`, com decaimento
    suave quando não há pico novo (mesma sensação de um VU meter de
    verdade)."""
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
#  Medidor pra canais SAMPLER/AUDIO/DRUM -- esses tocam pela engine de
#  áudio nativa do VSE (strips de som), não pelo Synth, então não tem
#  nenhum "Channel" do Mixer gerando o som. O jeito de mostrar um nível
#  REAL (não inventado) pra esse caso é ler a amostra de áudio no
#  próprio arquivo, exatamente na posição em que o playhead está --
#  é literalmente o mesmo trecho de PCM que está audível naquele
#  instante, só lido do arquivo em vez de interceptado do stream do
#  Blender (que não expõe uma torneira de análise em tempo real pra
#  strips de som do VSE).
#
#  LIMITAÇÃO CONHECIDA: só lê .wav (via módulo `wave` da stdlib, sem
#  dependência extra). Amostras em outros formatos (mp3/ogg/flac)
#  tocam normalmente pelo VSE, mas o medidor fica em 0 pra elas até
#  ganharem suporte (precisaria de um decoder extra tipo `soundfile`).
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

    if last_abs_step is None:
        # primeiro tick depois de apertar play -- não dispara nada
        # retroativo, só estabelece a referência
        state["last_abs_step"] = abs_step
    elif abs_step != last_abs_step:
        if abs_step < last_abs_step:
            # o playhead voltou (loop, ou o usuário reposicionou
            # enquanto tocava) -- reseta sem disparar nada pra evitar
            # uma rajada de notas "atrasadas" de um intervalo que não
            # faz mais sentido
            state["last_abs_step"] = abs_step
        else:
            # dispara cada step cruzado em ordem (cobre o caso de FPS
            # baixo/BPM alto pular mais de um step por frame) -- só
            # pra canais SYNTH/MIDI; SAMPLER/AUDIO/DRUM tocam pelo VSE
            # e são medidos por `_update_sample_meters`, não disparados
            # aqui.
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
            state["last_abs_step"] = abs_step

        # playhead do step grid (usado pelo overlay em
        # channel_rack/overlay.py e mixer_strip_draw.py, se algum dia
        # desenhar o passo atual)
        if rack.channels:
            rack.current_step = abs_step % max(1, rack.channels[0].step_count)

    _update_synth_meters(engine, rack)
    _update_sample_meters(scene, rack)


def reset(scene=None) -> None:
    """Limpa o estado de reprodução -- chame ao parar/rebobinar pra não
    disparar uma rajada de notas "perdidas" na próxima vez que apertar
    play. Se `scene` for None, limpa todas as cenas."""
    if scene is None:
        _state_by_scene.clear()
    else:
        _state_by_scene.pop(scene.name, None)


def close_wav_cache() -> None:
    """Fecha todos os arquivos WAV abertos pelo cache de leitura de
    nível -- chamar ao desligar a engine (evita handles de arquivo
    pendurados)."""
    for reader in _wav_cache.values():
        try:
            reader.close()
        except Exception:
            pass
    _wav_cache.clear()