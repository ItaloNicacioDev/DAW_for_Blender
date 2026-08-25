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

from typing import Dict

STEPS_PER_BEAT = 4

# Nota fixa usada pro "trigger" de step (percussivo/one-shot) -- ainda
# não existe no modelo de dados um campo de pitch por canal/step (isso
# é responsabilidade de um trabalho futuro: mapear
# `ChannelProperties.instrument_type`/sample pra uma nota ou sample
# real). C4 é um valor neutro que soa em qualquer preset do Synth.
DEFAULT_TRIGGER_NOTE = 60
DEFAULT_VELOCITY = 100
NOTE_OFF_DELAY = 0.12  # segundos -- dá um "tap" percussivo padrão

# Estado de reprodução por cena (não por Engine, que é singleton único
# mas pode conviver com múltiplas cenas abertas)
_state_by_scene: Dict[str, dict] = {}

# Decaimento do medidor quando não há pico novo neste tick (mesma ideia
# de METER_DECAY_PER_TICK em channel_rack/register.py, só que agora
# aplicado ao nível REAL vindo do Mixer)
METER_DECAY = 0.75


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


def _update_meters(engine, rack) -> None:
    """Escreve o nível real (pós-fader) de cada canal do Mixer de volta
    em `ChannelProperties.meter_level`, com decaimento suave quando não
    há pico novo (mesma sensação de um VU meter de verdade)."""
    for i, ch in enumerate(rack.channels):
        mixer_ch = engine.mixer.get_channel(i + 1)
        if mixer_ch is None:
            continue
        real_peak = max(0.0, min(1.0, mixer_ch.last_peak))
        if real_peak > ch.meter_level:
            ch.meter_level = real_peak
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
            # baixo/BPM alto pular mais de um step por frame)
            for step in range(last_abs_step + 1, abs_step + 1):
                for i, ch in enumerate(rack.channels):
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

    _update_meters(engine, rack)


def reset(scene=None) -> None:
    """Limpa o estado de reprodução -- chame ao parar/rebobinar pra não
    disparar uma rajada de notas "perdidas" na próxima vez que apertar
    play. Se `scene` for None, limpa todas as cenas."""
    if scene is None:
        _state_by_scene.clear()
    else:
        _state_by_scene.pop(scene.name, None)