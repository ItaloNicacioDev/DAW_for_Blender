# modules/project/utils.py
"""
Utilitários do módulo Project.

Responsabilidade:
    Funções auxiliares para manipulação de caminhos, nomes de arquivo,
    validação de projetos, e detecção de mudanças.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import bpy

PROJECT_EXTENSION = ".dawproj"
BACKUP_EXTENSION = ".dawbackup"
TEMPLATE_EXTENSION = ".dawtemplate"


def get_default_project_dir() -> Path:
    """Diretório padrão para projetos da DAW."""
    return Path(bpy.utils.user_resource('SCRIPTS', path="presets/daw_projects", create=True))


def get_backup_dir() -> Path:
    """Diretório padrão para backups."""
    path = get_default_project_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_templates_dir() -> Path:
    """Diretório padrão para templates."""
    path = get_default_project_dir() / "templates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_extension(filepath: str, ext: str = PROJECT_EXTENSION) -> str:
    """Garante que o filepath tenha a extensão correta."""
    if not filepath.lower().endswith(ext.lower()):
        filepath += ext
    return filepath


def get_project_name_from_path(filepath: str) -> str:
    """Extrai o nome do projeto do caminho do arquivo."""
    return Path(filepath).stem


def is_valid_project_file(filepath: str) -> bool:
    """Verifica se um arquivo é um projeto válido da DAW."""
    path = Path(filepath)
    if not path.exists() or not path.is_file():
        return False
    if not path.suffix.lower() == PROJECT_EXTENSION.lower():
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return "version" in data and "modules" in data
    except (OSError, json.JSONDecodeError):
        return False


def generate_backup_filename(project_name: str, index: int = 0) -> str:
    """Gera o nome de um arquivo de backup com índice."""
    if index > 0:
        return f"{project_name}_backup_{index:03d}{BACKUP_EXTENSION}"
    return f"{project_name}_backup{BACKUP_EXTENSION}"


def list_backup_files(project_name: str) -> list:
    """Lista os arquivos de backup de um projeto."""
    backup_dir = get_backup_dir()
    pattern = f"{project_name}_backup*{BACKUP_EXTENSION}"
    return sorted(backup_dir.glob(pattern))


def cleanup_old_backups(project_name: str, max_backups: int = 10) -> None:
    """Remove backups antigos mantendo apenas os mais recentes."""
    backups = list_backup_files(project_name)
    if len(backups) > max_backups:
        for old in backups[:-max_backups]:
            try:
                old.unlink()
            except OSError:
                pass