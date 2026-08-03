# modules/updater/properties.py
"""
Estado (runtime, não salvo no .blend) do sistema de atualização.
Vive em `bpy.types.WindowManager.daw_updater`.
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy.types import PropertyGroup

_STATUS_ITEMS = [
    ('IDLE', "Ocioso", "Nenhuma verificação em andamento"),
    ('CHECKING', "Verificando", "Consultando o GitHub"),
    ('UP_TO_DATE', "Atualizado", "Já está na versão mais recente"),
    ('UPDATE_AVAILABLE', "Atualização disponível", "Há uma nova versão"),
    ('DOWNLOADING', "Baixando", "Baixando o pacote da atualização"),
    ('INSTALLING', "Instalando", "Instalando os arquivos"),
    ('DONE_INSTALL', "Instalado", "Atualização instalada — reinicie o Blender"),
    ('ERROR', "Erro", "Ocorreu um erro"),
]


class DAW_UpdaterState(PropertyGroup):
    status: EnumProperty(items=_STATUS_ITEMS, default='IDLE')
    progress: FloatProperty(default=0.0, min=0.0, max=1.0)
    latest_version: StringProperty(default="")
    changelog: StringProperty(default="")
    download_url: StringProperty(default="")
    release_url: StringProperty(default="")
    error: StringProperty(default="")
    needs_restart: BoolProperty(default=False)


def get_updater_state(context=None) -> "DAW_UpdaterState":
    context = context or bpy.context
    return context.window_manager.daw_updater


classes = [DAW_UpdaterState]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.daw_updater = bpy.props.PointerProperty(type=DAW_UpdaterState)


def unregister():
    if hasattr(bpy.types.WindowManager, "daw_updater"):
        del bpy.types.WindowManager.daw_updater
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)