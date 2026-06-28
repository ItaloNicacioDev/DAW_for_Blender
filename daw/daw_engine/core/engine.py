# core/engine.py
"""
Motor principal da DAW. Coordena todos os subsistemas e se integra ao Blender
através de handlers de frame.
"""
from __future__ import annotations

import bpy
from typing import Optional

from .clock import Clock
from .transport import Transport
from .scheduler import Scheduler
from .events import EventSystem
from .session import Session
from .state import State
from .logger import LOGGER
from .constants import EngineState


class Engine:
    """Singleton do motor DAW."""
    _instance: Optional[Engine] = None

    def __new__(cls) -> Engine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        # Subsistemas principais
        self.clock = Clock()
        self.transport = Transport()
        self.scheduler = Scheduler()
        self.events = EventSystem()
        self.session = Session()
        self.state = State()

        # Estado interno
        self._is_running = False
        self._handler = None

        # Log
        LOGGER.info("Engine", "Motor DAW inicializado.")

    # ------------------------------------------------------------
    # Controle do motor
    # ------------------------------------------------------------

    def start(self) -> None:
        """Inicia o motor e registra o handler de atualização no Blender."""
        if self._is_running:
            return

        self.clock.start()
        self._is_running = True

        # Registra o handler para atualização a cada frame
        self._handler = bpy.app.handlers.frame_change_post.append(self._update)
        LOGGER.info("Engine", "Motor iniciado com handler de frame.")

    def stop(self) -> None:
        """Para o motor e remove o handler."""
        if not self._is_running:
            return

        self.clock.stop()
        self.transport.stop()
        self._is_running = False

        if self._handler is not None:
            bpy.app.handlers.frame_change_post.remove(self._handler)
            self._handler = None

        LOGGER.info("Engine", "Motor parado.")

    def _update(self, scene: bpy.types.Scene) -> None:
        """Callback chamado a cada frame pelo Blender."""
        if not self._is_running:
            return

        # Calcula o delta de tempo em segundos
        delta = 1.0 / scene.render.fps if scene.render.fps > 0 else 0.0

        # Atualiza transporte e scheduler
        self.transport.update(delta)
        self.scheduler.tick()

        # Notifica eventos de tempo (opcional)
        self.events.emit("frame_update", {
            "frame": scene.frame_current,
            "time": self.clock.get_current_time()
        })

    # ------------------------------------------------------------
    # Atalhos para transporte
    # ------------------------------------------------------------

    def play(self) -> None:
        self.transport.play()
        self.events.emit("play")

    def stop(self) -> None:
        self.transport.stop()
        self.events.emit("stop")

    def record(self) -> None:
        self.transport.record()
        self.events.emit("record")

    def toggle_loop(self) -> None:
        self.transport.toggle_loop()

    def set_position(self, time: float) -> None:
        self.transport.set_position(time)

    # ------------------------------------------------------------
    # Gerenciamento de projeto
    # ------------------------------------------------------------

    def new_project(self, name: str = "Untitled") -> None:
        """Cria um novo projeto e o define como atual."""
        self.session.new_project(name)
        LOGGER.info("Engine", f"Novo projeto criado: {name}")

    def open_project(self, filepath: str) -> None:
        """Abre um projeto do disco."""
        self.session.open_project(filepath)
        LOGGER.info("Engine", f"Projeto aberto: {filepath}")

    def save_project(self) -> None:
        """Salva o projeto atual."""
        self.session.save_project()
        LOGGER.info("Engine", "Projeto salvo.")

    # ------------------------------------------------------------
    # Acesso ao estado
    # ------------------------------------------------------------

    @property
    def is_playing(self) -> bool:
        return self.transport.is_playing

    @property
    def is_recording(self) -> bool:
        return self.transport.is_recording

    @property
    def current_time(self) -> float:
        return self.clock.get_current_time()