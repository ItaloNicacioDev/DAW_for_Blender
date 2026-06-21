bl_info = {
    "name": "Blender DAW",
    "author": "Italo Nicacio Dev ",
    "version": (0, 16, 4, 'beta'),
    "blender": (5, 0, 0),
    "location": "DAW Workspace",
    "description": "DAW completa integrada ao Blender",
    "category": "Audio",

}

import bpy
from . ui   import panels, workspace, piano_roll, beat_grid
from . core import register as core_register


@bpy.app.handlers.persistent
def on_load_post(scene, depsgraph=None):
    try:
        workspace.ensure_daw_workspace()
    except Exception:
        pass


def _install_template():
    try:
        from .template_installer import install_template
        install_template()
    except Exception as e:
        print(f"[DAW] Template: {e}")
    return None


def register():
    panels.register()
    workspace.register()
    piano_roll.register()
    beat_grid.register()
    core_register.register()

    if on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load_post)

    bpy.app.timers.register(_install_template, first_interval=1.0)

    try:
        workspace.ensure_daw_workspace()
    except Exception:
        pass

    print("[DAW] Addon v0.3.0 registrado")


def unregister():
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)

    def _cleanup():
        try:
            from .template_installer import uninstall_template
            uninstall_template()
        except Exception:
            pass
        try:
            workspace.remove_daw_workspace()
        except Exception:
            pass
        return None

    bpy.app.timers.register(_cleanup, first_interval=0.1)

    core_register.unregister()
    beat_grid.unregister()
    piano_roll.unregister()
    workspace.unregister()
    panels.unregister()