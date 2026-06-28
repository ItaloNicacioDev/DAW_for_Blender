# core/timeline.py
"""Representação da linha do tempo e dos clipes."""
class Clip:
    """Um clipe de áudio ou MIDI."""
    def __init__(self, name="", start=0.0, duration=1.0, data=None):
        self.name = name
        self.start = start
        self.duration = duration
        self.data = data  # pode ser um arquivo de áudio, eventos MIDI, etc.

    def to_dict(self):
        return {
            'name': self.name,
            'start': self.start,
            'duration': self.duration,
            'data': self.data  # serialização mais complexa
        }

class Track:
    """Uma faixa (áudio, MIDI, grupo)."""
    def __init__(self, name="", track_type="audio"):
        self.name = name
        self.type = track_type
        self.clips = []  # lista de Clip
        self.volume = 0.0
        self.pan = 0.0
        self.mute = False
        self.solo = False

    def add_clip(self, clip):
        self.clips.append(clip)

    def to_dict(self):
        return {
            'name': self.name,
            'type': self.type,
            'clips': [c.to_dict() for c in self.clips],
            'volume': self.volume,
            'pan': self.pan,
            'mute': self.mute,
            'solo': self.solo
        }

class Timeline:
    """Agrupa todas as faixas e fornece métodos de edição."""
    def __init__(self):
        self.tracks = []
        self.length = 0.0  # duração total em segundos

    def add_track(self, track):
        self.tracks.append(track)
        self._update_length()

    def remove_track(self, track):
        self.tracks.remove(track)
        self._update_length()

    def _update_length(self):
        # Calcula o maior fim de clipe
        max_end = 0.0
        for track in self.tracks:
            for clip in track.clips:
                end = clip.start + clip.duration
                if end > max_end:
                    max_end = end
        self.length = max_end

    def to_dict(self):
        return {
            'tracks': [t.to_dict() for t in self.tracks],
            'length': self.length
        }

    def from_dict(self, data):
        # Reconstruir tracks e clipes
        pass