"""transport/operators.py

Agrega os operadores centrais de transporte (play, pause, stop,
record) em uma única tupla `classes`, para simplificar o registro em
`register.py`. Operadores mais específicos (loop, bpm, tempo) mantêm
seus próprios módulos e são registrados separadamente.
"""

import bpy

from .play import DAW_OT_transport_play
from .pause import DAW_OT_transport_pause
from .stop import DAW_OT_transport_stop
from .record import DAW_OT_transport_record

classes = (
    DAW_OT_transport_play,
    DAW_OT_transport_pause,
    DAW_OT_transport_stop,
    DAW_OT_transport_record,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)