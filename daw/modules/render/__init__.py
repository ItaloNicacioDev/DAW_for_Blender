# modules/render/__init__.py
"""
Módulo Render do DAW.

Responsabilidade:
    Renderização e exportação: mixdown master de áudio, stems por canal,
    renderização de vídeo (animação) e combinação (mux) de áudio e vídeo
    no arquivo final via ffmpeg.
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
from . import register as reg_module


def register():
    reg_module.register_all()


def unregister():
    reg_module.unregister_all()