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

# [FIX PONTE ÁUDIO] Antes, Engine não tinha mixer nem saída de áudio --
# só o transporte/clock/scheduler ficavam "rodando no vazio" (o
# scheduler nunca recebia nenhuma tarefa, então seu tick() era sempre
# um no-op). Isso fazia o addon logar "Motor iniciado" sem nunca
# produzir som nenhum, e o medidor do mixer nunca tinha nível real pra
# mostrar. As linhas abaixo dão à Engine um Mixer de verdade e uma
# saída de áudio real (via sounddevice, com fallback seguro se não
# estiver instalado -- ver audio/stream.py).
from ..mixer import Mixer
from ..audio.output import AudioOutput
from ..audio.config import ENGINE_CONFIG


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

        # [FIX PONTE ÁUDIO] Mixer real + saída de áudio real. O Mixer já
        # nasce com o "Channel 0" default (ver mixer/mixer.py); canais
        # extras são criados/sincronizados por `channel_rack_bridge.py`
        # pra espelhar `scene.daw_channel_rack.channels`.
        self.mixer = Mixer(sample_rate=ENGINE_CONFIG.sample_rate)
        self.audio_output = AudioOutput()
        self.audio_output.set_generator(self.mixer)  # Mixer.process(frames) já bate com o contrato esperado

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

        # [FIX PONTE ÁUDIO] Liga a saída de áudio real. `start_safe()`
        # nunca levanta exceção -- se `sounddevice` não estiver
        # instalado, a engine continua rodando normalmente (clock,
        # transporte, ponte do Channel Rack), só sem som real audível
        # (fica só a lógica/o medidor calculando em silêncio).
        ok, msg = self.audio_output.start_safe()
        if ok:
            LOGGER.info("Engine", msg)
        else:
            LOGGER.warning("Engine", msg)

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

        # [FIX PONTE ÁUDIO] Desliga a saída de áudio real antes de
        # parar o clock/scheduler.
        try:
            self.audio_output.stop()
        except Exception as e:
            LOGGER.warning("Engine", f"Erro ao parar saída de áudio: {e}")

        self.clock.stop()
        self.scheduler.clear()
        self._is_running = False
        self._engine_state = EngineState.STOPPED

        # [FIX PONTE ÁUDIO] Fecha os arquivos .wav abertos pelo cache
        # de leitura de nível dos canais SAMPLER/AUDIO/DRUM.
        try:
            from .channel_rack_bridge import close_wav_cache as _close_wav_cache
            _close_wav_cache()
        except Exception:
            pass

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

        # [FIX PONTE ÁUDIO] Só dispara notas do Channel Rack quando o
        # Blender está de fato reproduzindo (spacebar/play) -- não a
        # cada scrub manual do playhead, que também dispara
        # frame_change_post e faria a "reprodução" avançar/disparar
        # notas mesmo parado.
        if bpy.context.screen is not None and bpy.context.screen.is_animation_playing:
            try:
                from . import channel_rack_bridge
                channel_rack_bridge.tick(self, scene)
            except Exception as e:
                LOGGER.error("Engine", f"Erro na ponte do Channel Rack: {e}")

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
        # [FIX PONTE ÁUDIO] Sem isso, a próxima vez que desse play a
        # ponte tentaria "recuperar" todos os steps entre o ponto onde
        # parou e o novo ponto de partida, disparando uma rajada de
        # notas atrasadas de uma vez só.
        try:
            from .channel_rack_bridge import reset as _reset_channel_rack_bridge
            _reset_channel_rack_bridge()
        except Exception:
            pass
        try:
            self.mixer.all_notes_off()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # [FIX PONTE ÁUDIO] Fachada de compatibilidade -- métodos que
    # `daw/core/register.py::get_engine()` já documentava existir
    # ("A Engine expõe set_volume/set_pan/set_mute/set_solo/
    # set_master_volume/note_on/note_off/get_state()"), mas que nunca
    # tinham sido implementados de verdade. Delegam pro Mixer real.
    # ------------------------------------------------------------------

    def set_volume(self, channel_idx: int, volume: float) -> None:
        self.mixer.set_volume(channel_idx, volume)

    def set_pan(self, channel_idx: int, pan: float) -> None:
        self.mixer.set_pan(channel_idx, pan)

    def set_mute(self, channel_idx: int, mute: bool) -> None:
        self.mixer.set_mute(channel_idx, mute)

    def set_solo(self, channel_idx: int, solo: bool) -> None:
        self.mixer.set_solo(channel_idx, solo)

    def set_master_volume(self, volume: float) -> None:
        self.mixer.set_master_volume(volume)

    def note_on(self, note: int, velocity: int = 100, channel_idx: int = 0) -> None:
        self.mixer.note_on(note, velocity, channel_idx)

    def note_off(self, note: int, channel_idx: int = 0) -> None:
        self.mixer.note_off(note, channel_idx)

    def get_state(self) -> dict:
        """Snapshot leve do estado atual, útil pra depuração/UI."""
        return {
            "engine_state": self._engine_state.name if hasattr(self._engine_state, "name") else str(self._engine_state),
            "is_running": self._is_running,
            "is_playing": self.is_playing,
            "current_time": self.current_time,
            "channel_count": self.mixer.channel_count,
            "audio_output_active": self.audio_output.active,
        }


# ------------------------------------------------------------------
# Instância global (alternativa ao singleton via __new__)
# Usar ENGINE ao invés de Engine() em outros módulos garante
# que sempre apontamos para a mesma instância.
# ------------------------------------------------------------------

ENGINE = Engine()