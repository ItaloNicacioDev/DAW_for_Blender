# modules/vst/realtime/ring_buffer.py
"""
Buffer circular de áudio estéreo indexado por TEMPO ABSOLUTO (segundos),
não por posição de escrita/leitura relativa.

Por quê: o produtor (PrefetchThread) e o consumidor (RingBufferSound, ver
aud_source.py) não avançam em lockstep -- o produtor pode estar 1.5s à
frente do playhead, e o consumidor lê exatamente na posição do playhead.
Indexar por tempo absoluto deixa write()/read()/invalidate_from() simples
de raciocinar, sem contabilidade manual de "quantos samples de folga".

Este módulo é 100% Python/numpy puro -- sem bpy, aud ou dawdreamer -- de
propósito, pra poder ser testado fora do Blender (ver
tests/test_ring_buffer.py).
"""
from __future__ import annotations

import threading
from typing import Optional

import numpy as np


class RingBuffer:
    """
    Buffer circular estéreo de duração fixa (`capacity_seconds`), que
    "desliza" junto com o tempo: escrever além da capacidade sobrescreve
    o trecho mais antigo. Pensado para conter só a janela
    [now - PAST_MARGIN, now + HORIZON] em volta do playhead -- não a
    timeline inteira.

    Todas as posições de tempo são em SEGUNDOS ABSOLUTOS da timeline
    (mesma referência que `scene.frame_current / fps`), não relativas ao
    buffer.
    """

    def __init__(self, sample_rate: int = 44100, capacity_seconds: float = 4.0):
        if capacity_seconds <= 0:
            raise ValueError("capacity_seconds precisa ser positivo")
        self.sample_rate = int(sample_rate)
        self.capacity_seconds = float(capacity_seconds)
        self.capacity_samples = int(round(self.capacity_seconds * self.sample_rate))

        self._lock = threading.Lock()
        self._data = np.zeros((2, self.capacity_samples), dtype=np.float32)

        # Máscara paralela: True = amostra válida (já renderizada e
        # ainda dentro da janela), False = silêncio/desconhecido. Sem
        # isso não daria pra distinguir "trecho pré-renderizado com
        # silêncio de verdade" de "trecho que a thread de prefetch
        # ainda não chegou".
        self._valid = np.zeros(self.capacity_samples, dtype=bool)

        # `filled_until` é a fronteira de tempo (em segundos) até onde o
        # produtor já escreveu de forma contígua a partir do início da
        # janela atual. É o que o PrefetchThread consulta pra saber até
        # onde continuar renderizando.
        self._filled_until: float = 0.0
        self._window_start: float = 0.0  # início (em segundos) do buffer

    # ------------------------------------------------------------------
    # Consulta de estado (usado pelo PrefetchThread para decidir o que
    # ainda falta renderizar)
    # ------------------------------------------------------------------
    @property
    def filled_until(self) -> float:
        with self._lock:
            return self._filled_until

    @property
    def window_start(self) -> float:
        with self._lock:
            return self._window_start

    def _time_to_index(self, t: float) -> int:
        offset = t - self._window_start
        idx = int(round(offset * self.sample_rate))
        return idx % self.capacity_samples

    # ------------------------------------------------------------------
    # Escrita (chamada pela PrefetchThread)
    # ------------------------------------------------------------------
    def write(self, chunk: np.ndarray, start_time: float) -> None:
        """
        Escreve `chunk` (shape (2, N) float32) começando em `start_time`
        (segundos absolutos). Deve ser chamado com `start_time` igual ao
        `filled_until` atual (escrita sempre contígua, sem buracos) --
        caso contrário levanta ValueError, porque um buraco silencioso
        no meio do buffer é um bug mais perigoso de deixar passar batido
        do que travar em teste.
        """
        chunk = np.ascontiguousarray(chunk, dtype=np.float32)
        if chunk.ndim != 2 or chunk.shape[0] != 2:
            raise ValueError(f"chunk precisa ter shape (2, N), recebeu {chunk.shape}")

        n = chunk.shape[1]
        if n == 0:
            return

        with self._lock:
            if abs(start_time - self._filled_until) > (0.5 / self.sample_rate):
                raise ValueError(
                    f"escrita não-contígua: start_time={start_time:.6f} != "
                    f"filled_until={self._filled_until:.6f} (use invalidate_from() "
                    f"antes de reescrever um trecho já preenchido)"
                )

            for i in range(n):
                idx = self._time_to_index(start_time + i / self.sample_rate)
                self._data[:, idx] = chunk[:, i]
                self._valid[idx] = True

            self._filled_until = start_time + n / self.sample_rate

    # ------------------------------------------------------------------
    # Leitura (chamada pelo consumidor -- RingBufferSound / aud)
    # ------------------------------------------------------------------
    def read(self, start_time: float, n_samples: int) -> np.ndarray:
        """
        Lê `n_samples` a partir de `start_time`. Trechos ainda não
        preenchidos (produtor atrasado) ou fora da janela atual do
        buffer voltam como silêncio -- este método NUNCA bloqueia nem
        levanta exceção por causa de dado faltando, porque é chamado da
        thread de áudio do Blender (não pode travar).
        """
        out = np.zeros((2, n_samples), dtype=np.float32)
        if n_samples <= 0:
            return out

        with self._lock:
            window_end = self._window_start + self.capacity_seconds
            for i in range(n_samples):
                t = start_time + i / self.sample_rate
                if t < self._window_start or t >= window_end:
                    continue  # fora da janela: silêncio
                idx = self._time_to_index(t)
                if self._valid[idx]:
                    out[:, i] = self._data[:, idx]
                # senão: ainda não renderizado -> silêncio (default do np.zeros)
        return out

    # ------------------------------------------------------------------
    # Invalidação (chamada quando um parâmetro muda durante o play)
    # ------------------------------------------------------------------
    def invalidate_from(self, t: float) -> None:
        """
        Marca tudo a partir de `t` (segundos absolutos) como inválido e
        volta `filled_until` para `t`, forçando a PrefetchThread a
        re-renderizar dali em diante na próxima iteração. Não mexe no
        que já foi tocado (antes de `t`) -- automação e parâmetros só
        afetam o futuro, igual numa DAW de verdade.
        """
        with self._lock:
            if t >= self._filled_until:
                return  # nada a invalidar, já está "no futuro" do que foi escrito
            t = max(t, self._window_start)
            window_end = self._window_start + self.capacity_seconds
            valid_until = min(self._filled_until, window_end)
            i0 = self._time_to_index(t)
            n = int(round((valid_until - t) * self.sample_rate))
            for k in range(max(n, 0)):
                idx = (i0 + k) % self.capacity_samples
                self._valid[idx] = False
            self._filled_until = t

    def advance_window(self, new_window_start: float) -> None:
        """
        Desliza a janela do buffer pra frente (chamado periodicamente
        pelo PlaybackSupervisor conforme o playhead avança), invalidando
        implicitamente qualquer coisa que ficou pra trás da nova janela.
        Não precisa fazer nada com os dados físicos -- `_time_to_index`
        já é módulo circular, então o próximo `write()` naturalmente
        sobrescreve as amostras antigas que caem fora da nova janela.
        """
        with self._lock:
            if new_window_start <= self._window_start:
                return
            self._window_start = new_window_start
            if self._filled_until < new_window_start:
                self._filled_until = new_window_start

    def reset(self, at_time: float = 0.0) -> None:
        """Limpa o buffer inteiro (usado em seek/scrub do playhead)."""
        with self._lock:
            self._data.fill(0.0)
            self._valid.fill(False)
            self._window_start = at_time
            self._filled_until = at_time