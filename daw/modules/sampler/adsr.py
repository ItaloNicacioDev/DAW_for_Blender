# modules/sampler/adsr.py
"""
Envelope ADSR (Attack, Decay, Sustain, Release) clássico de amplitude.
"""
from __future__ import annotations

import numpy as np


class ADSREnvelope:
    """Envelope de amplitude com estágios attack/decay/sustain/release.

    Tempos (`attack`, `decay`, `release`) são em segundos; `sustain` é um
    nível (0-1). O estado avança amostra a amostra via `process()`.
    """

    STAGE_IDLE = 'IDLE'
    STAGE_ATTACK = 'ATTACK'
    STAGE_DECAY = 'DECAY'
    STAGE_SUSTAIN = 'SUSTAIN'
    STAGE_RELEASE = 'RELEASE'

    def __init__(self, samplerate: int = 48000):
        self.samplerate = samplerate
        self.attack = 0.01
        self.decay = 0.1
        self.sustain = 0.8
        self.release = 0.2

        self.stage = self.STAGE_IDLE
        self.level = 0.0
        self._release_start_level = 0.0

    def configure(self, attack: float, decay: float, sustain: float, release: float):
        self.attack = max(attack, 0.0001)
        self.decay = max(decay, 0.0001)
        self.sustain = min(max(sustain, 0.0), 1.0)
        self.release = max(release, 0.0001)

    def note_on(self):
        self.stage = self.STAGE_ATTACK

    def note_off(self):
        if self.stage != self.STAGE_IDLE:
            self._release_start_level = self.level
            self.stage = self.STAGE_RELEASE

    def is_active(self) -> bool:
        return self.stage != self.STAGE_IDLE

    def process(self, num_samples: int) -> np.ndarray:
        """Gera `num_samples` valores de ganho (0-1), avançando o estado do envelope.

        Implementado amostra a amostra para lidar corretamente com transições
        de estágio no meio de um bloco; para os tamanhos de bloco típicos de
        um sampler o custo é aceitável, mas pode ser vetorizado por estágio
        caso a performance se torne um gargalo.
        """
        out = np.empty(num_samples, dtype=np.float32)
        dt = 1.0 / self.samplerate

        for i in range(num_samples):
            if self.stage == self.STAGE_ATTACK:
                self.level += dt / self.attack
                if self.level >= 1.0:
                    self.level = 1.0
                    self.stage = self.STAGE_DECAY

            elif self.stage == self.STAGE_DECAY:
                self.level -= dt * (1.0 - self.sustain) / self.decay
                if self.level <= self.sustain:
                    self.level = self.sustain
                    self.stage = self.STAGE_SUSTAIN

            elif self.stage == self.STAGE_SUSTAIN:
                self.level = self.sustain

            elif self.stage == self.STAGE_RELEASE:
                self.level -= dt * self._release_start_level / self.release
                if self.level <= 0.0:
                    self.level = 0.0
                    self.stage = self.STAGE_IDLE

            else:  # IDLE
                self.level = 0.0

            out[i] = self.level

        return out


classes = []


def register():
    pass


def unregister():
    pass