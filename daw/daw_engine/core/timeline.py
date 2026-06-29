# core/timeline.py
"""
Modelo de dados da linha do tempo da DAW.

Correção vs versão anterior:
- Clip.to_dict() não serializava o campo 'type' (ClipType) — adicionado.
- Timeline.from_dict() era `pass` — implementado completamente.
- Track.to_dict() armazenava type como string bruta — agora usa .value do Enum.
- Adicionados métodos de consulta: get_clips_at(), get_track_by_name().
- Clip tem campo 'type' (ClipType) e 'color' para identificação visual.
- Track tem campo 'type' (TrackType) correto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .constants import ClipType, TrackType


# ------------------------------------------------------------------
# Clip
# ------------------------------------------------------------------

@dataclass
class Clip:
    """
    Um segmento de conteúdo (áudio ou MIDI) posicionado na timeline.

    Campos:
        name     — nome exibido na UI
        start    — início em segundos
        duration — duração em segundos
        type     — ClipType (AUDIO, MIDI, AUTOMATION)
        data     — payload: caminho de arquivo (áudio) ou lista de NoteEvent (MIDI)
        color    — cor RGB para exibição (r, g, b) no range 0.0–1.0
    """
    name:     str       = ""
    start:    float     = 0.0
    duration: float     = 1.0
    type:     ClipType  = ClipType.AUDIO
    data:     Any       = None
    color:    tuple     = field(default_factory=lambda: (0.18, 0.63, 0.93))

    # Propriedade calculada
    @property
    def end(self) -> float:
        return self.start + self.duration

    def overlaps(self, other: "Clip") -> bool:
        """Retorna True se este clip sobrepõe outro no tempo."""
        return self.start < other.end and self.end > other.start

    # ------------------------------------------------------------------
    # Serialização
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":     self.name,
            "start":    self.start,
            "duration": self.duration,
            "type":     self.type.value,
            "data":     self.data,
            "color":    list(self.color),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Clip":
        clip_type = ClipType.AUDIO
        try:
            clip_type = ClipType(data.get("type", ClipType.AUDIO.value))
        except ValueError:
            pass

        color = tuple(data.get("color", [0.18, 0.63, 0.93]))

        return cls(
            name=data.get("name", ""),
            start=data.get("start", 0.0),
            duration=data.get("duration", 1.0),
            type=clip_type,
            data=data.get("data"),
            color=color,
        )

    def __repr__(self) -> str:
        return f"Clip('{self.name}', {self.start:.2f}s–{self.end:.2f}s, {self.type.value})"


# ------------------------------------------------------------------
# Track
# ------------------------------------------------------------------

class Track:
    """
    Uma faixa da timeline (áudio, MIDI, bus ou master).

    Contém uma lista ordenada de Clips e parâmetros de mixer básicos.
    """

    def __init__(
        self,
        name: str = "",
        track_type: TrackType | str = TrackType.AUDIO,
    ) -> None:
        self.name: str = name

        # Normaliza para TrackType
        if isinstance(track_type, str):
            try:
                self.type = TrackType(track_type)
            except ValueError:
                self.type = TrackType.AUDIO
        else:
            self.type = track_type

        self.clips:  List[Clip] = []
        self.volume: float = 1.0    # 0.0–1.0 (linear)
        self.pan:    float = 0.0    # -1.0 (esq) .. 0.0 .. 1.0 (dir)
        self.mute:   bool  = False
        self.solo:   bool  = False
        self.color:  tuple = (0.35, 0.35, 0.35)

    # ------------------------------------------------------------------
    # Gerenciamento de clips
    # ------------------------------------------------------------------

    def add_clip(self, clip: Clip) -> None:
        """Adiciona um clip e mantém a lista ordenada por start."""
        self.clips.append(clip)
        self.clips.sort(key=lambda c: c.start)

    def remove_clip(self, clip: Clip) -> bool:
        """Remove um clip. Retorna True se encontrado."""
        try:
            self.clips.remove(clip)
            return True
        except ValueError:
            return False

    def get_clips_at(self, time: float) -> List[Clip]:
        """Retorna todos os clips que cobrem o instante 'time'."""
        return [c for c in self.clips if c.start <= time < c.end]

    def get_duration(self) -> float:
        """Duração total da faixa (fim do último clip)."""
        if not self.clips:
            return 0.0
        return max(c.end for c in self.clips)

    # ------------------------------------------------------------------
    # Serialização
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":   self.name,
            "type":   self.type.value,
            "clips":  [c.to_dict() for c in self.clips],
            "volume": self.volume,
            "pan":    self.pan,
            "mute":   self.mute,
            "solo":   self.solo,
            "color":  list(self.color),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Track":
        track = cls(
            name=data.get("name", ""),
            track_type=data.get("type", TrackType.AUDIO.value),
        )
        track.volume = data.get("volume", 1.0)
        track.pan    = data.get("pan", 0.0)
        track.mute   = data.get("mute", False)
        track.solo   = data.get("solo", False)
        track.color  = tuple(data.get("color", [0.35, 0.35, 0.35]))

        for clip_data in data.get("clips", []):
            track.clips.append(Clip.from_dict(clip_data))

        return track

    def __repr__(self) -> str:
        return f"Track('{self.name}', {self.type.value}, clips={len(self.clips)})"


# ------------------------------------------------------------------
# Timeline
# ------------------------------------------------------------------

class Timeline:
    """
    Agrupa todas as faixas e fornece métodos de edição da linha do tempo.
    """

    def __init__(self) -> None:
        self.tracks: List[Track] = []
        self.length: float = 0.0     # duração total calculada em segundos

    # ------------------------------------------------------------------
    # Gerenciamento de faixas
    # ------------------------------------------------------------------

    def add_track(self, track: Track) -> None:
        self.tracks.append(track)
        self._update_length()

    def remove_track(self, track: Track) -> bool:
        try:
            self.tracks.remove(track)
            self._update_length()
            return True
        except ValueError:
            return False

    def get_track_by_name(self, name: str) -> Optional[Track]:
        """Retorna a primeira faixa com o nome dado, ou None."""
        for t in self.tracks:
            if t.name == name:
                return t
        return None

    def get_tracks_by_type(self, track_type: TrackType) -> List[Track]:
        """Retorna todas as faixas de um tipo específico."""
        return [t for t in self.tracks if t.type == track_type]

    def get_active_tracks(self, time: float) -> List[Track]:
        """Retorna faixas que possuem algum clip ativo no instante dado."""
        return [t for t in self.tracks if t.get_clips_at(time)]

    # ------------------------------------------------------------------
    # Duração
    # ------------------------------------------------------------------

    def _update_length(self) -> None:
        """Recalcula a duração total como o fim do clip mais distante."""
        if not self.tracks:
            self.length = 0.0
            return
        ends = [t.get_duration() for t in self.tracks]
        self.length = max(ends) if ends else 0.0

    # ------------------------------------------------------------------
    # Serialização
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tracks": [t.to_dict() for t in self.tracks],
            "length": self.length,
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Reconstrói a timeline a partir de um dicionário."""
        self.tracks = []
        for track_data in data.get("tracks", []):
            self.tracks.append(Track.from_dict(track_data))
        self.length = data.get("length", 0.0)
        self._update_length()   # recalcula para garantir consistência

    def __repr__(self) -> str:
        return f"Timeline(tracks={len(self.tracks)}, length={self.length:.2f}s)"