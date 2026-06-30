# core/profiler.py
"""
Ferramenta de profiling para medir desempenho de funções/blocos da DAW.

Correção vs versão anterior:
- start()/end() guardavam tudo na mesma lista misturando tuplas
  ('start', t) e ('end', elapsed) — funcional, mas frágil: uma chamada
  end() sem start() correspondente, ou start() duplicado sem end(),
  corrompe o histórico silenciosamente. Reescrito com uma pilha de
  início por label e uma lista separada de durações concluídas.
- Adicionado context manager (`with profiler.measure("label"):`) que é
  a forma mais segura de usar — não tem como esquecer o end().
- Adicionado reset() para limpar entre sessões de profiling.
"""
from __future__ import annotations

import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Dict, List


class Profiler:
    """
    Mede tempos de execução de funções/blocos de código.

    Uso recomendado (context manager — seguro contra exceções):
        with profiler.measure("audio_callback"):
            do_something()

    Uso manual (cuidado: end() deve sempre ser chamado):
        profiler.start("label")
        do_something()
        profiler.end("label")
    """

    def __init__(self) -> None:
        # Pilha de starts pendentes por label (permite chamadas aninhadas
        # do mesmo label, ex: recursão)
        self._pending: Dict[str, List[float]] = defaultdict(list)
        # Durações já concluídas por label
        self._durations: Dict[str, List[float]] = defaultdict(list)

    # ------------------------------------------------------------------
    # API manual
    # ------------------------------------------------------------------

    def start(self, label: str) -> None:
        """Marca o início da medição para 'label'."""
        self._pending[label].append(time.perf_counter())

    def end(self, label: str) -> float | None:
        """
        Marca o fim da medição para 'label' e retorna a duração em segundos.
        Retorna None se não havia start() pendente para esse label.
        """
        stack = self._pending.get(label)
        if not stack:
            return None

        start_time = stack.pop()
        elapsed = time.perf_counter() - start_time
        self._durations[label].append(elapsed)
        return elapsed

    # ------------------------------------------------------------------
    # Context manager — forma segura de uso
    # ------------------------------------------------------------------

    @contextmanager
    def measure(self, label: str):
        """
        Context manager que mede o bloco automaticamente,
        mesmo se uma exceção for lançada dentro dele.
        """
        start_time = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start_time
            self._durations[label].append(elapsed)

    # ------------------------------------------------------------------
    # Relatórios
    # ------------------------------------------------------------------

    def report(self) -> Dict[str, Dict[str, float]]:
        """Retorna estatísticas (count, total, avg, max, min) por label."""
        result: Dict[str, Dict[str, float]] = {}
        for label, times in self._durations.items():
            if not times:
                continue
            result[label] = {
                "count": len(times),
                "total": sum(times),
                "avg":   sum(times) / len(times),
                "max":   max(times),
                "min":   min(times),
            }
        return result

    def report_string(self) -> str:
        """Versão formatada em texto do relatório, útil para print/log."""
        lines = []
        for label, stats in sorted(self.report().items(), key=lambda kv: -kv[1]["total"]):
            lines.append(
                f"{label:<24} count={stats['count']:<5} "
                f"avg={stats['avg']*1000:.3f}ms "
                f"max={stats['max']*1000:.3f}ms "
                f"total={stats['total']*1000:.1f}ms"
            )
        return "\n".join(lines) if lines else "(sem dados de profiling)"

    def reset(self, label: str | None = None) -> None:
        """Limpa os dados de profiling — de um label específico ou todos."""
        if label is None:
            self._pending.clear()
            self._durations.clear()
        else:
            self._pending.pop(label, None)
            self._durations.pop(label, None)

    def __repr__(self) -> str:
        return f"Profiler(labels={list(self._durations.keys())})"