"""transport/properties.py

Define o PropertyGroup que guarda o estado do transporte (play/pause/
record, bpm, compasso e região de loop) e o registra em `Scene.daw_transport`.

Pressupõe que o resto do addon acessa o estado sempre via
`utils.get_transport(context)`.
"""

import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    BoolProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
)


def _on_bpm_update(self, context):
    from .tempo import apply_bpm
    apply_bpm(context, self.bpm)


def _on_loop_toggle(self, context):
    from .loop import on_loop_toggle
    on_loop_toggle(context, self.loop_enabled)


class DAW_TransportProperties(PropertyGroup):
    """Estado runtime do transporte da DAW."""

    is_playing: BoolProperty(
        name="Playing",
        description="Se o transporte está tocando no momento",
        default=False,
    )
    is_paused: BoolProperty(
        name="Paused",
        description="Se a reprodução está pausada (frame preservado)",
        default=False,
    )
    is_recording: BoolProperty(
        name="Recording",
        description="Se o transporte está armado/gravando",
        default=False,
    )

    bpm: FloatProperty(
        name="BPM",
        description="Tempo do projeto, em batidas por minuto",
        default=120.0,
        min=20.0,
        max=999.0,
        update=_on_bpm_update,
    )
    beats_per_bar: IntProperty(
        name="Beats/Bar",
        description="Número de batidas por compasso",
        default=4,
        min=1,
        max=32,
    )

    loop_enabled: BoolProperty(
        name="Loop",
        description="Repetir a reprodução entre os marcadores de loop",
        default=False,
        update=_on_loop_toggle,
    )
    loop_start: IntProperty(
        name="Loop Start",
        description="Frame onde a região de loop começa",
        default=1,
        min=0,
    )
    loop_end: IntProperty(
        name="Loop End",
        description="Frame onde a região de loop termina",
        default=100,
        min=1,
    )

    metronome_enabled: BoolProperty(
        name="Metronome",
        description="Tocar um clique de metrônomo durante a reprodução",
        default=False,
    )


classes = (DAW_TransportProperties,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_transport = PointerProperty(type=DAW_TransportProperties)


def unregister():
    if hasattr(bpy.types.Scene, "daw_transport"):
        del bpy.types.Scene.daw_transport
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)