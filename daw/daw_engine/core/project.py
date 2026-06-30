# core/project.py
"""
Representação de um projeto DAW com serialização para JSON.

Correção vs versão anterior:
- A versão anterior fazia monkey-patch de Timeline.to_dict/from_dict em
  tempo de import (patch_timeline() rodava automaticamente). Isso é
  frágil: depende de project.py ser importado antes de qualquer uso de
  Timeline, duplica lógica que já existe em timeline.py, e quebra
  silenciosamente se a ordem de import mudar. Removido por completo —
  Timeline/Track/Clip já implementam to_dict/from_dict corretamente
  (ver core/timeline.py revisado).
- save() não criava o diretório de destino se não existisse — corrigido.
- load() não validava a versão do projeto (PROJECT_VERSION) — agora
  avisa se o arquivo for de uma versão diferente (não impede de abrir,
  mas loga o aviso para facilitar debug de migração futura).
- Extensão de arquivo usava ".dawproj" hardcoded — agora usa
  PROJECT_EXTENSION de constants.py para manter consistência.
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional

from .settings import Settings
from .timeline import Timeline
from .constants import PROJECT_EXTENSION, PROJECT_VERSION, DEFAULT_PROJECT_NAME


class Project:
    """
    Contém todos os dados de uma sessão DAW, com suporte a salvar/carregar
    em formato JSON (.blendaw / PROJECT_EXTENSION).
    """

    def __init__(self, name: str = DEFAULT_PROJECT_NAME, path: Optional[str] = None) -> None:
        self.name: str = name
        self.path: str = path or os.getcwd()
        self.settings = Settings()
        self.timeline = Timeline()
        self.media_files: List[str] = []   # caminhos de arquivos de áudio referenciados

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------

    def save(self, filepath: Optional[str] = None) -> None:
        """
        Salva o projeto em formato JSON.
        Se filepath não for dado, usa self.path/self.name + PROJECT_EXTENSION.
        Cria o diretório de destino se necessário.
        """
        if filepath is None:
            filepath = os.path.join(self.path, f"{self.name}{PROJECT_EXTENSION}")

        directory = os.path.dirname(filepath)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)

        data = self.to_dict()
        data["_version"] = PROJECT_VERSION

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def load(self, filepath: str) -> None:
        """
        Carrega um projeto a partir de um arquivo JSON.
        Levanta FileNotFoundError se o arquivo não existir.
        """
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Arquivo de projeto não encontrado: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        file_version = data.get("_version", 0)
        if file_version != PROJECT_VERSION:
            from .logger import LOGGER
            LOGGER.warning(
                "Project",
                f"Versão do arquivo ({file_version}) difere da versão atual "
                f"({PROJECT_VERSION}). Pode haver incompatibilidades."
            )

        self.name = data.get("name", DEFAULT_PROJECT_NAME)
        self.path = data.get("path", os.path.dirname(filepath))
        self.settings.from_dict(data.get("settings", {}))
        self.media_files = data.get("media_files", [])
        self.timeline.from_dict(data.get("timeline", {}))

    # ------------------------------------------------------------------
    # Conversão dict <-> objeto
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Converte o projeto para dicionário (salvar ou exportar)."""
        return {
            "name": self.name,
            "path": self.path,
            "settings": self.settings.to_dict(),
            "timeline": self.timeline.to_dict(),
            "media_files": self.media_files,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        """Cria um projeto a partir de um dicionário (importação)."""
        proj = cls(data.get("name", DEFAULT_PROJECT_NAME), data.get("path"))
        proj.settings.from_dict(data.get("settings", {}))
        proj.timeline.from_dict(data.get("timeline", {}))
        proj.media_files = data.get("media_files", [])
        return proj

    # ------------------------------------------------------------------
    # Gerenciamento de arquivos de mídia
    # ------------------------------------------------------------------

    def add_media_file(self, filepath: str) -> None:
        """Registra um arquivo de áudio usado pelo projeto (evita duplicatas)."""
        if filepath not in self.media_files:
            self.media_files.append(filepath)

    def remove_media_file(self, filepath: str) -> bool:
        if filepath in self.media_files:
            self.media_files.remove(filepath)
            return True
        return False

    def get_missing_media(self) -> List[str]:
        """Retorna a lista de arquivos de mídia referenciados que não existem no disco."""
        return [f for f in self.media_files if not os.path.isfile(f)]

    def __repr__(self) -> str:
        return f"Project('{self.name}', tracks={len(self.timeline.tracks)})"