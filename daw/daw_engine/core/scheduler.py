# core/scheduler.py
"""
Agendador de eventos baseado no tempo. Suporta cancelamento por ID.
"""
from __future__ import annotations

import heapq
import time
from typing import Callable, Tuple, Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass(order=True)
class _Task:
    """Item interno da fila de prioridade."""
    exec_time: float
    id: int
    callback: Callable = field(compare=False)
    args: Tuple = field(compare=False)
    cancelled: bool = field(default=False, compare=False)


class Scheduler:
    """Agenda tarefas para execução em momentos específicos (tempo absoluto)."""

    def __init__(self):
        self._queue: list[_Task] = []
        self._counter = 0
        self._active_tasks: Dict[int, _Task] = {}  # ID -> tarefa

    def schedule(self, delay: float, callback: Callable, *args) -> int:
        """
        Agenda uma callback após 'delay' segundos (tempo absoluto).

        Retorna um ID que pode ser usado para cancelar.
        """
        exec_time = time.time() + delay
        self._counter += 1
        task = _Task(exec_time, self._counter, callback, args)
        heapq.heappush(self._queue, task)
        self._active_tasks[task.id] = task
        return task.id

    def cancel(self, task_id: int) -> bool:
        """Cancela uma tarefa agendada pelo ID. Retorna True se foi cancelada."""
        task = self._active_tasks.get(task_id)
        if task is None:
            return False
        task.cancelled = True
        del self._active_tasks[task_id]
        return True

    def tick(self) -> None:
        """Executa todas as tarefas cujo tempo de execução já passou."""
        now = time.time()
        while self._queue and self._queue[0].exec_time <= now:
            task = heapq.heappop(self._queue)
            # Remove do dicionário de ativas
            self._active_tasks.pop(task.id, None)
            if not task.cancelled:
                try:
                    task.callback(*task.args)
                except Exception as e:
                    # Log do erro (usando logger global)
                    from .logger import LOGGER
                    LOGGER.error("Scheduler", f"Erro ao executar tarefa {task.id}: {e}")

    def clear(self) -> None:
        """Remove todas as tarefas pendentes."""
        self._queue.clear()
        self._active_tasks.clear()

    def pending_count(self) -> int:
        """Número de tarefas ainda pendentes (não executadas)."""
        return len(self._active_tasks)

    def has_pending(self) -> bool:
        return bool(self._active_tasks)