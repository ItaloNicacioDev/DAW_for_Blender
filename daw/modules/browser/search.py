# modules/browser/search.py
"""
Busca de arquivos de áudio no browser.
Sem bpy — lógica pura.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from .utils import list_audio_files, friendly_name, get_extension, AUDIO_EXTENSIONS


@dataclass
class SearchResult:
    path:      str
    name:      str
    extension: str
    score:     int = 0   # relevância (maior = mais relevante)

    def to_dict(self):
        return {"path": self.path, "name": self.name, "extension": self.extension}


class AudioSearch:
    """
    Busca de arquivos de áudio por nome dentro de um diretório raiz.

    Suporta:
    - Busca por substring no nome
    - Filtro por extensão
    - Busca recursiva
    - Limite de resultados
    """

    def __init__(self) -> None:
        self._last_query:   str              = ""
        self._last_results: List[SearchResult] = []
        self._search_root:  str              = os.path.expanduser("~")
        self._max_results:  int              = 200

    def set_root(self, path: str) -> None:
        self._search_root = path

    def search(
        self,
        query:      str,
        root:       Optional[str]      = None,
        extensions: Optional[set]      = None,
        recursive:  bool               = True,
    ) -> List[SearchResult]:
        """
        Busca arquivos cujo nome contém 'query' (case-insensitive).

        Args:
            query:      texto a buscar
            root:       diretório raiz (usa self._search_root se None)
            extensions: conjunto de extensões a incluir (ex: {'.wav', '.flac'})
            recursive:  se True, busca em subpastas

        Returns:
            Lista de SearchResult ordenada por relevância.
        """
        if not query.strip():
            self._last_results = []
            return []

        root = root or self._search_root
        exts = extensions or AUDIO_EXTENSIONS
        q    = query.strip().lower()

        files  = list_audio_files(root, recursive=recursive)
        results: List[SearchResult] = []

        for path in files:
            ext  = get_extension(path)
            if ext not in exts:
                continue
            name = friendly_name(path).lower()
            if q not in name:
                continue

            # Score: match no início > match no meio
            score = 10 if name.startswith(q) else (5 if name == q else 1)

            results.append(SearchResult(
                path=path,
                name=os.path.splitext(os.path.basename(path))[0],
                extension=ext,
                score=score,
            ))

            if len(results) >= self._max_results:
                break

        results.sort(key=lambda r: (-r.score, r.name))
        self._last_query   = query
        self._last_results = results
        return results

    @property
    def last_results(self) -> List[SearchResult]:
        return list(self._last_results)

    @property
    def last_query(self) -> str:
        return self._last_query

    def clear(self) -> None:
        self._last_query   = ""
        self._last_results = []


# Instância global
SEARCH = AudioSearch()