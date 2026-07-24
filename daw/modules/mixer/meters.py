# modules/mixer/meters.py
"""
Medição de nível (VU meter) do Mixer.

Responsabilidade:
    Calcular peak/RMS em dB, aplicar decaimento (release) nos medidores
    e manter uma "ponte" opcional com a engine de áudio real
    (daw.daw_engine.ENGINE.mixer), sem quebrar caso a engine não esteja
    disponível (ex.: DLL/engine não iniciada, ou rodando fora do Blender).

Este módulo NÃO depende de tracks.py, inserts.py, sends.py, effects.py,
routing.py, utils.py ou mixer.py — é autocontido e só lê/escreve nos
PropertyGroups definidos em properties.py (MixerMeterProperties).
"""
from __future__ import annotations

import math
import time
from typing import Optional, Tuple

import bpy

# ---------------------------------------------------------------------- #
# Conversões dB <-> linear
# ---------------------------------------------------------------------- #
MIN_DB = -60.0
MAX_DB = 6.0


def linear_to_db(value: float) -> float:
    """Converte amplitude linear (0.0-~2.0) para dB, limitado em MIN_DB."""
    value = max(abs(value), 1e-6)
    db = 20.0 * math.log10(value)
    return max(db, MIN_DB)


def db_to_linear(db: float) -> float:
    """Converte dB para amplitude linear."""
    return 10.0 ** (db / 20.0)


def normalize_for_display(value: float) -> float:
    """
    Normaliza um valor linear (0.0-2.0) para 0.0-1.0 para uso direto em
    barras de progresso da UI (slider/factor), preservando clipping visual.
    """
    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------- #
# Amostragem de nível
# ---------------------------------------------------------------------- #
def _try_get_engine_mixer():
    """
    Tenta obter o Mixer real da engine de áudio pura em Python
    (daw.daw_engine.ENGINE.mixer). Retorna None se a engine não estiver
    disponível — o módulo continua funcional apenas com valores simulados
    a partir do estado dos próprios canais (volume/mute/solo).
    """
    try:
        from ...daw_engine import ENGINE  # daw/daw_engine
    except Exception:
        return None

    mixer = getattr(ENGINE, "mixer", None)
    return mixer


def _simulated_level(channel_props) -> Tuple[float, float]:
    """
    Nível simulado (sem áudio real) usado quando a engine não está rodando,
    apenas para os medidores não ficarem sempre vazios durante a edição.
    Retorna (peak_left, peak_right) em 0.0-1.0.
    """
    if not channel_props.is_audible:
        return 0.0, 0.0

    base = normalize_for_display(channel_props.volume * 0.5)
    pan = channel_props.pan
    left = base * min(1.0, 1.0 - max(pan, 0.0))
    right = base * min(1.0, 1.0 + min(pan, 0.0))
    return normalize_for_display(left), normalize_for_display(right)


def _real_level(channel_props) -> Optional[Tuple[float, float]]:
    """
    Tenta extrair nível real da engine para o canal, caso ele esteja
    vinculado (source_index >= 0) e a engine exponha um AudioMeter.
    Retorna None se não houver dado real disponível.
    """
    if channel_props.source_index < 0:
        return None

    mixer = _try_get_engine_mixer()
    if mixer is None:
        return None

    ch = mixer.get_channel(channel_props.source_index) if hasattr(mixer, "get_channel") else None
    if ch is None:
        return None

    meter = getattr(ch, "meter", None)
    if meter is None:
        return None

    peak = getattr(meter, "peak", None)
    if peak is None:
        return None

    return float(peak[0]), float(peak[1])


def sample_channel_level(channel_props) -> Tuple[float, float]:
    """Retorna (peak_left, peak_right) 0.0-1.0 para um canal, real ou simulado."""
    real = _real_level(channel_props)
    if real is not None:
        return real
    return _simulated_level(channel_props)


def sample_master_level(mixer_props) -> Tuple[float, float]:
    """Retorna (peak_left, peak_right) 0.0-1.0 para o master bus."""
    engine_mixer = _try_get_engine_mixer()
    if engine_mixer is not None:
        master = getattr(engine_mixer, "master", None)
        meter = getattr(master, "meter", None) if master is not None else None
        peak = getattr(meter, "peak", None) if meter is not None else None
        if peak is not None:
            return float(peak[0]), float(peak[1])

    # Fallback: soma simples dos canais audíveis, normalizada.
    total_l = 0.0
    total_r = 0.0
    for ch in mixer_props.channels:
        l, r = _simulated_level(ch)
        total_l += l
        total_r += r
    total_l *= mixer_props.master.volume
    total_r *= mixer_props.master.volume
    return normalize_for_display(total_l), normalize_for_display(total_r)


# ---------------------------------------------------------------------- #
# Aplicação de decaimento (release) e escrita nas propriedades
# ---------------------------------------------------------------------- #
def _apply_meter(meter_props, new_left: float, new_right: float, decay_per_second: float, dt: float) -> None:
    """Atualiza um MixerMeterProperties com ataque instantâneo e release suave."""
    decay = max(0.0, 1.0 - decay_per_second * dt)

    meter_props.peak_left = max(new_left, meter_props.peak_left * decay)
    meter_props.peak_right = max(new_right, meter_props.peak_right * decay)

    meter_props.rms_left = max(new_left * 0.7, meter_props.rms_left * decay)
    meter_props.rms_right = max(new_right * 0.7, meter_props.rms_right * decay)

    if new_left >= 0.999 or new_right >= 0.999:
        meter_props.clipping = True
        meter_props.peak_hold_left = 1.0
        meter_props.peak_hold_right = 1.0
    else:
        meter_props.peak_hold_left = max(new_left, meter_props.peak_hold_left * 0.999)
        meter_props.peak_hold_right = max(new_right, meter_props.peak_hold_right * 0.999)


def reset_meter(meter_props) -> None:
    """Zera um medidor (usado ao remover/adicionar canais ou parar o transporte)."""
    meter_props.peak_left = 0.0
    meter_props.peak_right = 0.0
    meter_props.peak_hold_left = 0.0
    meter_props.peak_hold_right = 0.0
    meter_props.rms_left = 0.0
    meter_props.rms_right = 0.0
    meter_props.clipping = False


def update_all_meters(mixer_props, dt: float) -> None:
    """Atualiza os medidores de todos os canais e do master de uma vez."""
    decay = mixer_props.meter_decay_speed

    for ch in mixer_props.channels:
        left, right = sample_channel_level(ch)
        _apply_meter(ch.meter, left, right, decay, dt)

    m_left, m_right = sample_master_level(mixer_props)
    _apply_meter(mixer_props.master.meter, m_left, m_right, decay, dt)


def clear_clip_indicators(mixer_props) -> None:
    """Limpa os indicadores de clipping de todos os canais e do master."""
    for ch in mixer_props.channels:
        ch.meter.clipping = False
    mixer_props.master.meter.clipping = False


# ---------------------------------------------------------------------- #
# Timer periódico (bpy.app.timers) — roda ~20x por segundo
# ---------------------------------------------------------------------- #
_METER_INTERVAL = 0.05  # segundos
_last_tick: Optional[float] = None
_timer_running = False


def _meter_tick() -> Optional[float]:
    global _last_tick

    now = time.monotonic()
    dt = _METER_INTERVAL if _last_tick is None else max(1e-3, now - _last_tick)
    _last_tick = now

    for scene in bpy.data.scenes:
        mixer_props = getattr(scene, "daw_mixer", None)
        if mixer_props is None or not mixer_props.meters_enabled:
            continue
        try:
            update_all_meters(mixer_props, dt)
        except Exception:
            # Nunca deixa o timer morrer por causa de um erro pontual de leitura.
            pass

    return _METER_INTERVAL


def start_meter_timer() -> None:
    """Inicia o timer de atualização dos medidores, se ainda não estiver rodando."""
    global _timer_running, _last_tick
    if _timer_running:
        return
    _last_tick = None
    if not bpy.app.timers.is_registered(_meter_tick):
        bpy.app.timers.register(_meter_tick, first_interval=_METER_INTERVAL, persistent=True)
    _timer_running = True


def stop_meter_timer() -> None:
    """Para o timer de atualização dos medidores."""
    global _timer_running
    if bpy.app.timers.is_registered(_meter_tick):
        bpy.app.timers.unregister(_meter_tick)
    _timer_running = False


def register() -> None:
    start_meter_timer()


def unregister() -> None:
    stop_meter_timer()