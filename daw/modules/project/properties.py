# modules/project/properties.py
"""
Propriedades RNA do Blender para o módulo Project.

Responsabilidade:
    Armazenar metadados do projeto (nome, caminho, configurações
    de autosave) e expor o estado para os operadores.
    Fica em context.scene.daw_project.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .templates import get_builtin_template_names


# ------------------------------------------------------------------ #
# Configurações do projeto
# ------------------------------------------------------------------ #
class ProjectSettingsProperties(PropertyGroup):
    """Configurações gerais do projeto."""

    autosave_enabled: BoolProperty(name="Autosave", default=False)
    autosave_interval: IntProperty(name="Intervalo (s)", default=120, min=30, max=600)
    max_backups: IntProperty(name="Máx. Backups", default=10, min=1, max=100)

    default_bpm: IntProperty(name="BPM Padrão", default=120, min=1, max=999)
    default_time_signature_num: IntProperty(name="Compasso (num)", default=4, min=1, max=32)
    default_time_signature_den: IntProperty(name="Compasso (den)", default=4, min=1, max=32)


# ------------------------------------------------------------------ #
# Estado global do Project
# ------------------------------------------------------------------ #
class ProjectProperties(PropertyGroup):
    """Metadados e estado do projeto atual."""

    name: StringProperty(name="Nome do Projeto", default="Untitled")
    filepath: StringProperty(name="Arquivo", default="", subtype='FILE_PATH')
    is_modified: BoolProperty(name="Modificado", default=False)

    template: EnumProperty(
        name="Template",
        items=lambda self, context: [
            ("empty", "Vazio", "Projeto vazio"),
            ("basic", "Básico", "Projeto com faixas básicas"),
        ] + [(n, n.title(), f"Template '{n}'") for n in get_builtin_template_names() if n not in ("empty", "basic")],
        default=0,  # índice, não string -- quando `items` é uma função (dinâmica),
                    # o Blender só aceita 'default' inteiro, nunca o identificador
                    # como string (era isso que causava
                    # "TypeError: EnumProperty(...): 'default' can only be an
                    # integer when 'items' is a function" e derrubava o registro
                    # de ProjectProperties inteiro). Índice 0 = "empty", que é
                    # sempre o primeiro item da lista, então o comportamento é
                    # o mesmo que default="empty" pretendia.
    )

    settings: PointerProperty(type=ProjectSettingsProperties)

    @property
    def has_filepath(self) -> bool:
        return bool(self.filepath)

    @property
    def display_name(self) -> str:
        if self.filepath:
            from pathlib import Path
            return Path(self.filepath).stem
        return self.name


_ALL_CLASSES = [
    ProjectSettingsProperties,
    ProjectProperties,
]


def register() -> None:
    for cls in _ALL_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_project = bpy.props.PointerProperty(type=ProjectProperties)
    bpy.types.Scene.daw_project_name = bpy.props.StringProperty(name="Nome do Projeto", default="Untitled")


def unregister() -> None:
    if hasattr(bpy.types.Scene, "daw_project_name"):
        del bpy.types.Scene.daw_project_name
    if hasattr(bpy.types.Scene, "daw_project"):
        del bpy.types.Scene.daw_project
    for cls in reversed(_ALL_CLASSES):
        bpy.utils.unregister_class(cls)