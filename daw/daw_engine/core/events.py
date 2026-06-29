# core/events.py
"""
Sistema de eventos pub/sub da DAW.

Correção vs versão anterior:
- Sem thread-safety: listeners podiam ser modificados durante emit()
  causando RuntimeError. Agora emit() itera sobre uma cópia.
- Adicionado subscribe_once() para listeners de uso único.
- Adicionado clear() para limpar todos os listeners (útil no shutdown).
- Adicionado unsubscribe_all(event_type) para limpar um evento específico.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List


# ------------------------------------------------------------------
# Constantes de eventos padrão
# ------------------------------------------------------------------

EVENT_PLAY       = "play"
EVENT_STOP       = "stop"
EVENT_RECORD     = "record"
EVENT_PAUSE      = "pause"
EVENT_LOOP       = "loop"
EVENT_BPM_CHANGE = "bpm_change"
EVENT_TIME_CHANGE = "time_change"
EVENT_FRAME_UPDATE = "frame_update"
EVENT_PROJECT_NEW  = "project_new"
EVENT_PROJECT_OPEN = "project_open"
EVENT_PROJECT_SAVE = "project_save"
EVENT_TRACK_ADD    = "track_add"
EVENT_TRACK_REMOVE = "track_remove"
EVENT_CLIP_ADD     = "clip_add"
EVENT_CLIP_REMOVE  = "clip_remove"


class EventSystem:
    """
    Publicador/assinante de eventos desacoplado.

    Uso:
        events = EventSystem()
        events.subscribe("play", lambda data: print("tocando!"))
        events.emit("play")
    """

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable]] = {}
        self._once: Dict[str, List[Callable]] = {}

    # ------------------------------------------------------------------
    # Assinatura
    # ------------------------------------------------------------------

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Registra um listener permanente para o evento."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        if callback not in self._listeners[event_type]:
            self._listeners[event_type].append(callback)

    def subscribe_once(self, event_type: str, callback: Callable) -> None:
        """Registra um listener que dispara apenas uma vez."""
        if event_type not in self._once:
            self._once[event_type] = []
        if callback not in self._once[event_type]:
            self._once[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Remove um listener permanente."""
        listeners = self._listeners.get(event_type, [])
        if callback in listeners:
            listeners.remove(callback)

    def unsubscribe_all(self, event_type: str) -> None:
        """Remove todos os listeners de um evento específico."""
        self._listeners.pop(event_type, None)
        self._once.pop(event_type, None)

    def clear(self) -> None:
        """Remove todos os listeners de todos os eventos."""
        self._listeners.clear()
        self._once.clear()

    # ------------------------------------------------------------------
    # Emissão
    # ------------------------------------------------------------------

    def emit(self, event_type: str, data: Any = None) -> None:
        """
        Dispara um evento para todos os listeners registrados.
        Itera sobre cópia da lista para ser seguro durante modificações.
        Erros nos listeners são silenciados para não quebrar a engine.
        """
        # Listeners permanentes
        for cb in list(self._listeners.get(event_type, [])):
            try:
                cb(data)
            except Exception as e:
                # Não queremos que um listener bugado trave a engine
                print(f"[EventSystem] Erro no listener de '{event_type}': {e}")

        # Listeners de uso único — dispara e remove
        once_list = self._once.pop(event_type, [])
        for cb in once_list:
            try:
                cb(data)
            except Exception as e:
                print(f"[EventSystem] Erro no once-listener de '{event_type}': {e}")

    # ------------------------------------------------------------------
    # Inspeção
    # ------------------------------------------------------------------

    def listener_count(self, event_type: str) -> int:
        """Retorna o número de listeners para um evento."""
        return (
            len(self._listeners.get(event_type, []))
            + len(self._once.get(event_type, []))
        )

    def registered_events(self) -> list[str]:
        """Lista todos os eventos que têm listeners registrados."""
        return list(set(list(self._listeners.keys()) + list(self._once.keys())))

    def __repr__(self) -> str:
        return f"EventSystem(events={self.registered_events()})"