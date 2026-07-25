# modules/render/animation.py
"""
Handlers de progresso de renderização de vídeo.

Estes handlers usam os eventos nativos de render do Blender
(bpy.app.handlers.render_*) para manter DAW_RenderSettings sincronizado
com o andamento real da renderização de animação/vídeo.
"""
from __future__ import annotations

import bpy
from bpy.app.handlers import persistent


def _get_settings(scene):
    return scene.daw_render_settings


@persistent
def render_init_handler(scene, depsgraph=None):
    settings = _get_settings(scene)
    settings.is_rendering = True
    settings.render_cancelled = False
    settings.render_progress = 0.0
    settings.render_status_text = "Iniciando renderização de vídeo..."


@persistent
def render_pre_handler(scene, depsgraph=None):
    settings = _get_settings(scene)
    start, end = scene.frame_start, scene.frame_end
    current = scene.frame_current
    total = max(end - start, 1)
    settings.render_progress = max(0.0, min(1.0, (current - start) / total))
    settings.render_status_text = f"Renderizando frame {current} de {end}"


@persistent
def render_post_handler(scene, depsgraph=None):
    settings = _get_settings(scene)
    start, end = scene.frame_start, scene.frame_end
    current = scene.frame_current
    total = max(end - start, 1)
    settings.render_progress = max(0.0, min(1.0, (current - start) / total))


@persistent
def render_complete_handler(scene, depsgraph=None):
    settings = _get_settings(scene)
    settings.is_rendering = False
    settings.render_progress = 1.0
    settings.render_status_text = "Renderização de vídeo concluída"


@persistent
def render_cancel_handler(scene, depsgraph=None):
    settings = _get_settings(scene)
    settings.is_rendering = False
    settings.render_cancelled = True
    settings.render_status_text = "Renderização de vídeo cancelada"


_HANDLER_MAP = [
    (bpy.app.handlers.render_init, render_init_handler),
    (bpy.app.handlers.render_pre, render_pre_handler),
    (bpy.app.handlers.render_post, render_post_handler),
    (bpy.app.handlers.render_complete, render_complete_handler),
    (bpy.app.handlers.render_cancel, render_cancel_handler),
]


def start_render_tracking():
    """Registra os handlers de progresso. Chamar antes de iniciar a renderização de vídeo."""
    for handler_list, func in _HANDLER_MAP:
        if func not in handler_list:
            handler_list.append(func)


def stop_render_tracking():
    """Remove os handlers de progresso. Chamar sempre ao final (mesmo em erro)."""
    for handler_list, func in _HANDLER_MAP:
        if func in handler_list:
            handler_list.remove(func)


classes = []


def register():
    pass


def unregister():
    stop_render_tracking()