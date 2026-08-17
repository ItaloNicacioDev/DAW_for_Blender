# modules/vst/realtime/supervisor.py
"""
!! NÃO TESTADO NESTE AMBIENTE -- precisa de Blender de verdade !!

PlaybackSupervisor: orquestra RingBuffer + PrefetchThread + (via
aud_source.py) a sincronização com o VSE, ligado num
`bpy.app.timers`. É o único ponto de entrada que o resto do addon
(operators.py, ui.py) precisa chamar.

Uso pretendido (a integrar em operators.py -- NÃO incluído neste
arquivo, ver observações no final):

    supervisor = get_or_create_supervisor(context.scene)
    supervisor.on_playback_started()   # chamado do handler de play
    supervisor.on_playback_stopped()   # chamado do handler de stop/pause
    supervisor.on_parameter_changed(vst_id, t_now)  # ao mexer num knob

Comportamento de fallback: se qualquer coisa falhar na inicialização
(worker indisponível, dawdreamer sem streaming, `aud` não expor o que
`aud_source.py` precisa), `start_for_vst()` devolve False e o chamador
deve continuar usando o bounce manual/automático já existente em
`operators.py::_schedule_auto_bounce` -- este módulo nunca deve ser a
única forma de ouvir um VST.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

from .ring_buffer import RingBuffer
from .prefetch import PrefetchThread
from .aud_source import RingBufferSoundSync

_log = logging.getLogger("daw.vst.realtime")

# Canal do VSE reservado para strips de playback ao vivo. Escolhido alto
# o bastante pra não colidir com canais que o resto do addon já usa por
# convenção (canais baixos = strips normais de áudio/vídeo do usuário).
LIVE_CHANNEL_BASE = 900

TICK_INTERVAL_SECONDS = 0.1


class VstRealtimeSession:
    """Estado de playback ao vivo de UM VST-instrumento."""

    def __init__(self, live_vst, scene, channel: int, sample_rate: int = 44100):
        self.live_vst = live_vst
        self.scene = scene
        self.ring_buffer = RingBuffer(sample_rate=sample_rate, capacity_seconds=4.0)
        self.sync = RingBufferSoundSync(scene, live_vst.vst_id, self.ring_buffer, channel, sample_rate)
        self.prefetch: Optional[PrefetchThread] = None
        self._consecutive_errors = 0
        self._MAX_CONSECUTIVE_ERRORS = 5

    def _on_prefetch_error(self, exc: Exception) -> None:
        self._consecutive_errors += 1
        _log.warning("[realtime:%s] erro no prefetch (%d consecutivos): %s",
                      self.live_vst.vst_id, self._consecutive_errors, exc)

    @property
    def has_too_many_errors(self) -> bool:
        return self._consecutive_errors >= self._MAX_CONSECUTIVE_ERRORS

    def start(self, notes, origin_time: float, get_playhead_seconds) -> bool:
        try:
            ok = self.live_vst.bridge.stream_reset(notes, origin_time)
        except Exception as e:
            _log.warning("[realtime:%s] stream_reset falhou, caindo pro fallback de bounce: %s",
                          self.live_vst.vst_id, e)
            return False
        if not ok:
            return False

        self.ring_buffer.reset(at_time=origin_time)

        automation_fn = None
        if self.live_vst.has_automation():
            automation_fn = lambda t: {
                str(pid): self.live_vst.get_automation_value(pid, t)
                for pid, points in self.live_vst.automation.items()
                if points
            }

        self.prefetch = PrefetchThread(
            self.live_vst,
            self.ring_buffer,
            get_playhead_seconds=get_playhead_seconds,
            automation_schedule_fn=automation_fn,
            on_error=self._on_prefetch_error,
        )
        self.prefetch.start()
        return True

    def tick(self, playhead_seconds: float) -> None:
        if self.prefetch is not None:
            self.sync.tick(playhead_seconds)

    def stop(self) -> None:
        if self.prefetch is not None:
            self.prefetch.stop()
            self.prefetch = None
        self.sync.cleanup()


class PlaybackSupervisor:
    """
    Uma instância por Scene (guardada num dict global fraco, ver
    `get_or_create_supervisor`). Mantém uma `VstRealtimeSession` por
    VST-instrumento ativo durante o play.
    """

    def __init__(self, scene):
        self.scene = scene
        self.sessions: Dict[str, VstRealtimeSession] = {}
        self._timer_registered = False
        self._next_channel = LIVE_CHANNEL_BASE

    # ------------------------------------------------------------------
    def _get_playhead_seconds(self) -> float:
        scene = self.scene
        fps = scene.render.fps / max(scene.render.fps_base, 0.0001)
        return (scene.frame_current - scene.frame_start) / fps

    def _allocate_channel(self) -> int:
        ch = self._next_channel
        self._next_channel += 1
        return ch

    # ------------------------------------------------------------------
    def start_for_vst(self, live_vst, notes) -> bool:
        """
        Tenta iniciar playback ao vivo para este VST. Devolve False (sem
        levantar exceção) se não for possível -- o chamador deve então
        continuar usando o bounce manual/automático já existente.
        """
        if live_vst.vst_id in self.sessions:
            return True  # já está rodando

        if live_vst.bridge is None or not live_vst.loaded:
            return False

        session = VstRealtimeSession(live_vst, self.scene, self._allocate_channel())
        origin_time = self._get_playhead_seconds()
        ok = session.start(notes, origin_time, self._get_playhead_seconds)
        if not ok:
            return False

        self.sessions[live_vst.vst_id] = session
        self._ensure_timer()
        return True

    def stop_for_vst(self, vst_id: str) -> None:
        session = self.sessions.pop(vst_id, None)
        if session is not None:
            session.stop()

    def stop_all(self) -> None:
        for vst_id in list(self.sessions.keys()):
            self.stop_for_vst(vst_id)
        self._timer_registered = False  # o próprio _tick() se desregistra ao devolver None

    def notify_parameter_changed(self, vst_id: str) -> None:
        """Chame quando um parâmetro de `vst_id` mudar durante o play --
        invalida o buffer a partir do playhead atual, forçando
        re-render do trecho futuro com o novo valor."""
        session = self.sessions.get(vst_id)
        if session is not None:
            session.ring_buffer.invalidate_from(self._get_playhead_seconds())

    # ------------------------------------------------------------------
    def _ensure_timer(self) -> None:
        if self._timer_registered:
            return
        import bpy
        bpy.app.timers.register(self._tick, first_interval=TICK_INTERVAL_SECONDS)
        self._timer_registered = True

    def _tick(self) -> Optional[float]:
        if not self.sessions:
            self._timer_registered = False
            return None  # desregistra o timer -- nada rodando

        playhead = self._get_playhead_seconds()
        dead_sessions = []
        for vst_id, session in self.sessions.items():
            if session.prefetch is not None and session.prefetch.is_running is False:
                # thread morreu sem stop() explícito -- não deveria
                # acontecer (a thread sempre re-tenta em erro), mas por
                # segurança removemos a sessão em vez de deixar o tick
                # tentar usar algo morto.
                dead_sessions.append(vst_id)
                continue
            if hasattr(session, "has_too_many_errors") and session.has_too_many_errors:
                _log.warning("[realtime:%s] erros consecutivos demais, desligando playback ao vivo "
                             "e voltando pro bounce manual", vst_id)
                dead_sessions.append(vst_id)
                continue
            session.tick(playhead)

        for vst_id in dead_sessions:
            self.stop_for_vst(vst_id)

        return TICK_INTERVAL_SECONDS  # reagenda o próximo tick


# ------------------------------------------------------------------
# Registro global (uma instância por Scene). Usa id(scene) como chave
# em vez de guardar a referência da Scene diretamente em algum
# PropertyGroup, pra não arriscar interferir na serialização de
# .blend -- isso é estado de sessão de playback, não estado do projeto.
# ------------------------------------------------------------------
_supervisors: Dict[int, PlaybackSupervisor] = {}


def get_or_create_supervisor(scene) -> PlaybackSupervisor:
    key = id(scene)
    sup = _supervisors.get(key)
    if sup is None:
        sup = PlaybackSupervisor(scene)
        _supervisors[key] = sup
    return sup


# ═══════════════════════════════════════════════════════════════
# OBSERVAÇÕES PARA INTEGRAÇÃO EM operators.py / ui.py
# (deliberadamente NÃO incluído neste arquivo -- ver por quê abaixo)
# ═══════════════════════════════════════════════════════════════
#
# 1. Detectar play/stop: Blender não tem um "on play started" direto
#    pra addons. As opções mais comuns são:
#      a) bpy.app.handlers.frame_change_pre/post + checar
#         `context.screen.is_animation_playing` numa property callback;
#      b) um modal operator leve iniciado por um handler de
#         `bpy.types.SpaceSequenceEditor`.
#    Qual delas é confiável varia por versão do Blender -- isso PRECISA
#    ser confirmado no ambiente de destino antes de eu decidir qual
#    caminho colar em operators.py, pra não implementar às cegas algo
#    que só funciona em uma versão específica.
#
# 2. `notify_parameter_changed` precisa ser chamado do MESMO lugar que
#    hoje chama `_schedule_auto_bounce` em operators.py (provavelmente
#    o `update=` de `DawVstParameterProperty.param_value`) -- ideia é:
#    se existir uma sessão ao vivo pra esse VST, invalida o buffer em
#    vez de (ou além de) agendar o bounce pra arquivo.
#
# Não colei essas mudanças em operators.py agora porque exigem eu ver
# exatamente onde esse `update=` está registrado e testar contra uma
# instância real do Blender -- prefiro te devolver isso funcionando de
# verdade depois que você validar o protótipo de aud_source.py, a
# chutar uma integração que quebra silenciosamente.