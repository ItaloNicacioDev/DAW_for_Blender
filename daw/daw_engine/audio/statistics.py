"""
DAW Engine - Runtime Statistics

Coleta informações da Engine em tempo real.

Nenhum processamento de áudio deve ocorrer aqui.
"""

from __future__ import annotations

import time

from dataclasses import dataclass, field


@dataclass(slots=True)
class EngineStatistics:

    # --------------------------------------------------------

    callback_count: int = 0

    frames_processed: int = 0

    xruns: int = 0

    dropped_buffers: int = 0

    overruns: int = 0

    underruns: int = 0

    cpu_load: float = 0.0

    peak_cpu_load: float = 0.0

    average_callback_time: float = 0.0

    sample_rate: int = 0

    buffer_size: int = 0

    started_at: float = field(default_factory=time.perf_counter)

    # --------------------------------------------------------

    def reset(self):

        self.callback_count = 0

        self.frames_processed = 0

        self.xruns = 0

        self.dropped_buffers = 0

        self.overruns = 0

        self.underruns = 0

        self.cpu_load = 0.0

        self.peak_cpu_load = 0.0

        self.average_callback_time = 0.0

        self.started_at = time.perf_counter()

    # --------------------------------------------------------

    def update_callback(

        self,

        callback_time: float,

        frames: int,

        buffer_duration: float,

    ):

        """
        Atualiza estatísticas após cada callback.
        """

        self.callback_count += 1

        self.frames_processed += frames

        self.average_callback_time = (

            (

                self.average_callback_time

                *

                (self.callback_count - 1)

            )

            +

            callback_time

        ) / self.callback_count

        self.cpu_load = callback_time / buffer_duration

        if self.cpu_load > self.peak_cpu_load:

            self.peak_cpu_load = self.cpu_load

    # --------------------------------------------------------

    @property

    def uptime(self):

        return time.perf_counter() - self.started_at

    # --------------------------------------------------------

    @property

    def fps(self):

        if self.uptime == 0:

            return 0.0

        return self.callback_count / self.uptime

    # --------------------------------------------------------

    def as_dict(self):

        return {

            "callback_count": self.callback_count,

            "frames_processed": self.frames_processed,

            "xruns": self.xruns,

            "dropped_buffers": self.dropped_buffers,

            "overruns": self.overruns,

            "underruns": self.underruns,

            "cpu_load": self.cpu_load,

            "peak_cpu_load": self.peak_cpu_load,

            "average_callback_time": self.average_callback_time,

            "sample_rate": self.sample_rate,

            "buffer_size": self.buffer_size,

            "uptime": self.uptime,

        }


ENGINE_STATS = EngineStatistics()