# core/session.py
"""Gerencia a sessão atual do usuário (projeto aberto, preferências)."""
from .project import Project
from .settings import Settings

class Session:
    """Estado da sessão do usuário."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.current_project = None
            cls._instance.settings = Settings()
            cls._instance.is_playing = False
            cls._instance.is_recording = False
        return cls._instance

    def new_project(self, name="Novo Projeto"):
        self.current_project = Project(name)
        return self.current_project

    def open_project(self, filepath):
        proj = Project()
        proj.load(filepath)
        self.current_project = proj
        return proj

    def save_project(self):
        if self.current_project:
            self.current_project.save()

    def close_project(self):
        self.current_project = None