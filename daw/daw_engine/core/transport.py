# core/transport.py
"""Controle de reprodução (play, stop, record, loop)."""
from .events import EventSystem, EVENT_PLAY, EVENT_STOP, EVENT_RECORD

class Transport:
    """Gerencia o estado de reprodução."""
    def __init__(self):
        self.is_playing = False
        self.is_recording = False
        self.is_looping = False
        self.loop_start = 0.0
        self.loop_end = 4.0
        self.current_position = 0.0  # em segundos
        self.event_system = EventSystem()

    def play(self):
        self.is_playing = True
        self.event_system.emit(EVENT_PLAY)

    def stop(self):
        self.is_playing = False
        self.is_recording = False
        self.event_system.emit(EVENT_STOP)

    def record(self):
        self.is_recording = True
        self.is_playing = True
        self.event_system.emit(EVENT_RECORD)

    def toggle_loop(self):
        self.is_looping = not self.is_looping

    def set_position(self, time):
        self.current_position = time

    def update(self, delta_time):
        """Atualiza posição durante reprodução."""
        if self.is_playing:
            self.current_position += delta_time
            if self.is_looping and self.current_position >= self.loop_end:
                self.current_position = self.loop_start