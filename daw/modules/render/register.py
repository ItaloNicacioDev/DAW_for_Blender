# modules/render/register.py
"""
Registro centralizado do módulo Render.
"""
from __future__ import annotations

from . import properties
from . import utils
from . import audio
from . import stems
from . import video
from . import animation
from . import operators
from . import ui


def register_all():
    properties.register()
    utils.register()
    audio.register()
    stems.register()
    video.register()
    animation.register()
    operators.register()
    ui.register()


def unregister_all():
    ui.unregister()
    operators.unregister()
    animation.unregister()
    video.unregister()
    stems.unregister()
    audio.unregister()
    utils.unregister()
    properties.unregister()