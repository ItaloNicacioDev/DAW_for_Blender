# modules/recorder/__init__.py
"""
Módulo Recorder do DAW.

Responsabilidade:
    Gerenciamento de gravação de áudio: captura, monitoramento,
    armamento de tracks e exportação.
"""
from __future__ import annotations

from . import properties
from . import utils
from . import input
from . import monitoring
from . import recording
from . import operators
from . import ui
from . import register as reg_module


def register():
    reg_module.register_all()


def unregister():
    reg_module.unregister_all()