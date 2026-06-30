"""Stub for automation/interpolation.py"""
# modules/automation/interpolation.py
"""
Tipos e funções de interpolação para curvas de automação.

Responsabilidade:
    Dado dois pontos de controle (t0, v0) e (t1, v1) e um t intermediário,
    retorna o valor interpolado segundo o modo escolhido.

    Nenhum acesso a bpy aqui — lógica pura reutilizável pelo DSP e pela UI.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Callable


class InterpolationMode(Enum):
    LINEAR      = "LINEAR"
    CONSTANT    = "CONSTANT"     # degrau — valor muda abruptamente no ponto seguinte
    BEZIER      = "BEZIER"       # suave, usa ease-in/out cúbico simples
    EASE_IN     = "EASE_IN"      # aceleração suave no início
    EASE_OUT    = "EASE_OUT"     # desaceleração suave no fim
    SINE        = "SINE"         # senoidal (útil para vibrato/tremolo)
    EXPONENTIAL = "EXPONENTIAL"  # crescimento/decaimento exponencial


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def interpolate(
    t0: float, v0: float,
    t1: float, v1: float,
    t:  float,
    mode: InterpolationMode = InterpolationMode.LINEAR,
) -> float:
    """
    Interpola entre (t0, v0) e (t1, v1) no instante t.

    Args:
        t0, v0: ponto inicial (tempo, valor)
        t1, v1: ponto final   (tempo, valor)
        t:      tempo alvo (pode estar fora de [t0, t1] — retorna extremo mais próximo)
        mode:   modo de interpolação

    Returns:
        Valor interpolado como float.
    """
    if t1 <= t0:
        return v1

    # Posição normalizada [0, 1] dentro do intervalo
    u = _clamp((t - t0) / (t1 - t0))

    if mode == InterpolationMode.CONSTANT:
        return v0

    elif mode == InterpolationMode.LINEAR:
        return v0 + (v1 - v0) * u

    elif mode == InterpolationMode.BEZIER:
        # Cúbica suave equivalente a smoothstep
        w = u * u * (3.0 - 2.0 * u)
        return v0 + (v1 - v0) * w

    elif mode == InterpolationMode.EASE_IN:
        w = u * u
        return v0 + (v1 - v0) * w

    elif mode == InterpolationMode.EASE_OUT:
        w = 1.0 - (1.0 - u) ** 2
        return v0 + (v1 - v0) * w

    elif mode == InterpolationMode.SINE:
        w = (1.0 - math.cos(u * math.pi)) * 0.5
        return v0 + (v1 - v0) * w

    elif mode == InterpolationMode.EXPONENTIAL:
        if u <= 0.0:
            return v0
        w = (math.exp(u * 4.0) - 1.0) / (math.exp(4.0) - 1.0)
        return v0 + (v1 - v0) * w

    return v0 + (v1 - v0) * u


# Mapa nome → função parcial — útil para a UI popular um EnumProperty
INTERPOLATION_ITEMS = [
    (m.value, m.value.replace("_", " ").title(), "")
    for m in InterpolationMode
]