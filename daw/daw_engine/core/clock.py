# core/clock.py
"""
Relógio principal da DAW.

Responsabilidades:
- Medir tempo real (wall-clock) com precisão
- Converter tempo <-> beats <-> ticks (PPQ)
- Suportar pause/resume sem saltar no tempo

NÃO faz output de áudio nem acessa bpy.
"""
from __future__ import annotations

import time

from .constants import (
    DEFAULT_BPM,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_PPQ,
    MIN_BPM,
    MAX_BPM,
)


class Clock:
    """
    Relógio de tempo real da DAW.

    Unidade primária: segundos (float).
    Conversões para beats e ticks são derivadas do BPM e PPQ atuais.
    """

    def __init__(
        self,
        bpm: float = DEFAULT_BPM,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        ppq: int = DEFAULT_PPQ,
    ) -> None:
        self._bpm: float = float(bpm)
        self.sample_rate: int = sample_rate
        self.ppq: int = ppq

        self._start_wall: float | None = None   # time.time() no momento do start
        self._paused: bool = False
        self._paused_at: float = 0.0            # segundos acumulados antes do pause

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Inicia (ou reinicia) o relógio do zero."""
        self._start_wall = time.time()
        self._paused = False
        self._paused_at = 0.0

    def stop(self) -> None:
        """Para o relógio e zera a posição."""
        self._start_wall = None
        self._paused = False
        self._paused_at = 0.0

    def pause(self) -> None:
        """Congela o tempo sem perder a posição atual."""
        if self._paused or self._start_wall is None:
            return
        self._paused_at = self._elapsed_since_start()
        self._paused = True

    def resume(self) -> None:
        """Retoma a partir de onde pausou."""
        if not self._paused:
            return
        # Reancora o start_wall para que elapsed = _paused_at + tempo desde agora
        self._start_wall = time.time() - self._paused_at
        self._paused = False

    # ------------------------------------------------------------------
    # Leitura de tempo
    # ------------------------------------------------------------------

    def get_current_time(self) -> float:
        """Retorna o tempo corrido em segundos (0.0 se parado)."""
        if self._start_wall is None:
            return 0.0
        if self._paused:
            return self._paused_at
        return self._elapsed_since_start()

    def get_current_beat(self) -> float:
        """Retorna a posição em beats (compassos = beat / beats_por_compasso)."""
        return self.seconds_to_beats(self.get_current_time())

    def get_ticks(self) -> int:
        """Retorna a posição em ticks MIDI (baseado em PPQ e BPM)."""
        return self.seconds_to_ticks(self.get_current_time())

    # ------------------------------------------------------------------
    # Conversões
    # ------------------------------------------------------------------

    def seconds_to_beats(self, seconds: float) -> float:
        """Converte segundos para beats dado o BPM atual."""
        return seconds * (self._bpm / 60.0)

    def beats_to_seconds(self, beats: float) -> float:
        """Converte beats para segundos dado o BPM atual."""
        if self._bpm == 0:
            return 0.0
        return beats / (self._bpm / 60.0)

    def seconds_to_ticks(self, seconds: float) -> int:
        """Converte segundos para ticks MIDI."""
        beats = self.seconds_to_beats(seconds)
        return int(beats * self.ppq)

    def ticks_to_seconds(self, ticks: int) -> float:
        """Converte ticks MIDI para segundos."""
        beats = ticks / self.ppq
        return self.beats_to_seconds(beats)

    def seconds_to_samples(self, seconds: float) -> int:
        """Converte segundos para número de samples."""
        return int(seconds * self.sample_rate)

    def samples_to_seconds(self, samples: int) -> float:
        """Converte número de samples para segundos."""
        return samples / self.sample_rate

    # ------------------------------------------------------------------
    # BPM
    # ------------------------------------------------------------------

    @property
    def bpm(self) -> float:
        return self._bpm

    @bpm.setter
    def bpm(self, value: float) -> None:
        if not (MIN_BPM <= value <= MAX_BPM):
            raise ValueError(f"BPM fora do range permitido ({MIN_BPM}–{MAX_BPM}): {value}")
        self._bpm = float(value)

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._start_wall is not None and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------

    def _elapsed_since_start(self) -> float:
        """Tempo corrido desde o start sem considerar pausa."""
        return time.time() - self._start_wall  # type: ignore[operator]

    def __repr__(self) -> str:
        return (
            f"Clock(bpm={self._bpm}, time={self.get_current_time():.3f}s, "
            f"paused={self._paused})"
        )