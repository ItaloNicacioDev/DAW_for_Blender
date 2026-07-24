# modules/project/backup.py
"""
Backup de projetos da DAW.

Responsabilidade:
    Criar cópias de segurança de projetos com versionamento automático,
    permitir restauração de backups e gerenciar a retenção.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import bpy

from .save import save_project
from .utils import (
    get_backup_dir, generate_backup_filename, list_backup_files,
    cleanup_old_backups, BACKUP_EXTENSION,
)


def create_backup(scene, project_name: str = "untitled", max_backups: int = 10) -> Optional[str]:
    """
    Cria um backup do estado atual do projeto.

    Returns:
        Caminho do arquivo de backup criado, ou None em caso de erro.
    """
    backup_dir = get_backup_dir()
    existing = list_backup_files(project_name)
    index = len(existing)

    filename = generate_backup_filename(project_name, index)
    filepath = str(backup_dir / filename)

    if save_project(filepath, scene):
        cleanup_old_backups(project_name, max_backups)
        return filepath
    return None


def restore_backup(filepath: str, scene) -> bool:
    """Restaura um projeto a partir de um arquivo de backup."""
    from .load import load_project
    return load_project(filepath, scene)


def list_backups(project_name: str) -> list:
    """Lista os backups disponíveis para um projeto."""
    files = list_backup_files(project_name)
    return [str(f) for f in files]