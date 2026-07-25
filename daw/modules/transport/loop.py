"""transport/loop.py

Implementa o loop de reprodução via `frame_change_pre` handler (mais
confiável que os pontos de preview do Blender, pois funciona igual
tanto no Timeline quanto no Sequencer/Graph Editor), além de
operadores para definir/ajustar a região de loop.
"""

import bpy
from bpy.app.handlers import persistent
from bpy.types import Operator

from .utils import get_transport, redraw_ui


@persistent
def _loop_frame_change_handler(scene, depsgraph=None):
    transport = scene.daw_transport
    if not transport.loop_enabled:
        return
    if not bpy.context.screen or not bpy.context.screen.is_animation_playing:
        return

    if scene.frame_current >= transport.loop_end:
        scene.frame_set(transport.loop_start)
    elif scene.frame_current < transport.loop_start:
        # playhead foi movido manualmente para antes do loop: realinha
        scene.frame_set(transport.loop_start)


def on_loop_toggle(context, enabled):
    """Chamado pelo update callback de `loop_enabled` em properties.py."""
    handlers = bpy.app.handlers.frame_change_pre
    if enabled:
        if _loop_frame_change_handler not in handlers:
            handlers.append(_loop_frame_change_handler)
    else:
        if _loop_frame_change_handler in handlers:
            handlers.remove(_loop_frame_change_handler)
    redraw_ui(context)


class DAW_OT_transport_set_loop_start(Operator):
    """Define o início do loop no frame atual do playhead"""
    bl_idname = "daw.transport_set_loop_start"
    bl_label = "Set Loop Start"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        transport = get_transport(context)
        frame = context.scene.frame_current
        transport.loop_start = min(frame, transport.loop_end - 1)
        redraw_ui(context)
        return {"FINISHED"}


class DAW_OT_transport_set_loop_end(Operator):
    """Define o fim do loop no frame atual do playhead"""
    bl_idname = "daw.transport_set_loop_end"
    bl_label = "Set Loop End"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        transport = get_transport(context)
        frame = context.scene.frame_current
        transport.loop_end = max(frame, transport.loop_start + 1)
        redraw_ui(context)
        return {"FINISHED"}


class DAW_OT_transport_toggle_loop(Operator):
    """Ativa/desativa o loop de reprodução"""
    bl_idname = "daw.transport_toggle_loop"
    bl_label = "Toggle Loop"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        transport = get_transport(context)
        transport.loop_enabled = not transport.loop_enabled
        # on_loop_toggle já é chamado automaticamente pelo update
        # callback da property, então não precisa chamar de novo aqui.
        return {"FINISHED"}


classes = (
    DAW_OT_transport_set_loop_start,
    DAW_OT_transport_set_loop_end,
    DAW_OT_transport_toggle_loop,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    # Garante que o handler não fique pendurado se o addon for
    # desabilitado enquanto o loop está ativo.
    handlers = bpy.app.handlers.frame_change_pre
    if _loop_frame_change_handler in handlers:
        handlers.remove(_loop_frame_change_handler)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)