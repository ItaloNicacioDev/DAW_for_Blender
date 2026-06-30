# core/__init__.py
"""
Pacote principal do núcleo da DAW para Blender.

Correção vs versão anterior:
- `from .constants import *` é evitado aqui — poluí o namespace do pacote
  com toda a lista de Enums/constantes sem controle explícito, e mascara
  de onde cada símbolo veio. Trocado por import explícito dos itens
  realmente usados fora do core.
- Engine agora também exporta a instância global ENGINE (ver core/engine.py)
  — é a forma recomendada de acessar a engine de fora do pacote core,
  ao invés de chamar Engine() de novo em cada módulo.
- Logger não existia como classe exportável (logger.py expõe um singleton
  chamado LOGGER, não uma classe Logger) — corrigido o import para refletir
  a API real.
"""
from __future__ import annotations

from .clock import Clock
from .commands import Command, CommandManager
from .constants import (
    EngineState,
    TrackType,
    ClipType,
    AutomationInterpolation,
    LoopMode,
    LogLevel,
    CommandStatus,
    DEFAULT_BPM,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_PPQ,
    PROJECT_EXTENSION,
)
from .engine import Engine, ENGINE
from .events import EventSystem
from .history import History
from .logger import LOGGER
from .profiler import Profiler
from .project import Project
from .registry import Registry
from .scheduler import Scheduler
from .session import Session
from .settings import Settings
from .state import State
from .timeline import Timeline, Track, Clip
from .transport import Transport

__all__ = [
    # Engine
    "Engine", "ENGINE",
    # Tempo e transporte
    "Clock", "Transport", "Scheduler",
    # Eventos
    "EventSystem",
    # Comandos / undo-redo
    "Command", "CommandManager", "History",
    # Projeto e dados
    "Project", "Settings", "Session",
    "Timeline", "Track", "Clip",
    # Estado e infraestrutura
    "State", "Registry", "Profiler", "LOGGER",
    # Enums e constantes
    "EngineState", "TrackType", "ClipType",
    "AutomationInterpolation", "LoopMode", "LogLevel", "CommandStatus",
    "DEFAULT_BPM", "DEFAULT_SAMPLE_RATE", "DEFAULT_PPQ", "PROJECT_EXTENSION",
]