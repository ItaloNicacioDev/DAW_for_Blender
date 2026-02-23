bl_info = {
    "name": "Blender DAW",
    "author": "DAW Project",
    "version": (0, 2, 0),
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


def register():
    panels.register()
    workspace.register()
    piano_roll.register()
    core_register.register()

    if on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load_post)

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