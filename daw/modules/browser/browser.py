# modules/browser/browser.py
"""
Modelo de dados do browser de arquivos de áudio.

Responsabilidade:
    Representar o estado de navegação (diretório atual, lista de itens,
    seleção) sem nenhuma dependência de bpy.
    A UI (ui.py) e os operadores (operators.py) leem/escrevem este estado.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .utils import (
    list_audio_files,
    list_subdirs,
    is_audio_file,
    friendly_name,
    file_size_str,
    get_extension,
    normalize_path,
)


@dataclass
class BrowserItem:
    """
    Um item exibido no browser: pode ser arquivo de áudio ou subdiretório.
    """
    path:       str
    name:       str
    is_dir:     bool   = False
    size_str:   str    = ""
    extension:  str    = ""
    is_favorite: bool  = False

    @classmethod
    def from_path(cls, path: str) -> "BrowserItem":
        is_dir = os.path.isdir(path)
        return cls(
            path      = path,
            name      = os.path.basename(path) if is_dir else friendly_name(path),
            is_dir    = is_dir,
            size_str  = "" if is_dir else file_size_str(path),
            extension = "" if is_dir else get_extension(path),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path":      self.path,
            "name":      self.name,
            "is_dir":    self.is_dir,
            "extension": self.extension,
        }


class FileBrowser:
    """
    Estado de navegação do browser de arquivos.

    Singleton leve — uma instância por sessão, resetada ao trocar de projeto.
    """

    def __init__(self) -> None:
        self._history:    List[str] = []         # pilha de diretórios visitados
        self._current:    str       = os.path.expanduser("~")
        self._items:      List[BrowserItem] = []
        self._selected:   Optional[str] = None   # path do item selecionado
        self._filter:     str = ""               # texto de filtro por nome
        self._show_dirs:  bool = True
        self._recursive:  bool = False

        self.refresh()

    # ------------------------------------------------------------------
    # Navegação
    # ------------------------------------------------------------------

    def navigate(self, path: str) -> None:
        """Navega para um diretório, empilhando o atual no histórico."""
        path = normalize_path(path)
        if not os.path.isdir(path):
            return
        if path != self._current:
            self._history.append(self._current)
        self._current = path
        self._selected = None
        self.refresh()

    def go_back(self) -> None:
        """Volta ao diretório anterior."""
        if self._history:
            self._current = self._history.pop()
            self._selected = None
            self.refresh()

    def go_up(self) -> None:
        """Sobe um nível na hierarquia."""
        parent = os.path.dirname(self._current)
        if parent != self._current:
            self.navigate(parent)

    def refresh(self) -> None:
        """Recarrega a lista de itens do diretório atual."""
        items: List[BrowserItem] = []

        # Subdiretórios primeiro
        if self._show_dirs:
            for d in list_subdirs(self._current):
                items.append(BrowserItem.from_path(d))

        # Arquivos de áudio
        for f in list_audio_files(self._current, recursive=self._recursive):
            item = BrowserItem.from_path(f)
            if self._filter and self._filter.lower() not in item.name.lower():
                continue
            items.append(item)

        self._items = items

    # ------------------------------------------------------------------
    # Seleção
    # ------------------------------------------------------------------

    def select(self, path: str) -> None:
        self._selected = path

    def get_selected(self) -> Optional[BrowserItem]:
        if self._selected is None:
            return None
        for item in self._items:
            if item.path == self._selected:
                return item
        return None

    # ------------------------------------------------------------------
    # Filtro
    # ------------------------------------------------------------------

    def set_filter(self, text: str) -> None:
        self._filter = text
        self.refresh()

    def clear_filter(self) -> None:
        self._filter = ""
        self.refresh()

    # ------------------------------------------------------------------
    # Propriedades
    # ------------------------------------------------------------------

    @property
    def current_path(self) -> str:
        return self._current

    @property
    def items(self) -> List[BrowserItem]:
        return list(self._items)

    @property
    def selected_path(self) -> Optional[str]:
        return self._selected

    @property
    def can_go_back(self) -> bool:
        return bool(self._history)

    @property
    def filter_text(self) -> str:
        return self._filter

    @property
    def recursive(self) -> bool:
        return self._recursive

    @recursive.setter
    def recursive(self, value: bool) -> None:
        self._recursive = value
        self.refresh()

    def __repr__(self) -> str:
        return (
            f"FileBrowser(path='{self._current}', "
            f"items={len(self._items)}, filter='{self._filter}')"
        )


# Instância global da sessão
BROWSER = FileBrowser()