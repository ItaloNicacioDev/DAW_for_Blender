# modules/mixer/register.py
"""
Registro e desregistro do módulo Mixer no Blender.
Chamado por daw/__init__.py (ou pelo módulo pai) no register()/unregister().

Além de registrar as classes RNA (properties/operators/ui), garante que
todo `context.scene.daw_mixer` tenha o bus Master criado (buses[0]),
já que `MixerProperties.master` e o próprio meters.py dependem dele
sempre existir.
"""
from __future__ import annotations

import bpy

from .properties import _ALL_CLASSES as property_classes, MixerProperties
from .operators import classes as operator_classes
from .ui import classes as ui_classes
from .tracks import MASTER_TRACK_NAME
from . import meters


_all_classes = [
    *property_classes,
    *operator_classes,
    *ui_classes,
]


def _ensure_master_bus(mixer_props) -> None:
    """Garante que o bus Master (índice 0) exista para uma cena."""
    if len(mixer_props.buses) > 0 and mixer_props.buses[0].is_master:
        return

    # Promove um bus Master existente (fora do índice 0) para o topo, se houver.
    for i, bus in enumerate(mixer_props.buses):
        if bus.is_master and i != 0:
            mixer_props.buses.move(i, 0)
            return

    master = mixer_props.buses.add()
    master.name = MASTER_TRACK_NAME
    master.volume = 0.8
    master.is_master = True
    if len(mixer_props.buses) > 1:
        mixer_props.buses.move(len(mixer_props.buses) - 1, 0)


def _ensure_defaults_all_scenes() -> None:
    for scene in bpy.data.scenes:
        mixer_props = getattr(scene, "daw_mixer", None)
        if mixer_props is not None:
            _ensure_master_bus(mixer_props)


def _delayed_ensure_defaults() -> None:
    """Executado logo após o registro (context ainda pode não estar pronto)."""
    _ensure_defaults_all_scenes()
    return None


@bpy.app.handlers.persistent
def _on_load_post(dummy1, dummy2=None):
    """Garante o bus Master também para arquivos .blend recém-carregados."""
    _ensure_defaults_all_scenes()


def register():
    for cls in _all_classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)

    bpy.types.Scene.daw_mixer = bpy.props.PointerProperty(type=MixerProperties)

    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)

    bpy.app.timers.register(_delayed_ensure_defaults, first_interval=0.1)

    meters.register()

    print("[DAW] Módulo mixer registrado")


def unregister():
    meters.unregister()

    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)

    if hasattr(bpy.types.Scene, "daw_mixer"):
        del bpy.types.Scene.daw_mixer

    for cls in reversed(_all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    print("[DAW] Módulo mixer desregistrado")