    # core/project.py
"""Representação de um projeto DAW."""
import os
import json
from .settings import Settings
from .timeline import Timeline

class Project:
    """Contém todos os dados de uma sessão."""
    def __init__(self, name="Untitled", path=None):
        self.name = name
        self.path = path or os.getcwd()
        self.settings = Settings()
        self.timeline = Timeline()
        self.tracks = []  # lista de objetos Track
        self.media_files = []  # referências a arquivos de áudio

    def save(self, filepath=None):
        """Salva o projeto em formato JSON."""
        if filepath is None:
            filepath = os.path.join(self.path, f"{self.name}.dawproj")
        data = {
            'name': self.name,
            'settings': self.settings.to_dict(),
            'timeline': self.timeline.to_dict(),
            'tracks': [track.to_dict() for track in self.tracks],
            'media_files': self.media_files
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

    def load(self, filepath):
        """Carrega um projeto a partir de JSON."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.name = data['name']
        self.settings.from_dict(data['settings'])
        self.timeline.from_dict(data['timeline'])
        # Recriar tracks, etc.