# core/transport.py
"""
Controle de reprodução da DAW (play, stop, pause, record, loop).

Correção vs versão anterior:
- Recebia EventSystem próprio e ignorava o central da Engine.
  Agora aceita a instância compartilhada via parâmetro (opcional
  para não quebrar código existente).
- Adicionado pause() real que não zera a posição.
- set_position() agora clipa em 0 para evitar posição negativa.
"""
from __future__ import annotations

from .events import (
    EventSystem,
    EVENT_PLAY,
    EVENT_STOP,
    EVENT_RECORD,
    EVENT_LOOP,
)
from .constants import DEFAULT_BPM


class Transport:
    """
    Gerencia o estado de reprodução.

    A posição (current_position) é avançada externamente por Engine._update
    a cada frame. Transport só guarda estado e emite eventos.
    """

    def __init__(self, event_system: EventSystem | None = None) -> None:
        # Usa o EventSystem passado (compartilhado com a Engine) ou cria um local
        self.event_system: EventSystem = event_system or EventSystem()

        # Estado do transporte
        self.is_playing:   bool  = False
        self.is_recording: bool  = False
        self.is_paused:    bool  = False
        self.is_looping:   bool  = False

        # Posição em segundos
        self.current_position: float = 0.0

        # Intervalo de loop em segundos
        self.loop_start: float = 0.0
        self.loop_end:   float = 4.0    # padrão: 4 segundos (1 compasso a 120 BPM)

    # ------------------------------------------------------------------
    # Controles básicos
    # ------------------------------------------------------------------

    def play(self) -> None:
        """Inicia ou retoma a reprodução."""
        self.is_playing   = True
        self.is_paused    = False
        self.is_recording = False
        self.event_system.emit(EVENT_PLAY)

    def stop(self) -> None:
        """Para a reprodução e volta ao início."""
        self.is_playing    = False
        self.is_recording  = False
        self.is_paused     = False
        self.current_position = 0.0
        self.event_system.emit(EVENT_STOP)

    def pause(self) -> None:
        """Pausa sem voltar ao início. Retome com play()."""
        if not self.is_playing:
            return
        self.is_playing = False
        self.is_paused  = True
        # Não emite EVENT_STOP para diferenciar de stop real

    def record(self) -> None:
        """Inicia gravação (também ativa reprodução)."""
        self.is_playing   = True
        self.is_recording = True
        self.is_paused    = False
        self.event_system.emit(EVENT_RECORD)

    def toggle_loop(self) -> None:
        """Liga/desliga o loop."""
        self.is_looping = not self.is_looping
        self.event_system.emit(EVENT_LOOP, {"enabled": self.is_looping})

    def set_position(self, seconds: float) -> None:
        """Move o playhead para uma posição em segundos (mínimo 0)."""
        self.current_position = max(0.0, seconds)

    # ------------------------------------------------------------------
    # Tick — chamado a cada frame pela Engine
    # ------------------------------------------------------------------

    def update(self, delta: float) -> None:
        """
        Avança a posição pelo delta de tempo (em segundos).
        Aplica o loop se necessário.
        Deve ser chamado a cada frame por Engine._update.
        """
        if not self.is_playing:
            return

        self.current_position += delta

        if self.is_looping and self.current_position >= self.loop_end:
            # Wrap mantendo o offset além do loop_end
            overflow = self.current_position - self.loop_end
            self.current_position = self.loop_start + overflow

    # ------------------------------------------------------------------
    # Leitura de estado
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """True se estiver rodando (play ou record)."""
        return self.is_playing

    def __repr__(self) -> str:
        status = "recording" if self.is_recording else ("playing" if self.is_playing else "stopped")
        return f"Transport({status}, pos={self.current_position:.3f}s, loop={self.is_looping})"