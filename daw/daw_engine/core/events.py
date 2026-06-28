# core/events.py
"""Sistema de eventos para comunicação entre componentes."""
from typing import Callable, Dict, List, Any

class EventSystem:
    """Publicador/assinante de eventos."""
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        if event_type in self._listeners:
            self._listeners[event_type].remove(callback)

    def emit(self, event_type: str, data: Any = None):
        if event_type in self._listeners:
            for cb in self._listeners[event_type]:
                cb(data)

# Eventos comuns
EVENT_PLAY = "play"
EVENT_STOP = "stop"
EVENT_RECORD = "record"
EVENT_LOOP = "loop"
EVENT_BPM_CHANGE = "bpm_change"
EVENT_TIME_CHANGE = "time_change"