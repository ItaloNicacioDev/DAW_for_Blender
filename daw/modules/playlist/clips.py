# modules/playlist/clips.py
"""
Clips na Playlist (Timeline) — sem dependência de bpy.

Responsabilidade:
    Representar um clip posicionado na timeline da playlist.
    Pode ser um clip de pattern (referencia um pattern do módulo
    patterns) ou um placeholder para clip de áudio.

Arquitetura:
    clips.py    → PlaylistClip: clip na timeline (este arquivo)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlaylistClip:
    """Um clip posicionado na timeline da playlist."""

    name: str = "Clip"
    clip_type: str = "PATTERN"   # "PATTERN" | "AUDIO" | "AUTOMATION"

    # Posição na timeline
    track_index: int = 0         # índice da track da playlist
    start_beat: float = 0.0
    duration_beats: float = 4.0

    # Conteúdo
    pattern_name: str = ""       # se clip_type == "PATTERN"
    audio_path: str = ""         # se clip_type == "AUDIO"
    automation_param: str = ""   # se clip_type == "AUTOMATION"

    # Offset dentro do conteúdo (para clips cortados)
    content_offset_beats: float = 0.0

    # Estado
    muted: bool = False
    locked: bool = False
    selected: bool = False
    color_override: Optional[tuple] = None

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.duration_beats

    def move(self, new_start: float) -> None:
        self.start_beat = max(0.0, new_start)

    def resize(self, new_duration: float) -> None:
        self.duration_beats = max(0.25, new_duration)

    def split(self, at_beat: float) -> Optional["PlaylistClip"]:
        """Divide o clip em dois. Retorna a segunda metade."""
        if at_beat <= self.start_beat or at_beat >= self.end_beat:
            return None

        first_dur = at_beat - self.start_beat
        second_offset = self.content_offset_beats + first_dur
        second_dur = self.duration_beats - first_dur

        self.duration_beats = first_dur

        return PlaylistClip(
            name=f"{self.name} (split)",
            clip_type=self.clip_type,
            track_index=self.track_index,
            start_beat=at_beat,
            duration_beats=second_dur,
            pattern_name=self.pattern_name,
            audio_path=self.audio_path,
            automation_param=self.automation_param,
            content_offset_beats=second_offset,
            color_override=self.color_override,
        )

    def __repr__(self) -> str:
        return (
            f"PlaylistClip(type={self.clip_type}, track={self.track_index}, "
            f"start={self.start_beat:.2f}, dur={self.duration_beats:.2f})"
        )