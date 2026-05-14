bl_info = {
    "name": "Blender DAW",
    "author": "DAW Project",
    "version": (0, 3, 0),
    "blender": (5, 0, 0),
    "location": "DAW Workspace",
    "description": "DAW completa integrada ao Blender",
    "category": "Audio",
}

import bpy
from . ui   import panels, workspace, piano_roll
from . core import register as core_register


@bpy.app.handlers.persistent
def on_load_post(scene, depsgraph=None):
    workspace.ensure_daw_workspace()


# [NOVO] Instala o template 1s após o registro (contexto já carregado)
def _install_template():
    try:
        from .template_installer import install_template
        install_template()
    except Exception as e:
        print(f"[DAW] Aviso na instalação do template: {e}")
    return None  # None = executa só uma vez


def register():
    panels.register()
    workspace.register()
    piano_roll.register()
    core_register.register()

    if on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load_post)

    # [NOVO] Instala o template automaticamente
    bpy.app.timers.register(_install_template, first_interval=1.0)

    try:
        workspace.ensure_daw_workspace()
    except Exception:
        pass


def unregister():
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)

    core_register.unregister()
    piano_roll.unregister()
    workspace.unregister()
    panels.unregister()