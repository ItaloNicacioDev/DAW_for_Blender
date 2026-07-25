# modules/recorder/register.py
"""
Registro centralizado do módulo Recorder.
"""
from __future__ import annotations

from . import properties
from . import operators
from . import ui
from . import recording
from . import monitoring


def register_all():
    properties.register()
    operators.register()
    ui.register()
    recording.register()
    monitoring.register()


def unregister_all():
    monitoring.unregister()
    recording.unregister()
    ui.unregister()
    operators.unregister()
    properties.unregister()