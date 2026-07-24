# modules/mixer/utils.py
"""
Utilitários do Mixer.

Responsabilidade:
    Funções auxiliares numéricas (conversão dB/linear, lei de pan, clamp),
    nomes/índices únicos e a ponte com o motor de áudio (daw.core.register)
    e entre o modelo puro (tracks.py/mixer.py) e as propriedades RNA
    (properties.py).
"""
from __future__ import annotations

import math
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .properties import MixerTrackProperties, MixerProperties
    from .tracks import MixerTrack


# ---------------------------------------------------------------------- #
# Numérico
# ---------------------------------------------------------------------- #
def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def clamp_index(index: int, length: int) -> int:
    """Restringe um índice ao range válido [0, length-1]. Retorna 0 se length <= 0."""
    if length <= 0:
        return 0
    return max(0, min(index, length - 1))


def db_to_linear(db: float) -> float:
    """Converte um valor em decibéis para ganho linear."""
    return 10.0 ** (db / 20.0)


def linear_to_db(linear: float, floor_db: float = -80.0) -> float:
    """Converte um ganho linear para decibéis (com piso para evitar log(0))."""
    linear = max(linear, 1e-6)
    return max(20.0 * math.log10(linear), floor_db)


def linear_pan_gains(pan: float) -> Tuple[float, float]:
    """
    Lei de pan de potência constante (constant power panning).
    pan: -1.0 (esquerda) .. 0.0 (centro) .. 1.0 (direita)
    Retorna (ganho_esquerda, ganho_direita).
    """
    pan = clamp(pan, -1.0, 1.0)
    angle = (pan + 1.0) * 0.25 * math.pi   # 0 .. pi/2
    return math.cos(angle), math.sin(angle)


def peak_to_meter_factor(peak: float) -> float:
    """Normaliza um valor de pico (0.0-1.0+) para desenho de barra de VU (0.0-1.0)."""
    return clamp(peak, 0.0, 1.0)


# ---------------------------------------------------------------------- #
# Nomes/índices únicos (RNA)
# ---------------------------------------------------------------------- #
def unique_track_name(mixer_props, base_name: str) -> str:
    """Garante que `base_name` seja único entre as faixas existentes."""
    existing = {t.name for t in mixer_props.tracks}
    if base_name not in existing:
        return base_name
    n = 2
    while f"{base_name} ({n})" in existing:
        n += 1
    return f"{base_name} ({n})"


def unique_bus_name(mixer_props, base_name: str) -> str:
    """Garante que `base_name` seja único entre os buses existentes."""
    existing = {b.name for b in mixer_props.buses}
    if base_name not in existing:
        return base_name
    n = 2
    while f"{base_name} ({n})" in existing:
        n += 1
    return f"{base_name} ({n})"


def any_solo_active(mixer_props) -> bool:
    """Verifica se alguma faixa está em modo solo (RNA)."""
    return any(t.solo for t in mixer_props.tracks)


def is_track_audible(track_props, solo_active: bool) -> bool:
    """Mesma regra de audibilidade do modelo puro, aplicada a uma faixa RNA."""
    if track_props.mute:
        return False
    if solo_active and not track_props.solo:
        return False
    return True


# ---------------------------------------------------------------------- #
# Ponte com o motor de áudio
# ---------------------------------------------------------------------- #
def get_engine():
    """
    Retorna a instância ativa do motor de áudio (ver daw/core/register.py),
    ou None se o motor não estiver disponível (modo local/simulado).
    """
    try:
        from ...core import register as core_register
        return core_register.get_engine()
    except Exception:
        return None


def push_volume_to_engine(track_index: int, volume: float) -> None:
    """Envia uma mudança de volume de faixa para o motor, se disponível."""
    engine = get_engine()
    if engine is None:
        return
    try:
        engine.set_volume(track_index, volume)
    except Exception:
        pass


def push_pan_to_engine(track_index: int, pan: float) -> None:
    """Envia uma mudança de pan de faixa para o motor, se disponível."""
    engine = get_engine()
    if engine is None:
        return
    try:
        engine.set_pan(track_index, pan)
    except Exception:
        pass


def push_mute_to_engine(track_index: int, mute: bool) -> None:
    engine = get_engine()
    if engine is None:
        return
    try:
        engine.set_mute(track_index, mute)
    except Exception:
        pass


def push_solo_to_engine(track_index: int, solo: bool) -> None:
    engine = get_engine()
    if engine is None:
        return
    try:
        engine.set_solo(track_index, solo)
    except Exception:
        pass


def push_master_volume_to_engine(volume: float) -> None:
    engine = get_engine()
    if engine is None:
        return
    try:
        engine.set_master_volume(volume)
    except Exception:
        pass


def read_engine_peaks() -> Optional[Tuple[float, float]]:
    """Lê os valores de pico L/R globais do motor, se disponível."""
    engine = get_engine()
    if engine is None:
        return None
    try:
        state = engine.get_state()
        if state is None:
            return None
        return float(state.peak_left), float(state.peak_right)
    except Exception:
        return None