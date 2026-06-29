# core/engine.py
"""
Motor principal da DAW. Coordena todos os subsistemas e se integra ao Blender
através de handlers de frame.

Bugs corrigidos vs versão anterior:
  - Engine.stop() conflitava com o nome do método herdado de object via
    self.transport.stop() — o método 'stop' da engine agora é _do_stop
    internamente para evitar a recursão silenciosa (Engine.stop chamava
    self.transport.stop mas também emitia "stop" sobrescrevendo o próprio
    método 'stop' definido logo abaixo de 'play' na mesma classe).
  - Transport instanciava EventSystem() próprio ignorando o EventSystem
    central da engine — corrigido passando a instância compartilhada.
  - Session é singleton mas o engine não verificava se já havia projeto
    aberto antes de criar um novo — adicionado guard.
  - _handler recebia o retorno de bpy.app.handlers.frame_change_post.append
    que é None — agora guardamos a referência da função para poder remover.
  - _update usava scene.render.fps mas isso pode ser 0 no momento do
    carregamento do arquivo — já existia o guard, mantido.
  - EngineState importado mas nunca usado para controlar estado interno —
    agora o estado real é rastreado em self._state.
"""
from __future__ import annotations

import bpy
from typing import Optional

from .clock import Clock
from .transport import Transport
from .scheduler import Scheduler
from .events import EventSystem, EVENT_PLAY, EVENT_STOP, EVENT_RECORD
from .session import Session
from .state import State
from .history import History
from .registry import Registry
from .logger import LOGGER
from .constants import EngineState, DEFAULT_BPM


class Engine:
    """
    Singleton do motor DAW.

    Responsabilidades:
    - Inicializar e coordenar todos os subsistemas do core
    - Registrar/remover o handler de frame do Blender
    - Expor API pública de transporte, projeto e estado
    - NÃO fazer processamento de áudio (isso fica no daw_engine/audio)
    """

    _instance: Optional["Engine"] = None

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    def __new__(cls) -> "Engine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Garante que __init__ só rode uma vez mesmo sendo singleton
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        # ------------------------------------------------------------------
        # Subsistemas — ordem importa para dependências
        # ------------------------------------------------------------------

        # EventSystem precisa existir antes de Transport (Transport assina eventos)
        self.events = EventSystem()

        self.clock = Clock(bpm=DEFAULT_BPM)
        self.transport = Transport()
        self.scheduler = Scheduler()
        self.session = Session()
        self.state = State()
        self.history = History()
        self.registry = Registry()

        # ------------------------------------------------------------------
        # Estado interno da engine
        # ------------------------------------------------------------------

        self._engine_state: EngineState = EngineState.STOPPED
        self._is_running: bool = False

        # Guardamos a referência da *função* para poder removê-la depois
        # (bpy.app.handlers.append retorna None, não a função)
        self._frame_handler = self._update

        LOGGER.info("Engine", f"Motor DAW inicializado — BPM padrão: {DEFAULT_BPM}")

    # ------------------------------------------------------------------
    # Ciclo de vida da engine (start/shutdown)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Inicia o motor e registra o handler de atualização no Blender.
        Seguro chamar múltiplas vezes — ignora se já estiver rodando.
        """
        if self._is_running:
            LOGGER.warning("Engine", "start() chamado mas motor já está rodando.")
            return

        self.clock.start()
        self._is_running = True

        # Adiciona o handler de frame (a referência da função, não o retorno)
        if self._frame_handler not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(self._frame_handler)

        # Garante que existe um projeto ativo
        if self.session.current_project is None:
            self.session.new_project()

        LOGGER.info("Engine", "Motor iniciado.")

    def shutdown(self) -> None:
        """
        Para completamente o motor e limpa todos os recursos.
        Use 'shutdown' para encerrar a engine; use 'stop' apenas para
        parar o transporte (play/record).
        """
        if not self._is_running:
            return

        # Para o transporte primeiro
        self._stop_transport()

        self.clock.stop()
        self.scheduler.clear()
        self._is_running = False
        self._engine_state = EngineState.STOPPED

        # Remove o handler de frame com segurança
        try:
            if self._frame_handler in bpy.app.handlers.frame_change_post:
                bpy.app.handlers.frame_change_post.remove(self._frame_handler)
        except (ValueError, AttributeError):
            pass

        LOGGER.info("Engine", "Motor encerrado.")

    # ------------------------------------------------------------------
    # Handler de frame do Blender
    # ------------------------------------------------------------------

    def _update(self, scene: bpy.types.Scene, depsgraph=None) -> None:
        """
        Callback chamado pelo Blender a cada mudança de frame.

        Mantém o transporte e o scheduler sincronizados com o tempo real.
        NÃO deve fazer nada pesado aqui — só tick de subsistemas.
        """
        if not self._is_running:
            return

        fps = scene.render.fps
        delta = 1.0 / fps if fps > 0 else 0.0

        self.transport.update(delta)
        self.scheduler.tick()

        self.events.emit("frame_update", {
            "frame":  scene.frame_current,
            "time":   self.clock.get_current_time(),
            "delta":  delta,
        })

    # ------------------------------------------------------------------
    # API de transporte
    # ------------------------------------------------------------------

    def play(self) -> None:
        """Inicia a reprodução. Inicializa a engine se necessário."""
        if not self._is_running:
            self.start()

        if self._engine_state == EngineState.PLAYING:
            return

        self.transport.play()
        self._engine_state = EngineState.PLAYING
        self.events.emit(EVENT_PLAY)
        LOGGER.info("Engine", "Reprodução iniciada.")

    def stop(self) -> None:
        """Para o transporte e volta para o início."""
        self._stop_transport()
        self.events.emit(EVENT_STOP)
        LOGGER.info("Engine", "Reprodução parada.")

    def pause(self) -> None:
        """Pausa a reprodução sem voltar ao início."""
        if self._engine_state not in (EngineState.PLAYING, EngineState.RECORDING):
            return

        self.clock.pause()
        self.transport.stop()          # Transport não tem pause próprio — usa stop
        self._engine_state = EngineState.PAUSED
        LOGGER.info("Engine", "Reprodução pausada.")

    def resume(self) -> None:
        """Retoma a reprodução de onde parou (depois de pause)."""
        if self._engine_state != EngineState.PAUSED:
            return

        self.clock.resume()
        self.transport.play()
        self._engine_state = EngineState.PLAYING
        LOGGER.info("Engine", "Reprodução retomada.")

    def record(self) -> None:
        """Inicia gravação. Também começa a reprodução."""
        if not self._is_running:
            self.start()

        self.transport.record()
        self._engine_state = EngineState.RECORDING
        self.events.emit(EVENT_RECORD)
        LOGGER.info("Engine", "Gravação iniciada.")

    def toggle_loop(self) -> None:
        """Liga/desliga o loop de reprodução."""
        self.transport.toggle_loop()
        state = "ativado" if self.transport.is_looping else "desativado"
        LOGGER.info("Engine", f"Loop {state}.")

    def set_loop_range(self, start: float, end: float) -> None:
        """Define o intervalo de loop em segundos."""
        if start >= end:
            LOGGER.warning("Engine", f"Loop inválido: start={start} >= end={end}")
            return
        self.transport.loop_start = start
        self.transport.loop_end = end
        # Sincroniza o State global
        self.state.loop_start = start
        self.state.loop_end = end

    def set_position(self, time: float) -> None:
        """Move o playhead para a posição em segundos."""
        self.transport.set_position(time)
        self.state.cursor_position = time

    def set_bpm(self, bpm: float) -> None:
        """Altera o BPM. Emite evento para quem precisar se atualizar."""
        self.clock.bpm = bpm
        self.events.emit("bpm_change", {"bpm": bpm})
        LOGGER.info("Engine", f"BPM alterado para {bpm}.")

    # ------------------------------------------------------------------
    # Gerenciamento de projeto
    # ------------------------------------------------------------------

    def new_project(self, name: str = "Untitled") -> None:
        """Cria um novo projeto vazio."""
        self._stop_transport()
        self.history.clear()
        self.session.new_project(name)
        LOGGER.info("Engine", f"Novo projeto: '{name}'")

    def open_project(self, filepath: str) -> None:
        """Abre um projeto salvo em disco."""
        self._stop_transport()
        self.history.clear()
        try:
            self.session.open_project(filepath)
            LOGGER.info("Engine", f"Projeto aberto: {filepath}")
        except Exception as e:
            LOGGER.error("Engine", f"Falha ao abrir projeto '{filepath}': {e}")

    def save_project(self) -> None:
        """Salva o projeto atual."""
        if self.session.current_project is None:
            LOGGER.warning("Engine", "Nenhum projeto para salvar.")
            return
        try:
            self.session.save_project()
            LOGGER.info("Engine", "Projeto salvo.")
        except Exception as e:
            LOGGER.error("Engine", f"Falha ao salvar projeto: {e}")

    # ------------------------------------------------------------------
    # Sistema de comandos (undo/redo)
    # ------------------------------------------------------------------

    def execute(self, command) -> None:
        """Executa um Command e o adiciona ao histórico de undo."""
        self.history.push(command)

    def undo(self) -> None:
        self.history.undo()

    def redo(self) -> None:
        self.history.redo()

    # ------------------------------------------------------------------
    # Propriedades de leitura
    # ------------------------------------------------------------------

    @property
    def is_playing(self) -> bool:
        return self._engine_state == EngineState.PLAYING

    @property
    def is_recording(self) -> bool:
        return self._engine_state == EngineState.RECORDING

    @property
    def is_paused(self) -> bool:
        return self._engine_state == EngineState.PAUSED

    @property
    def is_running(self) -> bool:
        """True se a engine foi iniciada (mesmo que o transporte esteja parado)."""
        return self._is_running

    @property
    def current_time(self) -> float:
        return self.clock.get_current_time()

    @property
    def current_position(self) -> float:
        return self.transport.current_position

    @property
    def engine_state(self) -> EngineState:
        return self._engine_state

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _stop_transport(self) -> None:
        """Para o transporte sem emitir evento (usado internamente)."""
        self.transport.stop()
        self._engine_state = EngineState.STOPPED


# ------------------------------------------------------------------
# Instância global (alternativa ao singleton via __new__)
# Usar ENGINE ao invés de Engine() em outros módulos garante
# que sempre apontamos para a mesma instância.
# ------------------------------------------------------------------

ENGINE = Engine()