# instruments/synth.py
"""
Sintetizador polifônico subtrativo básico.

Arquitetura de uma voz:
    MIDI note_on
        └─> Voice(note, velocity)
                ├─ Oscillator  (gera forma de onda: sine/saw/square/triangle)
                └─ ADSR        (molda o volume ao longo do tempo)

    O Synth gerencia N vozes simultâneas (polifonia) e mistura o áudio
    de todas elas num único buffer float32 estéreo, pronto para o Mixer.

Integração com o resto da DAW:
    - Mixer chama synth.process(frames) a cada bloco de áudio
    - Engine/Scheduler chama synth.note_on() / synth.note_off() via eventos
    - A forma de onda e os parâmetros ADSR são configuráveis por preset
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..dsp.oscillator import Oscillator, create_oscillator
from ..dsp.adsr import ADSR


# ------------------------------------------------------------------
# Tabela de frequências MIDI (nota 69 = A4 = 440 Hz)
# ------------------------------------------------------------------

MIDI_NOTE_FREQS: Dict[int, float] = {
    n: 440.0 * (2.0 ** ((n - 69) / 12.0))
    for n in range(128)
}


# ------------------------------------------------------------------
# Voz individual (uma nota soando)
# ------------------------------------------------------------------

class Voice:
    """
    Uma única voz do sintetizador: um par (Oscillator + ADSR).

    Gerada ao receber note_on; descartada quando o envelope chega a IDLE
    após o note_off (is_finished == True).
    """

    def __init__(
        self,
        note:        int,
        velocity:    int,
        wave_type:   str,
        sample_rate: int,
        attack:      float,
        decay:       float,
        sustain:     float,
        release:     float,
    ) -> None:
        self.note     = note
        self.velocity = velocity
        self.freq     = MIDI_NOTE_FREQS.get(note, 440.0)

        # Ganho baseado em velocity (0–127 → 0.0–1.0, escala quadrática
        # para soar mais natural do que linear)
        self.gain = (velocity / 127.0) ** 2

        self.osc  = create_oscillator(wave_type, sample_rate)
        self.adsr = ADSR(attack=attack, decay=decay, sustain=sustain, release=release)
        self.adsr.note_on()

    def note_off(self) -> None:
        self.adsr.note_off()

    def process(self, frames: int, sample_rate: int) -> np.ndarray:
        """Gera 'frames' amostras mono float32 desta voz."""
        wave     = self.osc.generate(self.freq, frames)        # forma de onda
        envelope = self.adsr.process(frames, sample_rate)      # ganho ADSR
        return wave * envelope * self.gain

    @property
    def is_finished(self) -> bool:
        return self.adsr.is_finished

    def __repr__(self) -> str:
        return f"Voice(note={self.note}, freq={self.freq:.1f}Hz, {self.adsr.stage.name})"


# ------------------------------------------------------------------
# Preset de parâmetros do Synth
# ------------------------------------------------------------------

@dataclass
class SynthPreset:
    """
    Parâmetros de um preset de sintetizador.
    Pode ser serializado para salvar no projeto.
    """
    name:       str   = "Default"
    wave_type:  str   = "sine"      # sine | saw | square | triangle
    attack:     float = 0.01
    decay:      float = 0.1
    sustain:    float = 0.8
    release:    float = 0.3
    volume:     float = 0.7         # volume master do instrumento (0.0–1.0)
    max_voices: int   = 16          # limite de polifonia

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "wave_type":  self.wave_type,
            "attack":     self.attack,
            "decay":      self.decay,
            "sustain":    self.sustain,
            "release":    self.release,
            "volume":     self.volume,
            "max_voices": self.max_voices,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SynthPreset":
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


# ------------------------------------------------------------------
# Sintetizador polifônico
# ------------------------------------------------------------------

class Synth:
    """
    Sintetizador subtrativo polifônico.

    Interface com o Mixer:
        synth.process(frames) -> np.ndarray shape (frames, 2) float32

    Interface com o Scheduler/Engine:
        synth.note_on(note, velocity)
        synth.note_off(note)
        synth.all_notes_off()
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        preset: Optional[SynthPreset] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.preset = preset or SynthPreset()

        # note -> lista de vozes (lista porque retrigger pode gerar
        # mais de uma voz para a mesma nota antes da anterior terminar)
        self._voices: Dict[int, List[Voice]] = {}

        # Vozes em release (note_off disparado, mas envelope ainda decaindo)
        self._releasing: List[Voice] = []

    # ------------------------------------------------------------------
    # Controle de notas
    # ------------------------------------------------------------------

    def note_on(self, note: int, velocity: int = 100) -> None:
        """
        Inicia uma nota. Se a nota já estiver ativa, faz retrigger
        (a voz antiga vai para release e uma nova começa).
        """
        note     = int(np.clip(note, 0, 127))
        velocity = int(np.clip(velocity, 0, 127))

        # Retrigger: manda a voz anterior para release sem silenciar
        if note in self._voices:
            for v in self._voices[note]:
                v.note_off()
                self._releasing.append(v)
            del self._voices[note]

        # Limite de polifonia: mata a voz mais antiga em release
        total = sum(len(vs) for vs in self._voices.values()) + len(self._releasing)
        if total >= self.preset.max_voices:
            self._steal_voice()

        voice = Voice(
            note=note,
            velocity=velocity,
            wave_type=self.preset.wave_type,
            sample_rate=self.sample_rate,
            attack=self.preset.attack,
            decay=self.preset.decay,
            sustain=self.preset.sustain,
            release=self.preset.release,
        )
        self._voices[note] = [voice]

    def note_off(self, note: int) -> None:
        """Inicia o release para a nota dada."""
        note = int(np.clip(note, 0, 127))
        if note in self._voices:
            for v in self._voices[note]:
                v.note_off()
                self._releasing.append(v)
            del self._voices[note]

    def all_notes_off(self) -> None:
        """Para todas as notas imediatamente (útil em stop/panic)."""
        for voices in self._voices.values():
            for v in voices:
                v.adsr.reset()
        self._voices.clear()

        for v in self._releasing:
            v.adsr.reset()
        self._releasing.clear()

    # ------------------------------------------------------------------
    # Processamento de áudio — chamado pelo Mixer a cada bloco
    # ------------------------------------------------------------------

    def process(self, frames: int) -> np.ndarray:
        """
        Gera 'frames' amostras estéreo (shape: frames x 2, dtype float32).
        Soma as contribuições de todas as vozes ativas e em release.
        """
        mono = np.zeros(frames, dtype=np.float32)

        # Vozes ativas (sustain)
        for voices in self._voices.values():
            for v in voices:
                mono += v.process(frames, self.sample_rate)

        # Vozes em release — processa e descarta as que terminaram
        still_releasing: List[Voice] = []
        for v in self._releasing:
            mono += v.process(frames, self.sample_rate)
            if not v.is_finished:
                still_releasing.append(v)
        self._releasing = still_releasing

        # Aplica volume master e previne clipping
        mono *= self.preset.volume
        mono  = np.clip(mono, -1.0, 1.0)

        # Duplica para estéreo (mono center)
        return np.column_stack([mono, mono])

    # ------------------------------------------------------------------
    # Preset
    # ------------------------------------------------------------------

    def load_preset(self, preset: SynthPreset) -> None:
        """
        Troca o preset. As vozes ativas continuam com os parâmetros
        antigos até terminar — novas vozes já usam o preset novo.
        """
        self.preset = preset

    def set_wave(self, wave_type: str) -> None:
        """Atalho para mudar a forma de onda sem trocar o preset inteiro."""
        self.preset.wave_type = wave_type

    def set_adsr(
        self,
        attack:  Optional[float] = None,
        decay:   Optional[float] = None,
        sustain: Optional[float] = None,
        release: Optional[float] = None,
    ) -> None:
        """Atalho para ajustar parâmetros ADSR individualmente."""
        if attack  is not None: self.preset.attack  = attack
        if decay   is not None: self.preset.decay   = decay
        if sustain is not None: self.preset.sustain = sustain
        if release is not None: self.preset.release = release

    # ------------------------------------------------------------------
    # Consulta de estado
    # ------------------------------------------------------------------

    @property
    def active_voice_count(self) -> int:
        return sum(len(vs) for vs in self._voices.values()) + len(self._releasing)

    @property
    def held_notes(self) -> List[int]:
        """Notas atualmente pressionadas (em sustain, não em release)."""
        return list(self._voices.keys())

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------

    def _steal_voice(self) -> None:
        """Remove a voz em release mais antiga para liberar polifonia."""
        if self._releasing:
            self._releasing.pop(0)

    def __repr__(self) -> str:
        return (
            f"Synth(preset='{self.preset.name}', wave={self.preset.wave_type}, "
            f"voices={self.active_voice_count}/{self.preset.max_voices})"
        )