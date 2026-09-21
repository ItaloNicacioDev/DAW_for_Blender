# modules/automation/runtime.py
"""
Aplica a automação durante a reprodução.

O handler `frame_change_pre` (registrado em register.py) converte o frame atual
em segundos, avalia todos os clips da cena e escreve os valores nos parâmetros
do mixer (`scene.daw_mixer`).

Alvos suportados (chave `target_param` da curva):
    master.volume            -> volume master (0..2)
    channel.N.volume|pan|mute  (ou track.N....) -> faixa N do mixer
    volume | pan | mute        -> faixa ATIVA do mixer

A lógica de resolução/aplicação não depende de bpy (recebe o objeto do mixer),
então é testada fora do Blender.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .store import get_clips
from .utils import collect_params_at

_PARAM_LIMITS = {
    "volume": (0.0, 1.0),
    "pan": (-1.0, 1.0),
    "mute": (0.0, 1.0),
}
_EPSILON = 1e-5


def default_range(target_param: str) -> Tuple[float, float, float]:
    """(mínimo, máximo, valor padrão) sugeridos para a curva de um parâmetro."""
    key = (target_param or "").strip().lower()
    if key in ("master.volume", "master_volume"):
        return 0.0, 2.0, 0.85
    attr = key.split(".")[-1]
    if attr == "pan":
        return -1.0, 1.0, 0.0
    if attr == "volume":
        return 0.0, 1.0, 0.78
    return 0.0, 1.0, 0.5


def resolve_target(mixer, target_param: str) -> Optional[Tuple[Any, str, float, float]]:
    """Devolve (objeto, atributo, mínimo, máximo) ou None se não der pra resolver."""
    key = (target_param or "").strip().lower()
    if not key or mixer is None:
        return None

    if key in ("master.volume", "master_volume"):
        return mixer, "master_volume", 0.0, 2.0

    parts = key.split(".")
    tracks = getattr(mixer, "tracks", [])

    if len(parts) == 1 and parts[0] in _PARAM_LIMITS:
        idx = getattr(mixer, "active_track_index", -1)
        attr = parts[0]
    elif len(parts) == 3 and parts[0] in ("channel", "track") and parts[1].isdigit() and parts[2] in _PARAM_LIMITS:
        idx = int(parts[1])
        attr = parts[2]
    else:
        return None

    if not (0 <= idx < len(tracks)):
        return None
    lo, hi = _PARAM_LIMITS[attr]
    return tracks[idx], attr, lo, hi


def apply_params(mixer, params: Dict[str, float]) -> int:
    """Escreve os valores no mixer. Só mexe no que mudou (evita disparar
    callbacks de update à toa). Devolve quantos parâmetros mudaram."""
    changed = 0
    for key, value in params.items():
        target = resolve_target(mixer, key)
        if target is None:
            continue
        obj, attr, lo, hi = target
        if attr == "mute":
            new = bool(value > 0.5)
            if getattr(obj, attr) != new:
                setattr(obj, attr, new)
                changed += 1
            continue
        new = min(max(float(value), lo), hi)
        if abs(getattr(obj, attr) - new) > _EPSILON:
            setattr(obj, attr, new)
            changed += 1
    return changed


def frame_to_seconds(scene, frame: Optional[float] = None) -> float:
    fps = scene.render.fps / max(scene.render.fps_base, 0.0001)
    frame = scene.frame_current if frame is None else frame
    return frame / fps if fps else 0.0


def apply_at_seconds(scene, seconds: float) -> int:
    clips = get_clips(scene)
    if not clips:
        return 0
    params = collect_params_at(clips, seconds)
    if not params:
        return 0
    return apply_params(getattr(scene, "daw_mixer", None), params)


def apply_at_current_frame(scene) -> int:
    return apply_at_seconds(scene, frame_to_seconds(scene))