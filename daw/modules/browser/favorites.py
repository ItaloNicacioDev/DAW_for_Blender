# modules/browser/favorites.py
"""
Favoritos do browser — pastas e arquivos marcados pelo usuário.
Persistidos em JSON na pasta de preferências do usuário.
Sem bpy.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


def _prefs_path() -> str:
    base = os.path.join(os.path.expanduser("~"), ".config", "blender_daw")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "favorites.json")


class Favorites:
    """
    Lista de paths favoritos (pastas e arquivos) com persistência JSON.
    """

    def __init__(self) -> None:
        self._items: List[Dict[str, str]] = []   # [{"path": ..., "label": ...}]
        self._load()

    # ------------------------------------------------------------------
    # Edição
    # ------------------------------------------------------------------

    def add(self, path: str, label: str = "") -> None:
        path = os.path.normpath(path)
        if self.contains(path):
            return
        self._items.append({"path": path, "label": label or os.path.basename(path)})
        self._save()

    def remove(self, path: str) -> bool:
        path = os.path.normpath(path)
        for i, item in enumerate(self._items):
            if item["path"] == path:
                self._items.pop(i)
                self._save()
                return True
        return False

    def rename(self, path: str, new_label: str) -> bool:
        path = os.path.normpath(path)
        for item in self._items:
            if item["path"] == path:
                item["label"] = new_label
                self._save()
                return True
        return False

    def clear(self) -> None:
        self._items.clear()
        self._save()

    def toggle(self, path: str) -> bool:
        """Adiciona se não estiver, remove se estiver. Retorna True se foi adicionado."""
        if self.contains(path):
            self.remove(path)
            return False
        self.add(path)
        return True

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def contains(self, path: str) -> bool:
        path = os.path.normpath(path)
        return any(f["path"] == path for f in self._items)

    @property
    def items(self) -> List[Dict[str, str]]:
        return list(self._items)

    @property
    def paths(self) -> List[str]:
        return [f["path"] for f in self._items]

    def __len__(self) -> int:
        return len(self._items)

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------

    def _save(self) -> None:
        try:
            with open(_prefs_path(), "w", encoding="utf-8") as f:
                json.dump(self._items, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def _load(self) -> None:
        path = _prefs_path()
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._items = data
        except (OSError, json.JSONDecodeError):
            self._items = []

    def __repr__(self) -> str:
        return f"Favorites({len(self._items)} items)"


# Instância global
FAVORITES = Favorites()