# dsp/adsr.py
"""
Envelope ADSR (Attack, Decay, Sustain, Release).

Por que isso importa: sem envelope, toda nota liga/desliga abruptamente
(clique audível, "pop" no áudio). O ADSR molda o volume da nota ao
longo do tempo para soar natural.

Modelo de estado:
    IDLE -> (note_on) -> ATTACK -> DECAY -> SUSTAIN -> (note_off) -> RELEASE -> IDLE

Uso típico dentro de uma voz de sintetizador:
    env = ADSR(attack=0.01, decay=0.1, sustain=0.7, release=0.3)
    env.note_on()
    ...
    gain_buffer = env.process(frames, sample_rate)   # numpy array
    ...
    env.note_off()
    # continua chamando process() até env.is_finished virar True
"""
from __future__ import annotations

from enum import Enum, auto

import numpy as np


class ADSRStage(Enum):
    IDLE     = auto()
    ATTACK   = auto()
    DECAY    = auto()
    SUSTAIN  = auto()
    RELEASE  = auto()


class ADSR:
    """
    Gerador de envelope de amplitude, processado em blocos (vetorizado com numpy)
    para ser eficiente o suficiente para rodar dentro do audio callback.

    Todos os tempos são em segundos. Sustain é um nível (0.0–1.0), não um tempo.
    """

    def __init__(
        self,
        attack:  float = 0.01,
        decay:   float = 0.1,
        sustain: float = 0.8,
        release: float = 0.2,
    ) -> None:
        self.attack  = max(0.0, attack)
        self.decay   = max(0.0, decay)
        self.sustain = min(1.0, max(0.0, sustain))
        self.release = max(0.0, release)

        self._stage: ADSRStage = ADSRStage.IDLE
        self._level: float = 0.0          # nível de amplitude atual (0.0–1.0)
        self._release_start_level: float = 0.0  # nível no instante do note_off

    # ------------------------------------------------------------------
    # Controle de nota
    # ------------------------------------------------------------------

    def note_on(self) -> None:
        """Inicia o envelope a partir do estágio ATTACK."""
        self._stage = ADSRStage.ATTACK
        # Não zera _level: se a nota for retriggada antes de soltar
        # totalmente, o attack parte do nível atual (evita clique).

    def note_off(self) -> None:
        """Inicia o estágio RELEASE a partir do nível atual."""
        if self._stage == ADSRStage.IDLE:
            return
        self._release_start_level = self._level
        self._stage = ADSRStage.RELEASE

    def reset(self) -> None:
        """Força o envelope de volta a IDLE imediatamente (sem release)."""
        self._stage = ADSRStage.IDLE
        self._level = 0.0

    # ------------------------------------------------------------------
    # Processamento em bloco
    # ------------------------------------------------------------------

    def process(self, frames: int, sample_rate: int) -> np.ndarray:
        """
        Gera 'frames' amostras de ganho (0.0–1.0) avançando o estado interno.

        Retorna um array numpy float32 de tamanho 'frames'.
        Deve ser chamado uma vez por bloco de áudio, na ordem correta
        (não pula tempo).
        """
        out = np.empty(frames, dtype=np.float32)

        i = 0
        while i < frames:
            if self._stage == ADSRStage.IDLE:
                out[i:] = 0.0
                self._level = 0.0
                break

            elif self._stage == ADSRStage.ATTACK:
                i = self._process_attack(out, i, frames, sample_rate)

            elif self._stage == ADSRStage.DECAY:
                i = self._process_decay(out, i, frames, sample_rate)

            elif self._stage == ADSRStage.SUSTAIN:
                remaining = frames - i
                out[i:] = self.sustain
                self._level = self.sustain
                i = frames

            elif self._stage == ADSRStage.RELEASE:
                i = self._process_release(out, i, frames, sample_rate)

        return out

    # ------------------------------------------------------------------
    # Estágios individuais
    # ------------------------------------------------------------------

    def _process_attack(self, out: np.ndarray, i: int, frames: int, sr: int) -> int:
        if self.attack <= 0.0:
            self._level = 1.0
            self._stage = ADSRStage.DECAY
            return i

        attack_samples = max(1, int(self.attack * sr))
        # Quantas amostras já passamos do attack, baseado no nível atual
        start_progress = self._level  # 0.0 (nível atual) até 1.0
        remaining_samples = int(attack_samples * (1.0 - start_progress))
        remaining_samples = max(1, remaining_samples)

        n = min(remaining_samples, frames - i)
        ramp = np.linspace(self._level, 1.0, n, endpoint=False, dtype=np.float32)
        out[i:i + n] = ramp
        self._level = float(ramp[-1]) if n > 0 else self._level
        i += n

        if n >= remaining_samples:
            self._level = 1.0
            self._stage = ADSRStage.DECAY

        return i

    def _process_decay(self, out: np.ndarray, i: int, frames: int, sr: int) -> int:
        if self.decay <= 0.0:
            self._level = self.sustain
            self._stage = ADSRStage.SUSTAIN
            return i

        decay_samples = max(1, int(self.decay * sr))
        # Progresso atual dentro do decay, baseado em onde _level está
        # entre 1.0 (início) e sustain (fim)
        span = 1.0 - self.sustain
        if span <= 0.0:
            self._level = self.sustain
            self._stage = ADSRStage.SUSTAIN
            return i

        progress = 1.0 - ((self._level - self.sustain) / span)
        progress = min(1.0, max(0.0, progress))
        remaining_samples = max(1, int(decay_samples * (1.0 - progress)))

        n = min(remaining_samples, frames - i)
        ramp = np.linspace(self._level, self.sustain, n, endpoint=False, dtype=np.float32)
        out[i:i + n] = ramp
        self._level = float(ramp[-1]) if n > 0 else self._level
        i += n

        if n >= remaining_samples:
            self._level = self.sustain
            self._stage = ADSRStage.SUSTAIN

        return i

    def _process_release(self, out: np.ndarray, i: int, frames: int, sr: int) -> int:
        if self.release <= 0.0:
            self._level = 0.0
            self._stage = ADSRStage.IDLE
            return i

        release_samples = max(1, int(self.release * sr))
        if self._release_start_level <= 0.0:
            self._level = 0.0
            self._stage = ADSRStage.IDLE
            return i

        progress = 1.0 - (self._level / self._release_start_level)
        progress = min(1.0, max(0.0, progress))
        remaining_samples = max(1, int(release_samples * (1.0 - progress)))

        n = min(remaining_samples, frames - i)
        ramp = np.linspace(self._level, 0.0, n, endpoint=False, dtype=np.float32)
        out[i:i + n] = ramp
        self._level = float(ramp[-1]) if n > 0 else self._level
        i += n

        if n >= remaining_samples:
            self._level = 0.0
            self._stage = ADSRStage.IDLE

        return i

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    @property
    def stage(self) -> ADSRStage:
        return self._stage

    @property
    def is_finished(self) -> bool:
        """True quando a voz pode ser descartada (envelope chegou a zero)."""
        return self._stage == ADSRStage.IDLE

    @property
    def is_active(self) -> bool:
        return self._stage != ADSRStage.IDLE

    @property
    def current_level(self) -> float:
        return self._level

    def __repr__(self) -> str:
        return (
            f"ADSR(stage={self._stage.name}, level={self._level:.3f}, "
            f"A={self.attack} D={self.decay} S={self.sustain} R={self.release})"
        )