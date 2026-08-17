# modules/vst/realtime/prefetch.py
"""
PrefetchThread: mantém um RingBuffer preenchido de HORIZON_SECONDS à
frente do playhead, chamando o worker (via `live_vst.bridge`) em pedaços
curtos e sequenciais.

Depende só de `live_vst.bridge` (a interface `stream_reset` /
`stream_render_chunk` de ipc_engine.py) e do `RingBuffer` -- nenhuma
dependência de `bpy`/`aud` aqui, de propósito, pra dar pra testar a
lógica de agendamento sem Blender (ver
tests/test_prefetch_scheduling.py, que usa um bridge fake).

O que este arquivo NÃO resolve sozinho (fica pro PlaybackSupervisor,
que tem acesso a `bpy`):
    - Descobrir a posição atual do playhead.
    - Decidir quando iniciar/parar a thread (play/stop).
    - Plugar o RingBuffer numa fonte de áudio de verdade (aud).
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional, Sequence, Tuple

from .ring_buffer import RingBuffer

# Tamanho de cada pedaço renderizado por chamada ao worker. Pequeno o
# bastante pra automação em pedaços de VST._build_automation_schedule
# (50ms) ficar granular, grande o bastante pra não afogar o worker em
# overhead de IPC (cada chamada tem custo fixo de round-trip).
DEFAULT_CHUNK_SECONDS = 0.1

# Quanto tempo à frente do playhead o buffer tenta ficar preenchido.
DEFAULT_HORIZON_SECONDS = 1.5

# Intervalo de "cochilo" entre iterações quando já está tudo preenchido
# até o horizonte -- não precisa de busy-wait.
DEFAULT_IDLE_SLEEP_SECONDS = 0.05


class PrefetchThread:
    """
    Uma instância por VST-instrumento ativo durante o play. Chame
    `start()` depois de `stream_reset()` já ter sido feito no
    `live_vst.bridge` (normalmente pelo PlaybackSupervisor, que sabe o
    `origin_time` certo).
    """

    def __init__(
        self,
        live_vst,
        ring_buffer: RingBuffer,
        get_playhead_seconds: Callable[[], float],
        automation_schedule_fn: Optional[Callable[[float], dict]] = None,
        chunk_seconds: float = DEFAULT_CHUNK_SECONDS,
        horizon_seconds: float = DEFAULT_HORIZON_SECONDS,
        idle_sleep_seconds: float = DEFAULT_IDLE_SLEEP_SECONDS,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        """
        live_vst: objeto VST (modules/vst/vst.py) já carregado, com
            `.bridge` pronto e `stream_reset()` já chamado.
        ring_buffer: RingBuffer que este thread mantém preenchido.
        get_playhead_seconds: callback que devolve a posição atual do
            playhead em segundos absolutos -- chamado a cada iteração,
            pensado pra ser algo leve tipo
            `lambda: scene.frame_current / fps`.
        automation_schedule_fn: opcional, `(t) -> {param_id_str: valor}`
            -- se fornecido, é chamado antes de cada pedaço e o
            resultado é enviado como `automation_point` pro worker.
            Normalmente vem de `VST._build_automation_schedule` fatiado,
            ou de uma versão "ao vivo" que lê os pontos de automação
            correntes sem precisar pré-computar a curva inteira.
        on_error: chamado (na própria thread) se uma chamada ao worker
            falhar -- pelo supervisor, pra decidir se pausa/reseta.
            Nunca deixa a exceção matar a thread silenciosamente.
        """
        self.live_vst = live_vst
        self.ring_buffer = ring_buffer
        self.get_playhead_seconds = get_playhead_seconds
        self.automation_schedule_fn = automation_schedule_fn
        self.chunk_seconds = chunk_seconds
        self.horizon_seconds = horizon_seconds
        self.idle_sleep_seconds = idle_sleep_seconds
        self.on_error = on_error

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="vst-prefetch")
        self._thread.start()

    def stop(self, join_timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=join_timeout)
        self._thread = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                did_work = self._step()
            except Exception as e:
                if self.on_error is not None:
                    try:
                        self.on_error(e)
                    except Exception:
                        pass
                # Não derruba a thread por um erro pontual (ex.: worker
                # momentaneamente ocupado) -- espera um pouco e tenta de
                # novo. Erros persistentes cabem ao supervisor detectar
                # (ex.: contando falhas consecutivas) e decidir desligar
                # o playback ao vivo, voltando pro fallback de bounce.
                did_work = False
                time.sleep(self.idle_sleep_seconds)

            if not did_work:
                time.sleep(self.idle_sleep_seconds)

    def _step(self) -> bool:
        """
        Uma iteração: se o buffer não está preenchido até
        `playhead + horizon`, renderiza mais um pedaço. Devolve True se
        renderizou algo (pra não dormir à toa na próxima iteração).
        """
        playhead = self.get_playhead_seconds()
        target = playhead + self.horizon_seconds
        filled_until = self.ring_buffer.filled_until

        if filled_until >= target:
            return False

        automation_point = None
        if self.automation_schedule_fn is not None:
            automation_point = self.automation_schedule_fn(filled_until)

        audio, _elapsed = self.live_vst.bridge.stream_render_chunk(
            self.chunk_seconds, automation_point=automation_point
        )
        self.ring_buffer.write(audio, start_time=filled_until)
        return True