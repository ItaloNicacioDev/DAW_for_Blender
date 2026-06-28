"""
DAW Engine - Audio State

Este módulo contém o estado global da Engine de Áudio.

Nenhum processamento de áudio deve acontecer aqui.

Responsabilidades:

- Estado do transporte
- Estado do dispositivo
- Configuração atualmente carregada
- Informações em tempo real
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import AudioConfig, ENGINE_CONFIG
from .backend import AudioBackend


@dataclass(slots=True)
class AudioState:
    """
    Estado global da Engine.

    Existe apenas UMA instância dessa classe.
    """

    # ==========================================================
    # TRANSPORT
    # ==========================================================

    playing: bool = False
    paused: bool = False
    recording: bool = False

    # ==========================================================
    # ENGINE
    # ==========================================================

    initialized: bool = False
    stream_running: bool = False

    # ==========================================================
    # CONFIG
    # ==========================================================

    config: AudioConfig = field(default_factory=lambda: ENGINE_CONFIG)

    # ==========================================================
    # DEVICE
    # ==========================================================

    backend: AudioBackend | None = None

    output_device: int | None = None

    input_device: int | None = None

    # ==========================================================
    # RUNTIME
    # ==========================================================

    cpu_load: float = 0.0

    xruns: int = 0

    frames_processed: int = 0

    # ==========================================================
    # PROPERTIES
    # ==========================================================

    @property
    def sample_rate(self) -> int:
        return self.config.sample_rate

    @property
    def buffer_size(self) -> int:
        return self.config.buffer_size

    @property
    def channels(self) -> int:
        return self.config.channels

    @property
    def latency(self):
        return self.config.latency

    # ==========================================================
    # HELPERS
    # ==========================================================

    def reset_runtime(self):
        """
        Limpa apenas informações temporárias.

        Não altera configurações.
        """

        self.cpu_load = 0.0
        self.xruns = 0
        self.frames_processed = 0

    def stop(self):
        """
        Coloca a engine em estado parado.
        """

        self.playing = False
        self.paused = False
        self.recording = False
        self.stream_running = False

    def play(self):
        self.playing = True
        self.paused = False

    def pause(self):
        self.paused = True

    def record(self):
        self.recording = True


# ==========================================================
# Singleton Global
# ==========================================================

ENGINE_STATE = AudioState()