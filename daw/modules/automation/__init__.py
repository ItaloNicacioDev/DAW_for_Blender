# modules/automation/__init__.py
"""
Módulo de automação da DAW.

Responsabilidade:
    Permitir que parâmetros do mixer, instrumentos e efeitos variem ao longo
    do tempo de forma programada, desenhando curvas na timeline.

Arquitetura:
    interpolation.py  — funções matemáticas de interpolação (linear, bezier, LFO...)
    curves.py         — AutomationCurve: lista de ControlPoints + evaluate(t)
    clips.py          — AutomationClip: curva posicionada na timeline com start/duration
    generators.py     — fábrica de curvas comuns (fade, LFO, ramp, step)
    utils.py          — helpers: snap, sample_curve, apply_params_to_mixer
    properties.py     — PropertyGroups do Blender (estado da UI)
    operators.py      — Operators do Blender (ações de edição)
    ui.py             — Painéis do Blender
    register.py       — register() / unregister()

Uso no Scheduler (reprodução):
    from daw.modules.automation import AutomationClip
    from daw.modules.automation.utils import collect_params_at, apply_params_to_mixer

    params = collect_params_at(active_clips, current_time)
    apply_params_to_mixer(params, mixer)
"""
from __future__ import annotations

from .interpolation import InterpolationMode, interpolate, INTERPOLATION_ITEMS
from .curves import AutomationCurve, ControlPoint
from .clips import AutomationClip
from .generators import (
    generate_fade_in,
    generate_fade_out,
    generate_lfo,
    generate_ramp,
    generate_step,
)
from .utils import (
    collect_params_at,
    apply_params_to_mixer,
    sample_curve,
    find_point_at_time,
    quantize_time,
)
from .register import register, unregister

__all__ = [
    # Lógica
    "InterpolationMode", "interpolate", "INTERPOLATION_ITEMS",
    "ControlPoint", "AutomationCurve",
    "AutomationClip",
    # Geradores
    "generate_fade_in", "generate_fade_out",
    "generate_lfo", "generate_ramp", "generate_step",
    # Utils
    "collect_params_at", "apply_params_to_mixer",
    "sample_curve", "find_point_at_time", "quantize_time",
    # Blender
    "register", "unregister",
]