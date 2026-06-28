# core/profiler.py
"""Ferramenta de profiling para medir desempenho."""
import time
from collections import defaultdict

class Profiler:
    """Mede tempos de execução de funções/blocos."""
    def __init__(self):
        self._timings = defaultdict(list)

    def start(self, label: str):
        self._timings[label].append(('start', time.time()))

    def end(self, label: str):
        if self._timings[label] and self._timings[label][-1][0] == 'start':
            start_time = self._timings[label].pop()[1]
            elapsed = time.time() - start_time
            self._timings[label].append(('end', elapsed))
            return elapsed
        return None

    def report(self):
        """Retorna um dicionário com estatísticas."""
        report = {}
        for label, entries in self._timings.items():
            times = [e[1] for e in entries if e[0] == 'end']
            if times:
                report[label] = {
                    'count': len(times),
                    'total': sum(times),
                    'avg': sum(times)/len(times),
                    'max': max(times),
                    'min': min(times)
                }
        return report