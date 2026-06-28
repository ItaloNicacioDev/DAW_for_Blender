"""
DAW Engine - Ring Buffer

Buffer circular para comunicação entre threads.

Características:

- FIFO
- Baixa latência
- Sem realocação
- Ideal para Audio Thread
"""

from __future__ import annotations

from collections import deque
from threading import Lock


class RingBuffer:

    def __init__(self, capacity: int):

        self.capacity = capacity

        self._buffer = deque(maxlen=capacity)

        self._lock = Lock()

    # ------------------------------------------------------------

    def write(self, item):

        """
        Adiciona um item.

        Retorna False caso o buffer esteja cheio.
        """

        with self._lock:

            if len(self._buffer) >= self.capacity:
                return False

            self._buffer.append(item)

            return True

    # ------------------------------------------------------------

    def read(self):

        """
        Remove o item mais antigo.

        Retorna None caso vazio.
        """

        with self._lock:

            if not self._buffer:
                return None

            return self._buffer.popleft()

    # ------------------------------------------------------------

    def peek(self):

        """
        Apenas consulta o próximo item.
        """

        with self._lock:

            if not self._buffer:
                return None

            return self._buffer[0]

    # ------------------------------------------------------------

    def clear(self):

        with self._lock:

            self._buffer.clear()

    # ------------------------------------------------------------

    def full(self):

        return len(self._buffer) >= self.capacity

    # ------------------------------------------------------------

    def empty(self):

        return len(self._buffer) == 0

    # ------------------------------------------------------------

    def size(self):

        return len(self._buffer)

    # ------------------------------------------------------------

    def available(self):

        return self.capacity - len(self._buffer)

    # ------------------------------------------------------------

    def __len__(self):

        return len(self._buffer)

    # ------------------------------------------------------------

    def __repr__(self):

        return (
            f"<RingBuffer "
            f"{len(self._buffer)}/{self.capacity}>"
        )