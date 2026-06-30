# modules/automation/generators.py
"""
Geradores de curvas de automação.

Responsabilidade:
    Criar AutomationCurves pré-preenchidas com formas comuns sem o usuário
    precisar colocar ponto a ponto. Usado por operadores de "Generate Automation".

Sem bpy — lógica pura.
"""
from __future__ import annotations

import math
from typing import Optional

from .curves import AutomationCurve
from .interpolation import InterpolationMode


def generate_ramp(
    target_param: str,
    start_val:  float,
    end_val:    float,
    duration:   float,
    min_val:    float = 0.0,
    max_val:    float = 1.0,
    mode:       InterpolationMode = InterpolationMode.LINEAR,
) -> AutomationCurve:
    """Curva de fade simples de start_val até end_val."""
    curve = AutomationCurve(target_param, min_val, max_val, start_val)
    curve.add_point(0.0,      start_val, mode)
    curve.add_point(duration, end_val,   mode)
    return curve


def generate_lfo(
    target_param: str,
    rate_hz:    float = 1.0,
    depth:      float = 0.5,
    center:     float = 0.5,
    duration:   float = 4.0,
    min_val:    float = 0.0,
    max_val:    float = 1.0,
    resolution: int   = 64,    # pontos por ciclo
    mode:       InterpolationMode = InterpolationMode.SINE,
) -> AutomationCurve:
    """
    LFO senoidal como curva de controle.

    rate_hz:    frequência do LFO em Hz
    depth:      amplitude (0.0 = nenhuma variação, 1.0 = range máximo)
    center:     valor central em [0, 1] normalizado para [min_val, max_val]
    resolution: pontos por ciclo (mais = mais suave, mais pesado)
    """
    curve = AutomationCurve(target_param, min_val, max_val, center)
    total_points = max(4, int(duration * rate_hz * resolution))
    center_abs   = min_val + center * (max_val - min_val)
    amplitude    = depth * (max_val - min_val) * 0.5

    for i in range(total_points + 1):
        t = duration * i / total_points
        v = center_abs + amplitude * math.sin(2.0 * math.pi * rate_hz * t)
        v = max(min_val, min(max_val, v))
        curve.add_point(t, v, mode)

    return curve


def generate_step(
    target_param: str,
    values:     list[float],
    step_duration: float = 0.25,
    min_val:    float = 0.0,
    max_val:    float = 1.0,
) -> AutomationCurve:
    """
    Sequência de degraus (valores constantes por step_duration segundos).

    Útil para automação de notas de escala, filtros em degrau, panning rítmico.
    """
    curve = AutomationCurve(target_param, min_val, max_val)
    for i, val in enumerate(values):
        t = i * step_duration
        curve.add_point(t, val, InterpolationMode.CONSTANT)
    # Último ponto mantém o último valor
    if values:
        curve.add_point(len(values) * step_duration, values[-1], InterpolationMode.CONSTANT)
    return curve


def generate_fade_in(
    target_param: str = "volume",
    duration: float   = 2.0,
    min_val:  float   = 0.0,
    max_val:  float   = 1.0,
) -> AutomationCurve:
    """Fade in de 0 até max_val."""
    return generate_ramp(target_param, min_val, max_val, duration,
                         min_val, max_val, InterpolationMode.EASE_OUT)


def generate_fade_out(
    target_param: str = "volume",
    duration: float   = 2.0,
    min_val:  float   = 0.0,
    max_val:  float   = 1.0,
) -> AutomationCurve:
    """Fade out de max_val até 0."""
    return generate_ramp(target_param, max_val, min_val, duration,
                         min_val, max_val, InterpolationMode.EASE_IN)