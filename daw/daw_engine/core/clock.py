# core/clock.py
"""Gerencia o tempo e a taxa de amostragem da DAW."""
import time

class Clock:
    """Relógio principal para sincronização de eventos e transporte."""
    def __init__(self, bpm=120, sample_rate=44100):
        self.bpm = bpm
        self.sample_rate = sample_rate
        self._start_time = None
        self._paused = False
        self._pause_time = 0.0

    def start(self):
        self._start_time = time.time()
        self._paused = False

    def stop(self):
        self._start_time = None

    def pause(self):
        if not self._paused and self._start_time is not None:
            self._pause_time = self.get_current_time()
            self._paused = True

    def resume(self):
        if self._paused:
            self._start_time = time.time() - self._pause_time
            self._paused = False

    def get_current_time(self) -> float:
        """Retorna o tempo atual em segundos desde o início."""
        if self._start_time is None:
            return 0.0
        if self._paused:
            return self._pause_time
        return time.time() - self._start_time

    def get_ticks(self) -> int:
        """Retorna o tempo em ticks (baseado em samples ou PPQ)."""
        # Exemplo: ticks = tempo * sample_rate / (60 / bpm) * ...
        return int(self.get_current_time() * self.sample_rate)