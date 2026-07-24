# modules/playlist/playback.py
"""
Controle de Playback/Transporte — sem dependência de bpy.

Responsabilidade:
    Gerenciar o estado de reprodução: play/pause/stop, posição
    atual do playhead, loop range, BPM, e time signature.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlaybackState:
    """Estado do transporte/playback."""

    is_playing: bool = False
    is_recording: bool = False

    current_beat: float = 0.0
    current_bpm: float = 120.0

    time_signature_num: int = 4
    time_signature_den: int = 4

    # Loop
    loop_enabled: bool = False
    loop_start_beat: float = 0.0
    loop_end_beat: float = 16.0

    # Metronomo
    metronome_enabled: bool = False
    pre_roll_beats: float = 0.0

    def play(self) -> None:
        self.is_playing = True

    def pause(self) -> None:
        self.is_playing = False

    def stop(self) -> None:
        self.is_playing = False
        self.is_recording = False
        self.current_beat = 0.0

    def toggle_play(self) -> None:
        self.is_playing = not self.is_playing

    def toggle_record(self) -> None:
        self.is_recording = not self.is_recording

    def seek(self, beat: float) -> None:
        self.current_beat = max(0.0, beat)

    def advance(self, delta_beats: float) -> None:
        """Avança o playhead (chamado pelo timer de playback)."""
        if not self.is_playing:
            return
        self.current_beat += delta_beats
        if self.loop_enabled and self.current_beat >= self.loop_end_beat:
            self.current_beat = self.loop_start_beat + (self.current_beat - self.loop_end_beat)

    @property
    def current_bar(self) -> int:
        return int(self.current_beat // self.time_signature_num) + 1

    @property
    def current_beat_in_bar(self) -> int:
        return int(self.current_beat % self.time_signature_num) + 1

    def __repr__(self) -> str:
        status = "PLAY" if self.is_playing else "STOP"
        if self.is_recording:
            status = "REC"
        return f"PlaybackState({status}, beat={self.current_beat:.2f}, bpm={self.current_bpm})"