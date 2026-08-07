"""
timeline/playback.py
Controle de transport da timeline (play, pause, stop, record).
Integra com a daw_engine via interface de Transport/Clock.
"""

import bpy
from .utils import get_timeline
from .cursor import set_cursor_beat, get_cursor_beat, wrap_cursor_if_looping, ensure_cursor_visible


# ---------------------------------------------------------------------------
# Estado de transport
# ---------------------------------------------------------------------------

class TransportState:
    """Singleton de estado do transport."""
    _playing    = False
    _recording  = False
    _pre_roll   = False
    _return_beat = None    # beat para retornar ao dar Stop


_state = TransportState()


# ---------------------------------------------------------------------------
# Acesso ao estado
# ---------------------------------------------------------------------------

def is_playing()   -> bool: return _state._playing
def is_recording() -> bool: return _state._recording
def is_stopped()   -> bool: return not _state._playing


# ---------------------------------------------------------------------------
# Comandos de transport
# ---------------------------------------------------------------------------

def play(context=None):
    """Inicia reprodução a partir da posição atual do cursor."""
    if _state._playing:
        return

    _state._return_beat = get_cursor_beat(context)
    _state._playing     = True
    _state._recording   = False

    _engine_play(context)
    _start_timer(context)
    _request_redraw()


def pause(context=None):
    """Pausa a reprodução (mantém posição do cursor)."""
    if not _state._playing:
        return

    _state._playing = False
    _engine_pause(context)
    _stop_timer(context)
    _request_redraw()


def stop(context=None, return_to_start: bool = True):
    """
    Para a reprodução.
    Se return_to_start=True, retorna ao beat de antes de iniciar.
    """
    was_playing = _state._playing

    _state._playing   = False
    _state._recording = False

    _engine_stop(context)
    _stop_timer(context)

    if return_to_start and _state._return_beat is not None:
        set_cursor_beat(_state._return_beat, context)
        _state._return_beat = None

    _request_redraw()


def toggle_play(context=None):
    """Alterna entre play e pause."""
    if _state._playing:
        pause(context)
    else:
        play(context)


def toggle_play_stop(context=None):
    """Play / Stop (retorna ao início ao parar)."""
    if _state._playing:
        stop(context, return_to_start=True)
    else:
        play(context)


def record(context=None):
    """Inicia reprodução em modo gravação."""
    if _state._playing and _state._recording:
        return

    _state._return_beat = get_cursor_beat(context)
    _state._playing     = True
    _state._recording   = True

    _engine_record(context)
    _start_timer(context)
    _request_redraw()


def stop_recording(context=None):
    """Para gravação sem retornar ao início."""
    stop(context, return_to_start=False)


# ---------------------------------------------------------------------------
# Callbacks de timer (atualização do cursor durante reprodução)
# ---------------------------------------------------------------------------

_TIMER_INTERVAL = 1.0 / 30.0   # 30 FPS
_timer_ref = None


def _start_timer(context=None):
    global _timer_ref
    wm = (context or bpy.context).window_manager
    try:
        _timer_ref = wm.event_timer_add(_TIMER_INTERVAL, window=(context or bpy.context).window)
    except Exception:
        pass


def _stop_timer(context=None):
    global _timer_ref
    if _timer_ref is not None:
        wm = (context or bpy.context).window_manager
        try:
            wm.event_timer_remove(_timer_ref)
        except Exception:
            pass
        _timer_ref = None


def on_timer_tick(context=None):
    """
    Chamado a cada tick do timer enquanto está reproduzindo.
    Atualiza o cursor com a posição da engine.
    """
    if not _state._playing:
        return

    engine_beat = _get_engine_beat(context)
    if engine_beat is not None:
        tl = get_timeline(context)
        tl.cursor_beat = engine_beat
        wrap_cursor_if_looping(context)
        ensure_cursor_visible(context)
        _request_redraw()


# ---------------------------------------------------------------------------
# Navegação rápida
# ---------------------------------------------------------------------------

def rewind_to_start(context=None):
    """Move o cursor para o beat 0."""
    set_cursor_beat(0.0, context)


def go_to_end(context=None):
    """Move o cursor para o fim do conteúdo."""
    tl = get_timeline(context)
    max_beat = 0.0
    for track in tl.tracks:
        for clip in track.clips:
            end = clip.start_beat + clip.length_beats
            if end > max_beat:
                max_beat = end
    set_cursor_beat(max_beat, context)


def skip_forward(beats: float = 4.0, context=None):
    """Avança o cursor em N beats."""
    beat = get_cursor_beat(context)
    set_cursor_beat(beat + beats, context)


def skip_backward(beats: float = 4.0, context=None):
    """Recua o cursor em N beats."""
    beat = get_cursor_beat(context)
    set_cursor_beat(max(0.0, beat - beats), context)


# ---------------------------------------------------------------------------
# Integração com a engine de áudio
# ---------------------------------------------------------------------------
#
# BUG CORRIGIDO: este módulo importava `daw.daw_engine.transport.Transport`
# e chamava `Transport.instance()` / `.get_position_beats()` — nenhum dos
# dois existe (o módulo certo é `daw.daw_engine.core.transport`, sem
# `instance()` nem `get_position_beats()`). O singleton de verdade é
# `daw.daw_engine.core.engine.Engine`, que guarda `self.transport` e
# `self.clock`. Como as chamadas abaixo estavam em "except Exception: pass",
# o erro nunca aparecia — play/pause/stop/record simplesmente não faziam
# nada, silenciosamente. Esta é a causa mais provável de o piano roll (e a
# reprodução em geral) não tocar/atualizar depois de editar notas: o play
# nunca chegava a iniciar a engine de verdade.


def _get_engine():
    from daw.daw_engine.core.engine import Engine
    return Engine()


def _engine_play(context=None):
    try:
        _get_engine().play()
    except Exception as exc:
        print(f"[DAW] Falha ao iniciar a engine de áudio: {exc}")


def _engine_pause(context=None):
    try:
        _get_engine().pause()
    except Exception as exc:
        print(f"[DAW] Falha ao pausar a engine de áudio: {exc}")


def _engine_stop(context=None):
    try:
        _get_engine().stop()
    except Exception as exc:
        print(f"[DAW] Falha ao parar a engine de áudio: {exc}")


def _engine_record(context=None):
    try:
        _get_engine().record()
    except Exception as exc:
        print(f"[DAW] Falha ao iniciar gravação na engine de áudio: {exc}")


def _get_engine_beat(context=None) -> float | None:
    """Retorna o beat atual da engine de áudio, ou None se não disponível."""
    try:
        return _get_engine().clock.get_current_beat()
    except Exception as exc:
        print(f"[DAW] Falha ao ler posição da engine de áudio: {exc}")
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _request_redraw():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except Exception:
        pass