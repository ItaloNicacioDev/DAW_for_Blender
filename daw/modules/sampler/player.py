# modules/sampler/player.py
"""
Sistema de reprodução de áudio: classe Voice com suporte a pitch, loop, envelope ADSR.
"""
from __future__ import annotations

import numpy as np

from .adsr import ADSREnvelope
from .looping import LoopCursor, LOOP_MODE_OFF
from .pitch import note_to_ratio, resample_linear


class Voice:
    """Reprodutor de sample com suporte a:
    - Transposição de pitch (nota MIDI)
    - Loop (OFF, FORWARD, PING_PONG)
    - Envelope ADSR de amplitude
    - Time-stretch (via razão de velocidade)
    """

    def __init__(self, sample_data: np.ndarray, samplerate: int, 
                 num_channels: int = 1):
        """
        Args:
            sample_data: array (frames,) ou (frames, canais)
            samplerate: taxa de amostragem em Hz
            num_channels: número de canais
        """
        self.sample_data = sample_data
        self.samplerate = samplerate
        self.num_channels = num_channels

        # Posição de reprodução (em frames, pode ser fracionária)
        self.position = 0.0
        self.is_active = False

        # Afinação
        self.root_note = 60  # C4
        self.played_note = 60
        self.tune_semitones = 0.0
        self.tune_cents = 0.0

        # Loop
        self.loop_mode = LOOP_MODE_OFF
        self.loop_start = 0
        self.loop_end = len(sample_data)
        self.loop_cursor = LoopCursor(self.loop_mode, self.loop_start, self.loop_end)

        # Envelope ADSR
        self.adsr = ADSREnvelope(samplerate=samplerate)

        # Ganho e pan
        self.gain_linear = 1.0
        self.pan = 0.0  # -1 (left) a +1 (right)

        # Time-stretch
        self.stretch_ratio = 1.0

    def note_on(self, note: int, velocity: float = 1.0):
        """Inicia a reprodução de uma nota MIDI."""
        self.played_note = note
        self.position = 0.0
        self.is_active = True
        self.adsr.note_on()

    def note_off(self):
        """Inicia o stage release do envelope."""
        self.adsr.note_off()

    def is_note_active(self) -> bool:
        """Retorna True se a nota ainda está tocando (envelope ativo)."""
        return self.adsr.is_active()

    def render(self, num_samples: int) -> np.ndarray:
        """Gera `num_samples` frames de áudio.

        Retorna array (num_samples, num_channels) ou (num_samples,) se mono.
        """
        if not self.is_active or len(self.sample_data) == 0:
            if self.num_channels == 1:
                return np.zeros(num_samples, dtype=np.float32)
            return np.zeros((num_samples, self.num_channels), dtype=np.float32)

        # Calcula razão de pitch
        pitch_ratio = note_to_ratio(
            self.played_note, self.root_note,
            self.tune_semitones, self.tune_cents
        )

        # Aplica time-stretch
        total_ratio = pitch_ratio * self.stretch_ratio

        # Gera envelope ADSR
        envelope = self.adsr.process(num_samples)

        # Reproduz sample com interpolação de pitch
        output = np.zeros((num_samples, self.num_channels), dtype=np.float32)

        for i in range(num_samples):
            if not self.is_note_active():
                break

            # Valida posição dentro dos bounds
            n_frames = len(self.sample_data)
            if self.position >= n_frames:
                self.is_active = False
                break

            # Interpolação linear simples
            idx = int(self.position)
            frac = self.position - idx
            idx_next = min(idx + 1, n_frames - 1)

            # Lê amostra (mono ou multi-canal)
            if self.sample_data.ndim == 1:
                val = (self.sample_data[idx] * (1.0 - frac) +
                       self.sample_data[idx_next] * frac)
                output[i, 0] = val * envelope[i] * self.gain_linear
                if self.num_channels > 1:
                    output[i, 1:] = output[i, 0]
            else:
                for ch in range(self.num_channels):
                    val = (self.sample_data[idx, ch] * (1.0 - frac) +
                           self.sample_data[idx_next, ch] * frac)
                    output[i, ch] = val * envelope[i] * self.gain_linear

            # Avança posição com loop handling
            self.position, finished = self.loop_cursor.advance(
                self.position, total_ratio, n_frames
            )
            if finished:
                self.is_active = False

        # Aplica pan (estéreo simples: -1 = L, 0 = center, +1 = R)
        if self.num_channels >= 2:
            left_gain = 1.0 if self.pan >= 0 else 1.0 + self.pan
            right_gain = 1.0 if self.pan <= 0 else 1.0 - self.pan
            output[:, 0] *= left_gain
            output[:, 1] *= right_gain

        if self.num_channels == 1:
            return output[:, 0]
        return output


class Sampler:
    """Gerenciador de vozes e reprodução polifônica."""

    def __init__(self, num_voices: int = 16, samplerate: int = 48000):
        self.voices: list[Voice | None] = [None] * num_voices
        self.samplerate = samplerate
        self.num_voices = num_voices

    def note_on(self, sample_data: np.ndarray, note: int, 
                velocity: float = 1.0, channels: int = 1):
        """Encontra uma voz livre e inicia reprodução."""
        for i in range(self.num_voices):
            if self.voices[i] is None or not self.voices[i].is_note_active():
                self.voices[i] = Voice(sample_data, self.samplerate, channels)
                self.voices[i].note_on(note, velocity)
                return i
        return -1

    def note_off(self, voice_index: int):
        """Para uma voz específica (inicia release)."""
        if 0 <= voice_index < len(self.voices) and self.voices[voice_index]:
            self.voices[voice_index].note_off()

    def render(self, num_samples: int) -> np.ndarray:
        """Mixdown de todas as vozes."""
        mix = None
        for voice in self.voices:
            if voice and voice.is_note_active():
                audio = voice.render(num_samples)
                if mix is None:
                    mix = audio.copy()
                else:
                    if audio.ndim == 1:
                        audio = audio[:, None]
                    if mix.ndim == 1:
                        mix = mix[:, None]
                    mix = mix + audio

        if mix is None:
            return np.zeros(num_samples, dtype=np.float32)
        return mix


classes = []


def register():
    pass


def unregister():
    pass