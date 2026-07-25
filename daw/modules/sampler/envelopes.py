# modules/sampler/envelopes.py
"""
Envelopes genéricos: fade in/out, crossfade e curvas de breakpoints.

Distintos do ADSR (adsr.py cuida apenas do envelope clássico de amplitude
attack/decay/sustain/release); este módulo fornece utilitários usados por
looping.py (crossfade de loop) e slicing.py (fade nas bordas das fatias),
além de um envelope genérico para modulação futura (filtro, pitch, etc).
"""
from __future__ import annotations

import numpy as np


def linear_fade(num_samples: int, fade_in: bool = True) -> np.ndarray:
    ramp = np.linspace(0.0, 1.0, num_samples, dtype=np.float32)
    return ramp if fade_in else ramp[::-1].copy()


def equal_power_fade(num_samples: int, fade_in: bool = True) -> np.ndarray:
    """Curva de fade com potência constante (soa mais natural que fade linear
    em crossfades, pois a soma de energia das duas curvas permanece ~1)."""
    ramp = np.linspace(0.0, np.pi / 2.0, num_samples, dtype=np.float32)
    return np.sin(ramp) if fade_in else np.cos(ramp)


def apply_crossfade(tail: np.ndarray, head: np.ndarray, curve: str = 'EQUAL_POWER') -> np.ndarray:
    """Combina o final de um buffer (`tail`) com o início de outro (`head`)
    usando uma curva de crossfade, retornando um buffer de tamanho
    min(len(tail), len(head))."""
    n = min(len(tail), len(head))
    if n <= 0:
        return np.concatenate([tail, head])

    if curve == 'LINEAR':
        fade_out = linear_fade(n, fade_in=False)
        fade_in = linear_fade(n, fade_in=True)
    else:
        fade_out = equal_power_fade(n, fade_in=False)
        fade_in = equal_power_fade(n, fade_in=True)

    return tail[-n:] * fade_out + head[:n] * fade_in


class BreakpointEnvelope:
    """Envelope genérico definido por pontos (tempo_normalizado, valor) em [0, 1].

    Útil para modulações customizadas (ex.: pitch bend de fatia, abertura de
    filtro) além do envelope de amplitude padrão do ADSR.
    """

    def __init__(self, points: list[tuple[float, float]] | None = None):
        self.points = sorted(points or [(0.0, 0.0), (1.0, 1.0)])

    def value_at(self, t: float) -> float:
        t = min(max(t, 0.0), 1.0)
        pts = self.points

        if t <= pts[0][0]:
            return pts[0][1]
        if t >= pts[-1][0]:
            return pts[-1][1]

        for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
            if t0 <= t <= t1:
                if t1 == t0:
                    return v1
                frac = (t - t0) / (t1 - t0)
                return v0 + (v1 - v0) * frac

        return pts[-1][1]

    def render(self, num_samples: int) -> np.ndarray:
        ts = np.linspace(0.0, 1.0, num_samples, dtype=np.float32)
        return np.array([self.value_at(float(t)) for t in ts], dtype=np.float32)


classes = []


def register():
    pass


def unregister():
    pass