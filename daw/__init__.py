bl_info = {
    "name": "Blender DAW",
    "author": "Italo Nicacio Dev ",
    "version": (0, 18, 2, 'beta'),
    "blender": (4, 5, 0),
    "location": "DAW Workspace",
    "description": "DAW completa integrada ao Blender",
    "category": "Audio",
}

import bpy
import importlib
import traceback

# ─────────────────────────────────────────────────────────────────
#  UI "legada" (workspace, painéis simples, editores modais)
# ─────────────────────────────────────────────────────────────────
from .ui import panels, workspace, beat_grid
from .ui import piano_roll as legacy_piano_roll

# ─────────────────────────────────────────────────────────────────
#  Motor de áudio / propriedades centrais da cena (scene.daw)
# ─────────────────────────────────────────────────────────────────
from .core import register as core_register

# ─────────────────────────────────────────────────────────────────
#  Módulos funcionais da DAW (daw/modules/*)
#
#  Cada módulo expõe register()/unregister() no seu __init__.py.
#  A importação é feita de forma defensiva (importlib + try/except):
#  se um módulo tiver um bug de import (ex.: um arquivo referenciando
#  um nome que não existe), o restante da DAW continua funcionando
#  em vez do addon inteiro falhar ao carregar no Blender.
# ─────────────────────────────────────────────────────────────────
_MODULE_NAMES = [
    "settings",
    "update",
    "project",
    "transport",
    "timeline",
    "mixer",
    "channel_rack",
    "patterns",
    "piano_roll",
    "instruments",
    "vst",
    "sampler",
    "effects",
    "automation",
    "metronome",
    "recorder",
    "render",
    "export",
    "playlist",
    "browser",
]

_SUBMODULES = []  # preenchido em _import_submodules(): lista de (name, module | None)


def _import_submodules():
    _SUBMODULES.clear()
    for name in _MODULE_NAMES:
        try:
            module = importlib.import_module(f".modules.{name}", package=__name__)
        except Exception:
            print(f"[DAW] ⚠ Falha ao importar o módulo '{name}' — ele ficará indisponível:")
            traceback.print_exc()
            module = None
        _SUBMODULES.append((name, module))


def _register_submodules():
    for name, module in _SUBMODULES:
        if module is None:
            continue
        func = getattr(module, "register", None)
        if not callable(func):
            print(f"[DAW] Módulo '{name}' ainda não implementa register() — pulando.")
            continue
        try:
            func()
        except Exception:
            print(f"[DAW] ⚠ Falha ao registrar o módulo '{name}':")
            traceback.print_exc()


def _unregister_submodules():
    for name, module in reversed(_SUBMODULES):
        if module is None:
            continue
        func = getattr(module, "unregister", None)
        if not callable(func):
            continue
        try:
            func()
        except Exception:
            print(f"[DAW] ⚠ Falha ao desregistrar o módulo '{name}':")
            traceback.print_exc()


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
    # 1. UI legada (janela/workspace + editores modais próprios)
    panels.register()
    workspace.register()
    legacy_piano_roll.register()
    beat_grid.register()

    # 2. Motor de áudio + propriedades centrais (scene.daw)
    core_register.register()

    # 3. Módulos funcionais (transport, mixer, patterns, piano_roll, etc.)
    _import_submodules()
    _register_submodules()

    if on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load_post)

    bpy.app.timers.register(_install_template, first_interval=1.0)

    try:
        workspace.ensure_daw_workspace()
    except Exception:
        pass

    version_str = ".".join(str(v) for v in bl_info["version"])
    print(f"[DAW] Addon v{version_str} registrado")


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

    # Ordem inversa do register()
    _unregister_submodules()

    core_register.unregister()

    beat_grid.unregister()
    legacy_piano_roll.unregister()
    workspace.unregister()
    panels.unregister()