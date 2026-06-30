# modules/automation/curves.py
"""
Curva de automação: sequência de pontos de controle com interpolação.

Responsabilidade:
    Representar e avaliar uma curva de valores ao longo do tempo.
    Sem bpy — lógica pura, serializável para JSON.

Uso típico:
    curve = AutomationCurve(target_param="volume", min_val=0.0, max_val=1.0)
    curve.add_point(0.0, 0.8)
    curve.add_point(2.0, 0.3, InterpolationMode.BEZIER)
    curve.add_point(4.0, 1.0)

    value = curve.evaluate(1.5)  # → interpola entre 0.8 e 0.3
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .interpolation import InterpolationMode, interpolate


# ------------------------------------------------------------------
# Ponto de controle
# ------------------------------------------------------------------

@dataclass
class ControlPoint:
    """Um ponto na curva de automação."""
    time:   float                              # posição em segundos
    value:  float                              # valor no parâmetro alvo
    mode:   InterpolationMode = InterpolationMode.LINEAR  # interpolação até o próximo ponto

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time":  self.time,
            "value": self.value,
            "mode":  self.mode.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ControlPoint":
        return cls(
            time=data["time"],
            value=data["value"],
            mode=InterpolationMode(data.get("mode", InterpolationMode.LINEAR.value)),
        )


# ------------------------------------------------------------------
# Curva de automação
# ------------------------------------------------------------------

class AutomationCurve:
    """
    Curva de automação: lista ordenada de ControlPoints + metadados do parâmetro.

    target_param: nome do parâmetro alvo (ex: "volume", "pan", "bpm",
                  "synth.attack", "channel.0.volume"...)
    """

    def __init__(
        self,
        target_param: str   = "",
        min_val:      float = 0.0,
        max_val:      float = 1.0,
        default_val:  float = 0.0,
    ) -> None:
        self.target_param = target_param
        self.min_val      = min_val
        self.max_val      = max_val
        self.default_val  = default_val
        self.enabled:     bool = True
        self._points:     List[ControlPoint] = []

    # ------------------------------------------------------------------
    # Edição de pontos
    # ------------------------------------------------------------------

    def add_point(
        self,
        time:  float,
        value: float,
        mode:  InterpolationMode = InterpolationMode.LINEAR,
    ) -> ControlPoint:
        """Adiciona um ponto e mantém a lista ordenada por tempo."""
        value = max(self.min_val, min(self.max_val, value))
        pt = ControlPoint(time=time, value=value, mode=mode)
        self._points.append(pt)
        self._points.sort(key=lambda p: p.time)
        return pt

    def remove_point(self, index: int) -> bool:
        if 0 <= index < len(self._points):
            self._points.pop(index)
            return True
        return False

    def move_point(self, index: int, new_time: float, new_value: float) -> None:
        if 0 <= index < len(self._points):
            new_value = max(self.min_val, min(self.max_val, new_value))
            self._points[index].time  = new_time
            self._points[index].value = new_value
            self._points.sort(key=lambda p: p.time)

    def clear(self) -> None:
        self._points.clear()

    # ------------------------------------------------------------------
    # Avaliação
    # ------------------------------------------------------------------

    def evaluate(self, time: float) -> float:
        """
        Retorna o valor da curva no instante dado.

        - Antes do primeiro ponto: retorna o valor do primeiro ponto (ou default).
        - Depois do último ponto: retorna o valor do último ponto.
        - Entre dois pontos: interpola com o modo definido no ponto anterior.
        """
        if not self._points:
            return self.default_val

        if time <= self._points[0].time:
            return self._points[0].value

        if time >= self._points[-1].time:
            return self._points[-1].value

        # Encontra o par de pontos que envolve o tempo
        for i in range(len(self._points) - 1):
            p0 = self._points[i]
            p1 = self._points[i + 1]
            if p0.time <= time <= p1.time:
                return interpolate(
                    p0.time, p0.value,
                    p1.time, p1.value,
                    time,
                    mode=p0.mode,
                )

        return self.default_val

    def evaluate_normalized(self, time: float) -> float:
        """Valor normalizado em [0, 1] relativo a min_val/max_val."""
        span = self.max_val - self.min_val
        if span == 0:
            return 0.0
        return (self.evaluate(time) - self.min_val) / span

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    @property
    def points(self) -> List[ControlPoint]:
        return list(self._points)

    @property
    def duration(self) -> float:
        if not self._points:
            return 0.0
        return self._points[-1].time

    def __len__(self) -> int:
        return len(self._points)

    # ------------------------------------------------------------------
    # Serialização
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_param": self.target_param,
            "min_val":      self.min_val,
            "max_val":      self.max_val,
            "default_val":  self.default_val,
            "enabled":      self.enabled,
            "points":       [p.to_dict() for p in self._points],
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        self.target_param = data.get("target_param", "")
        self.min_val      = data.get("min_val", 0.0)
        self.max_val      = data.get("max_val", 1.0)
        self.default_val  = data.get("default_val", 0.0)
        self.enabled      = data.get("enabled", True)
        self._points      = [ControlPoint.from_dict(p) for p in data.get("points", [])]

    def __repr__(self) -> str:
        return (
            f"AutomationCurve(param='{self.target_param}', "
            f"points={len(self._points)}, duration={self.duration:.2f}s)"
        )