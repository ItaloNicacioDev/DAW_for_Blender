# modules/project/__init__.py
"""
Módulo Project da DAW para Blender.

Responsabilidade:
    Gerenciar o ciclo de vida de projetos da DAW: criação, abertura,
    salvamento, backup, autosave, templates e exportação/importação.

Arquitetura
-----------
1. Modelo puro / lógica:
   utils.py      → caminhos, nomes, validação
   save.py       → serialização do estado para JSON
   load.py       → desserialização do JSON para o estado
   backup.py     → criação e restauração de backups
   autosave.py   → timer periódico de salvamento automático
   templates.py  → templates embutidos e do usuário

2. Integração Blender (bpy):
   properties.py → PropertyGroups RNA (metadados do projeto)
   operators.py  → Operators (novo, abrir, salvar, backup, etc.)
   ui.py         → Painéis, listas e menus
   register.py   → Registro/desregistro

Uso típico:
    from daw.modules.project import save_project, load_project
    save_project("/path/to/project.dawproj", scene)
    load_project("/path/to/project.dawproj", scene)
"""
from __future__ import annotations

# ------------------------------------------------------------------ #
# Lógica de projeto
# ------------------------------------------------------------------ #
from .save import save_project, serialize_project, CURRENT_PROJECT_VERSION
from .load import load_project, deserialize_project
from .backup import create_backup, restore_backup, list_backups
from .autosave import start_autosave, stop_autosave
from .templates import (
    apply_template, apply_user_template, save_user_template,
    list_user_templates, get_builtin_template_names, BUILTIN_TEMPLATES,
)
from .utils import (
    get_default_project_dir, get_backup_dir, get_templates_dir,
    ensure_extension, is_valid_project_file, get_project_name_from_path,
    cleanup_old_backups,
)

# ------------------------------------------------------------------ #
# Integração Blender
# ------------------------------------------------------------------ #
from .register import register, unregister

__all__ = [
    # Save/Load
    "save_project", "serialize_project", "CURRENT_PROJECT_VERSION",
    "load_project", "deserialize_project",
    # Backup
    "create_backup", "restore_backup", "list_backups",
    # Autosave
    "start_autosave", "stop_autosave",
    # Templates
    "apply_template", "apply_user_template", "save_user_template",
    "list_user_templates", "get_builtin_template_names", "BUILTIN_TEMPLATES",
    # Utils
    "get_default_project_dir", "get_backup_dir", "get_templates_dir",
    "ensure_extension", "is_valid_project_file", "get_project_name_from_path",
    "cleanup_old_backups",
    # Registro Blender
    "register", "unregister",
]