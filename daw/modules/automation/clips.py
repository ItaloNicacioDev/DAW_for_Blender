# modules/automation/clips.py
"""
Clip de automação: une uma AutomationCurve a uma posição na Timeline.

Responsabilidade:
    Um AutomationClip é o que aparece na faixa de automação da timeline —
    tem posição (start), duração e aponta para uma curva.
    É análogo ao Clip do core/timeline.py mas específico para automação.

Sem bpy — lógica pura, serializável.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .curves import AutomationCurve
from .interpolation import InterpolationMode


class AutomationClip:
    """
    Segmento de automação posicionado na timeline.

    Um clip contém uma ou mais curvas (uma por parâmetro automatizado).
    Na maioria dos casos tem só uma curva, mas um clip pode automatizar
    volume E pan simultaneamente, por exemplo.
    """

    def __init__(
        self,
        name:  str   = "Automation",
        start: float = 0.0,
        duration: float = 4.0,
    ) -> None:
        self.name:     str   = name
        self.start:    float = start
        self.duration: float = duration
        self.enabled:  bool  = True
        self.color:    tuple = (0.9, 0.6, 0.1)    # laranja — padrão visual p/ automação

        self._curves: List[AutomationCurve] = []

    # ------------------------------------------------------------------
    # Propriedades calculadas
    # ------------------------------------------------------------------

    @property
    def end(self) -> float:
        return self.start + self.duration

    # ------------------------------------------------------------------
    # Gerenciamento de curvas
    # ------------------------------------------------------------------

    def add_curve(
        self,
        target_param: str,
        min_val:  float = 0.0,
        max_val:  float = 1.0,
        default_val: float = 0.0,
    ) -> AutomationCurve:
        """Cria e adiciona uma curva para o parâmetro dado."""
        # Evita duplicata para o mesmo parâmetro
        existing = self.get_curve(target_param)
        if existing:
            return existing
        curve = AutomationCurve(
            target_param=target_param,
            min_val=min_val,
            max_val=max_val,
            default_val=default_val,
        )
        self._curves.append(curve)
        return curve

    def get_curve(self, target_param: str) -> Optional[AutomationCurve]:
        """Retorna a curva para o parâmetro dado, ou None."""
        for c in self._curves:
            if c.target_param == target_param:
                return c
        return None

    def remove_curve(self, target_param: str) -> bool:
        for i, c in enumerate(self._curves):
            if c.target_param == target_param:
                self._curves.pop(i)
                return True
        return False

    @property
    def curves(self) -> List[AutomationCurve]:
        return list(self._curves)

    # ------------------------------------------------------------------
    # Avaliação — chamada pelo Scheduler durante a reprodução
    # ------------------------------------------------------------------

    def evaluate(self, project_time: float) -> Dict[str, float]:
        """
        Dado o tempo absoluto do projeto, retorna um dict
        {target_param: valor} para todos os parâmetros do clip.

        Retorna {} se o tempo estiver fora do clip ou o clip estiver desativado.
        """
        if not self.enabled:
            return {}
        if not (self.start <= project_time < self.end):
            return {}

        local_time = project_time - self.start
        return {
            c.target_param: c.evaluate(local_time)
            for c in self._curves
            if c.enabled
        }

    # ------------------------------------------------------------------
    # Serialização
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":     self.name,
            "start":    self.start,
            "duration": self.duration,
            "enabled":  self.enabled,
            "color":    list(self.color),
            "curves":   [c.to_dict() for c in self._curves],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutomationClip":
        clip = cls(
            name=data.get("name", "Automation"),
            start=data.get("start", 0.0),
            duration=data.get("duration", 4.0),
        )
        clip.enabled = data.get("enabled", True)
        clip.color   = tuple(data.get("color", [0.9, 0.6, 0.1]))
        for cd in data.get("curves", []):
            curve = AutomationCurve()
            curve.from_dict(cd)
            clip._curves.append(curve)
        return clip

    def __repr__(self) -> str:
        return (
            f"AutomationClip('{self.name}', {self.start:.2f}s–{self.end:.2f}s, "
            f"curves={len(self._curves)})"
        )