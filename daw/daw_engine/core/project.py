# core/project.py
"""
Representação de um projeto DAW com serialização para JSON.
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional

from .settings import Settings
from .timeline import Timeline, Track, Clip
from .constants import TrackType, ClipType


class Project:
    """Contém todos os dados de uma sessão, com suporte a salvar/carregar."""

    def __init__(self, name: str = "Untitled", path: Optional[str] = None):
        self.name = name
        self.path = path or os.getcwd()
        self.settings = Settings()
        self.timeline = Timeline()
        self.media_files: List[str] = []  # caminhos relativos ou absolutos

    def save(self, filepath: Optional[str] = None) -> None:
        """Salva o projeto em formato JSON."""
        if filepath is None:
            filepath = os.path.join(self.path, f"{self.name}.dawproj")

        data = {
            "name": self.name,
            "path": self.path,
            "settings": self.settings.to_dict(),
            "timeline": self.timeline.to_dict(),
            "media_files": self.media_files,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def load(self, filepath: str) -> None:
        """Carrega um projeto a partir de um arquivo JSON."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.name = data.get("name", "Untitled")
        self.path = data.get("path", os.path.dirname(filepath))
        self.settings.from_dict(data.get("settings", {}))
        self.media_files = data.get("media_files", [])

        # Reconstrói a timeline
        timeline_data = data.get("timeline", {})
        self.timeline.from_dict(timeline_data)

    # ------------------------------------------------------------
    # Métodos auxiliares
    # ------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Converte o projeto para dicionário (útil para exportação)."""
        return {
            "name": self.name,
            "path": self.path,
            "settings": self.settings.to_dict(),
            "timeline": self.timeline.to_dict(),
            "media_files": self.media_files,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Project:
        """Cria um projeto a partir de um dicionário (útil para importação)."""
        proj = cls(data.get("name", "Untitled"), data.get("path"))
        proj.settings.from_dict(data.get("settings", {}))
        proj.timeline.from_dict(data.get("timeline", {}))
        proj.media_files = data.get("media_files", [])
        return proj


# ------------------------------------------------------------
# Extensão dos objetos de timeline para serialização
# ------------------------------------------------------------

def _clip_to_dict(clip: Clip) -> Dict[str, Any]:
    """Serializa um Clip."""
    return {
        "name": clip.name,
        "start": clip.start,
        "duration": clip.duration,
        "type": clip.type.value if hasattr(clip, "type") else ClipType.AUDIO.value,
        "data": clip.data,  # Pode ser um caminho de arquivo ou eventos MIDI
    }


def _clip_from_dict(data: Dict[str, Any]) -> Clip:
    """Reconstrói um Clip a partir de dicionário."""
    clip = Clip(
        name=data.get("name", ""),
        start=data.get("start", 0.0),
        duration=data.get("duration", 1.0),
        data=data.get("data"),
    )
    # Define o tipo (se presente no dict)
    if "type" in data:
        try:
            clip.type = ClipType(data["type"])
        except ValueError:
            pass
    return clip


# Monkey-patch para os métodos de serialização de Track e Timeline
# (poderíamos criar subclasses, mas aqui extendemos as existentes)

def _track_to_dict(track: Track) -> Dict[str, Any]:
    return {
        "name": track.name,
        "type": track.type.value if hasattr(track, "type") else TrackType.AUDIO.value,
        "clips": [_clip_to_dict(clip) for clip in track.clips],
        "volume": track.volume,
        "pan": track.pan,
        "mute": track.mute,
        "solo": track.solo,
    }


def _track_from_dict(data: Dict[str, Any]) -> Track:
    track = Track(
        name=data.get("name", ""),
        track_type=data.get("type", TrackType.AUDIO.value)
    )
    track.volume = data.get("volume", 0.0)
    track.pan = data.get("pan", 0.0)
    track.mute = data.get("mute", False)
    track.solo = data.get("solo", False)
    for clip_data in data.get("clips", []):
        track.add_clip(_clip_from_dict(clip_data))
    return track


# Atualiza os métodos to_dict/from_dict das classes existentes
# (ou podemos criar funções auxiliares no módulo)

# Para não modificar as classes originais, vamos sobrescrever temporariamente:
# (na prática, seria melhor ter métodos próprios, mas aqui mantemos compatibilidade)

def patch_timeline():
    """Aplica os métodos de serialização à classe Timeline."""
    original_to_dict = Timeline.to_dict
    original_from_dict = Timeline.from_dict

    def new_to_dict(self):
        return {
            "tracks": [_track_to_dict(t) for t in self.tracks],
            "length": self.length,
        }
    Timeline.to_dict = new_to_dict

    def new_from_dict(self, data):
        self.tracks = []
        for track_data in data.get("tracks", []):
            self.tracks.append(_track_from_dict(track_data))
        self._update_length()
    Timeline.from_dict = new_from_dict

# Chamar o patch no carregamento do módulo
patch_timeline()