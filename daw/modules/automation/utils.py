# modules/automation/utils.py
"""
Utilitários para o módulo de automação.

Responsabilidade:
    Funções auxiliares sem dependência de bpy, usadas tanto pelos
    operadores quanto pela UI e pelo DSP.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .curves import AutomationCurve, ControlPoint
from .clips import AutomationClip
from .interpolation import InterpolationMode

if TYPE_CHECKING:
    pass


def find_point_at_time(
    curve: AutomationCurve,
    time:  float,
    tolerance: float = 0.01,
) -> Optional[int]:
    """
    Retorna o índice do ponto mais próximo de 'time' dentro da tolerância,
    ou None se nenhum estiver próximo o suficiente.
    Útil para clicar num ponto na UI sem precisar acertar o pixel exato.
    """
    closest_idx = None
    closest_dist = float("inf")
    for i, pt in enumerate(curve.points):
        dist = abs(pt.time - time)
        if dist < tolerance and dist < closest_dist:
            closest_dist = dist
            closest_idx = i
    return closest_idx


def quantize_time(time: float, grid: float) -> float:
    """Quantiza um tempo para o grid (em segundos). Ex: grid=0.25 → semínima."""
    if grid <= 0:
        return time
    return round(time / grid) * grid


def clip_overlaps(clips: List[AutomationClip], start: float, duration: float) -> bool:
    """Verifica se um intervalo [start, start+duration] conflita com algum clip existente."""
    end = start + duration
    for c in clips:
        if start < c.end and end > c.start:
            return True
    return False


def collect_params_at(
    clips: List[AutomationClip],
    time:  float,
) -> Dict[str, float]:
    """
    Retorna o dict de {param: valor} resultante de todos os clips ativos
    no instante dado. Se dois clips automatizam o mesmo parâmetro, o último
    da lista vence (camadas).
    """
    result: Dict[str, float] = {}
    for clip in clips:
        result.update(clip.evaluate(time))
    return result


def apply_params_to_mixer(params: Dict[str, float], mixer) -> None:
    """
    Aplica o dict de automação ao Mixer.

    Formato das chaves esperadas:
        "master.volume"     → mixer.set_master_volume(value)
        "channel.N.volume"  → mixer.set_volume(N, value)
        "channel.N.pan"     → mixer.set_pan(N, value)
        "bpm"               → via ENGINE (tratado fora)
    """
    for param, value in params.items():
        parts = param.split(".")
        try:
            if parts[0] == "master" and parts[1] == "volume":
                mixer.set_master_volume(value)

            elif parts[0] == "channel" and len(parts) >= 3:
                idx = int(parts[1])
                attr = parts[2]
                if attr == "volume":
                    mixer.set_volume(idx, value)
                elif attr == "pan":
                    mixer.set_pan(idx, value)
                elif attr == "mute":
                    mixer.set_mute(idx, bool(value > 0.5))

        except (IndexError, ValueError):
            pass    # ignora chaves malformadas silenciosamente


def curve_to_points_list(curve: AutomationCurve) -> List[Tuple[float, float]]:
    """Converte uma curva para lista de (time, value) — útil para desenhar na UI."""
    return [(p.time, p.value) for p in curve.points]


def sample_curve(
    curve: AutomationCurve,
    start: float,
    end:   float,
    steps: int = 100,
) -> List[Tuple[float, float]]:
    """
    Amostra a curva em N pontos uniformes entre start e end.
    Retorna lista de (time, value) — para desenhar a curva suavemente na UI.
    """
    if steps < 2:
        steps = 2
    result = []
    for i in range(steps):
        t = start + (end - start) * i / (steps - 1)
        result.append((t, curve.evaluate(t)))
    return result