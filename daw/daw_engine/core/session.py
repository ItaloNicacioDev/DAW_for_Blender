# core/session.py
"""
Gerencia a sessão atual do usuário (projeto aberto, preferências).

Correção vs versão anterior:
- new_project() não verificava se já havia um projeto não salvo aberto —
  agora retorna um aviso opcional via has_unsaved_changes (a decisão de
  perguntar ao usuário fica para a camada de UI, mas o dado fica disponível).
- save_project() engolia silenciosamente o caso current_project is None —
  agora levanta exceção clara para a Engine logar.
- Faltava is_project_open e has_unsaved_changes.
- open_project() não tratava FileNotFoundError de forma explícita.
"""
from __future__ import annotations

import os
from typing import Optional

from .project import Project
from .settings import Settings


class Session:
    """
    Estado da sessão do usuário: projeto atual aberto + preferências globais.

    Singleton — sempre retorna a mesma instância.
    """

    _instance: Optional["Session"] = None

    def __new__(cls) -> "Session":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst.current_project: Optional[Project] = None
            inst.settings = Settings()
            inst.is_playing: bool = False
            inst.is_recording: bool = False
            inst._dirty: bool = False   # True se há alterações não salvas
            cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Gerenciamento de projeto
    # ------------------------------------------------------------------

    def new_project(self, name: str = "Novo Projeto") -> Project:
        """Cria um novo projeto vazio e o define como atual."""
        self.current_project = Project(name)
        self._dirty = False
        return self.current_project

    def open_project(self, filepath: str) -> Project:
        """
        Abre um projeto do disco.
        Levanta FileNotFoundError se o caminho não existir.
        """
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Arquivo de projeto não encontrado: {filepath}")

        proj = Project()
        proj.load(filepath)
        self.current_project = proj
        self._dirty = False
        return proj

    def save_project(self, filepath: Optional[str] = None) -> None:
        """
        Salva o projeto atual.
        Levanta RuntimeError se não houver projeto aberto.
        """
        if self.current_project is None:
            raise RuntimeError("Nenhum projeto aberto para salvar.")
        self.current_project.save(filepath)
        self._dirty = False

    def close_project(self) -> None:
        """Fecha o projeto atual (sem salvar)."""
        self.current_project = None
        self._dirty = False

    def mark_dirty(self) -> None:
        """Sinaliza que o projeto tem alterações não salvas."""
        self._dirty = True

    # ------------------------------------------------------------------
    # Consulta de estado
    # ------------------------------------------------------------------

    @property
    def is_project_open(self) -> bool:
        return self.current_project is not None

    @property
    def has_unsaved_changes(self) -> bool:
        return self._dirty

    @property
    def project_name(self) -> str:
        return self.current_project.name if self.current_project else ""

    def __repr__(self) -> str:
        name = self.project_name or "(nenhum projeto)"
        dirty = " *" if self._dirty else ""
        return f"Session(project='{name}'{dirty})"