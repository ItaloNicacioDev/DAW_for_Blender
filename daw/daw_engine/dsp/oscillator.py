# dsp/oscillator.py
"""
Osciladores de áudio.

Por que reescrever:
- A versão anterior (`SineOsc.sample(f, t, sr)`) calculava UMA amostra
  por chamada usando `math.sin` puro Python — isso é inviável em tempo
  real: gerar um bloco de 512 frames exigiria 512 chamadas Python por
  voz por callback, o que não acompanha 48kHz.
- Também não guardava fase: `sin(2*pi*f*t/sr)` depende de um `t` absoluto
  vindo de fora, que se não for perfeitamente contínuo entre blocos,
  gera "pulos" de fase audíveis (clique/estalo) toda vez que a frequência
  muda no meio de uma nota.

Esta versão:
- Processa em bloco (vetorizado com numpy) — uma chamada gera N amostras.
- Mantém fase interna contínua entre blocos, então pode mudar de
  frequência (pitch bend, vibrato) sem estalos.
- Oferece osciladores comuns de synth: seno, dente-de-serra, quadrada,
  triângulo — todos com a mesma interface, então o Mixer/Synth pode
  trocar de forma de onda sem mudar lógica.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class Oscillator(ABC):
    """
    Interface comum de todos os osciladores.

    Contrato: generate(freq, frames) sempre avança a fase internamente
    e retorna exatamente 'frames' amostras float32 no range [-1.0, 1.0].
    """

    def __init__(self, sample_rate: int = 48000) -> None:
        self.sample_rate = sample_rate
        self._phase: float = 0.0   # fase normalizada, range [0.0, 1.0)

    @abstractmethod
    def generate(self, freq: float, frames: int) -> np.ndarray:
        ...

    def reset_phase(self, phase: float = 0.0) -> None:
        """Reseta a fase (útil ao reiniciar uma nota do zero, sem retrigger suave)."""
        self._phase = phase % 1.0

    def _advance_phase(self, freq: float, frames: int) -> np.ndarray:
        """
        Calcula a fase normalizada (0.0–1.0) para cada uma das 'frames'
        amostras, avançando o estado interno ao final.

        Retorna um array de fases — cada subclasse decide como mapear
        fase -> forma de onda.
        """
        phase_inc = freq / self.sample_rate
        phases = self._phase + phase_inc * np.arange(frames, dtype=np.float64)
        self._phase = float((self._phase + phase_inc * frames) % 1.0)
        return np.mod(phases, 1.0)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(sr={self.sample_rate}, phase={self._phase:.4f})"


class SineOsc(Oscillator):
    """Oscilador senoidal — forma de onda mais "pura", som suave."""

    def generate(self, freq: float, frames: int) -> np.ndarray:
        phases = self._advance_phase(freq, frames)
        return np.sin(2.0 * np.pi * phases).astype(np.float32)


class SawOsc(Oscillator):
    """
    Oscilador dente-de-serra (saw) — rico em harmônicos, som "brilhante",
    base clássica de synths analógicos.
    """

    def generate(self, freq: float, frames: int) -> np.ndarray:
        phases = self._advance_phase(freq, frames)
        # Mapeia fase [0,1) para [-1, 1)
        return (2.0 * phases - 1.0).astype(np.float32)


class SquareOsc(Oscillator):
    """
    Oscilador de onda quadrada — som "oco", clássico de chiptune/8-bit.
    Suporta duty cycle ajustável (pulse width) via parâmetro opcional.
    """

    def __init__(self, sample_rate: int = 48000, duty: float = 0.5) -> None:
        super().__init__(sample_rate)
        self.duty = min(0.95, max(0.05, duty))

    def generate(self, freq: float, frames: int) -> np.ndarray:
        phases = self._advance_phase(freq, frames)
        out = np.where(phases < self.duty, 1.0, -1.0)
        return out.astype(np.float32)


class TriangleOsc(Oscillator):
    """Oscilador triangular — entre seno e quadrada, som suave mas com mais harmônicos que o seno."""

    def generate(self, freq: float, frames: int) -> np.ndarray:
        phases = self._advance_phase(freq, frames)
        # Triângulo: sobe de -1 a 1 na primeira metade, desce na segunda
        out = np.where(
            phases < 0.5,
            4.0 * phases - 1.0,
            3.0 - 4.0 * phases,
        )
        return out.astype(np.float32)


# ------------------------------------------------------------------
# Fábrica de osciladores por nome — útil para presets/UI (dropdown
# de forma de onda) sem precisar importar cada classe manualmente.
# ------------------------------------------------------------------

_OSCILLATOR_TYPES = {
    "sine":     SineOsc,
    "saw":      SawOsc,
    "square":   SquareOsc,
    "triangle": TriangleOsc,
}


def create_oscillator(wave_type: str, sample_rate: int = 48000) -> Oscillator:
    """
    Cria um oscilador pelo nome ('sine', 'saw', 'square', 'triangle').
    Levanta ValueError se o tipo não existir.
    """
    cls = _OSCILLATOR_TYPES.get(wave_type.lower())
    if cls is None:
        raise ValueError(
            f"Tipo de oscilador desconhecido: '{wave_type}'. "
            f"Disponíveis: {list(_OSCILLATOR_TYPES.keys())}"
        )
    return cls(sample_rate=sample_rate)


def available_waveforms() -> list[str]:
    """Lista os nomes de forma de onda disponíveis (para popular UI)."""
    return list(_OSCILLATOR_TYPES.keys())