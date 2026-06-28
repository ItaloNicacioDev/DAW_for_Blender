# core/scheduler.py
"""Agendador de eventos baseado no tempo."""
import heapq
import time
from typing import Callable

class Scheduler:
    """Agenda tarefas para execução em momentos específicos."""
    def __init__(self):
        self._queue = []  # heap (tempo, id, callback, args)
        self._counter = 0

    def schedule(self, delay: float, callback: Callable, *args):
        """Agenda uma callback após 'delay' segundos (tempo absoluto)."""
        exec_time = time.time() + delay
        self._counter += 1
        heapq.heappush(self._queue, (exec_time, self._counter, callback, args))
        return self._counter

    def cancel(self, task_id):
        # Remoção não trivial; para simplificar, marcar como cancelado?
        pass

    def tick(self):
        """Executa tarefas cujo tempo chegou."""
        now = time.time()
        while self._queue and self._queue[0][0] <= now:
            _, _, callback, args = heapq.heappop(self._queue)
            callback(*args)

    def clear(self):
        self._queue.clear()