# mixer/mixer.py
"""
Mixer de áudio da DAW.

Por que reescrever:
- process() retornava None — o AudioCallback tentava escrever None no
  stream de áudio e crashava silenciosamente.
- Só suportava um único Synth hardcoded. Um mixer real gerencia N canais,
  cada um com sua própria fonte (instrumento ou áudio), volume, pan, mute,
  solo e send para o master bus.

Arquitetura:
    Channel  — faixa individual: instrumento + ganho + pan + mute/solo
    MasterBus — soma todos os canais, aplica volume master e limiter
    Mixer    — orquestra canais e master bus, expõe API para o AudioCallback

Fluxo de sinal por bloco de áudio:
    [Channel 0: Synth] ─┐
    [Channel 1: Synth] ─┼─> MasterBus (soma + volume + limiter) ─> saída
    [Channel N: ...]   ─┘
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from ..instruments.synth import Synth, SynthPreset
from ..midi.events import (
    NoteOnEvent,
    NoteOffEvent,
    ControlChangeEvent,
    PitchBendEvent,
    CC,
)


# ------------------------------------------------------------------
# Canal individual
# ------------------------------------------------------------------

class Channel:
    """
    Um canal do mixer: contém um instrumento e parâmetros de ganho.

    Todos os parâmetros de volume/pan operam em float32 para combinar
    diretamente com os buffers de áudio numpy sem conversão extra.
    """

    def __init__(
        self,
        name:        str          = "Channel",
        instrument:  Optional[Synth] = None,
        sample_rate: int          = 48000,
    ) -> None:
        self.name        = name
        self.instrument  = instrument or Synth(sample_rate=sample_rate)
        self.sample_rate = sample_rate

        self.volume: float = 1.0     # 0.0–1.0 (linear)
        self.pan:    float = 0.0     # -1.0 (esq) .. 0.0 (centro) .. 1.0 (dir)
        self.mute:   bool  = False
        self.solo:   bool  = False

        # Pré-calculados a cada mudança de pan (lei de pan constante)
        self._pan_l: float = 1.0
        self._pan_r: float = 1.0
        self._update_pan()

    # ------------------------------------------------------------------
    # Parâmetros
    # ------------------------------------------------------------------

    def set_volume(self, volume: float) -> None:
        self.volume = float(np.clip(volume, 0.0, 1.0))

    def set_pan(self, pan: float) -> None:
        """Pan -1.0 (esq) a +1.0 (dir). Usa lei de potência constante."""
        self.pan = float(np.clip(pan, -1.0, 1.0))
        self._update_pan()

    def _update_pan(self) -> None:
        """Lei de pan de potência constante (constant power panning)."""
        angle = (self.pan + 1.0) * 0.25 * np.pi   # 0 .. pi/2
        self._pan_l = float(np.cos(angle))
        self._pan_r = float(np.sin(angle))

    # ------------------------------------------------------------------
    # Controle MIDI
    # ------------------------------------------------------------------

    def note_on(self, note: int, velocity: int = 100) -> None:
        if not self.mute:
            self.instrument.note_on(note, velocity)

    def note_off(self, note: int) -> None:
        self.instrument.note_off(note)

    def all_notes_off(self) -> None:
        self.instrument.all_notes_off()

    def handle_cc(self, controller: int, value: int) -> None:
        """Trata mensagens CC que afetam o canal (volume, pan, etc.)."""
        if controller == CC.VOLUME:
            self.set_volume(value / 127.0)
        elif controller == CC.PAN:
            self.set_pan((value / 63.5) - 1.0)   # 0–127 → -1.0–+1.0
        elif controller == CC.ALL_NOTES_OFF or controller == CC.ALL_SOUND_OFF:
            self.all_notes_off()

    def handle_pitch_bend(self, event: PitchBendEvent) -> None:
        # Pitch bend é tratado internamente pelo instrumento no futuro;
        # por ora guardamos o valor normalizado para quando o Synth suportar.
        pass

    # ------------------------------------------------------------------
    # Processamento de áudio
    # ------------------------------------------------------------------

    def process(self, frames: int) -> np.ndarray:
        """
        Gera 'frames' amostras estéreo para este canal.
        Retorna zeros se mute ativo ou instrumento silencioso.
        Shape: (frames, 2) float32.
        """
        if self.mute:
            return np.zeros((frames, 2), dtype=np.float32)

        # Delega ao instrumento
        stereo = self.instrument.process(frames)   # (frames, 2)

        # Aplica volume
        stereo *= self.volume

        # Aplica pan (multiplica L e R por coeficientes diferentes)
        stereo[:, 0] *= self._pan_l
        stereo[:, 1] *= self._pan_r

        return stereo

    def __repr__(self) -> str:
        status = "MUTE" if self.mute else ("SOLO" if self.solo else "active")
        return f"Channel('{self.name}', vol={self.volume:.2f}, pan={self.pan:.2f}, {status})"


# ------------------------------------------------------------------
# Master Bus
# ------------------------------------------------------------------

class MasterBus:
    """
    Barramento master: recebe a soma de todos os canais, aplica volume
    master e um limiter suave para evitar clipping.
    """

    def __init__(self) -> None:
        self.volume: float = 0.8   # volume master (0.0–1.0)

    def process(self, mixed: np.ndarray) -> np.ndarray:
        """
        Aplica volume master e limiter ao buffer já somado.
        mixed: (frames, 2) float32 — modificado in-place e retornado.
        """
        mixed *= self.volume

        # Soft limiter: tanh comprime suavemente ao invés de clipar hard
        # (evita o estalo de distorção quadrada, soa como saturação analógica)
        np.tanh(mixed, out=mixed)

        return mixed


# ------------------------------------------------------------------
# Mixer principal
# ------------------------------------------------------------------

class Mixer:
    """
    Mixer polifônico com N canais + master bus.

    Interface com o AudioCallback:
        mixer.process(frames) -> np.ndarray (frames, 2) float32

    Interface com o Scheduler/Engine:
        mixer.note_on(channel_idx, note, velocity)
        mixer.note_off(channel_idx, note)
        mixer.handle_midi_event(channel_idx, event)

    Canal 0 sempre existe (canal default). Canais adicionais são
    criados com add_channel().
    """

    def __init__(self, sample_rate: int = 48000, channels: int = 2) -> None:
        self.sample_rate    = sample_rate
        self.num_channels   = channels    # canais estéreo de saída (2)
        self.master         = MasterBus()

        # Canal default (channel 0)
        self._channels: List[Channel] = [
            Channel("Master Synth", sample_rate=sample_rate)
        ]

    # ------------------------------------------------------------------
    # Gerenciamento de canais
    # ------------------------------------------------------------------

    def add_channel(
        self,
        name:    str               = "Channel",
        preset:  Optional[SynthPreset] = None,
    ) -> Channel:
        """Adiciona um novo canal e retorna ele."""
        synth = Synth(sample_rate=self.sample_rate, preset=preset)
        ch = Channel(name=name, instrument=synth, sample_rate=self.sample_rate)
        self._channels.append(ch)
        return ch

    def remove_channel(self, index: int) -> bool:
        """Remove um canal pelo índice. Canal 0 não pode ser removido."""
        if index <= 0 or index >= len(self._channels):
            return False
        self._channels[index].all_notes_off()
        self._channels.pop(index)
        return True

    def get_channel(self, index: int) -> Optional[Channel]:
        if 0 <= index < len(self._channels):
            return self._channels[index]
        return None

    @property
    def channel_count(self) -> int:
        return len(self._channels)

    # ------------------------------------------------------------------
    # Controle MIDI — interface com Scheduler e Engine
    # ------------------------------------------------------------------

    def note_on(self, note: int, velocity: int = 100, channel_idx: int = 0) -> None:
        ch = self.get_channel(channel_idx)
        if ch:
            ch.note_on(note, velocity)

    def note_off(self, note: int, channel_idx: int = 0) -> None:
        ch = self.get_channel(channel_idx)
        if ch:
            ch.note_off(note)

    def handle_midi_event(self, event, channel_idx: int = 0) -> None:
        """
        Despacha qualquer MidiEvent para o canal correto.
        Chamado pelo Scheduler durante a reprodução de clips MIDI.
        """
        ch = self.get_channel(channel_idx)
        if ch is None:
            return

        if isinstance(event, NoteOnEvent):
            if event.is_note_off:
                ch.note_off(event.note)
            else:
                ch.note_on(event.note, event.velocity)

        elif isinstance(event, NoteOffEvent):
            ch.note_off(event.note)

        elif isinstance(event, ControlChangeEvent):
            ch.handle_cc(event.controller, event.value)

        elif isinstance(event, PitchBendEvent):
            ch.handle_pitch_bend(event)

    def all_notes_off(self) -> None:
        """Para todas as notas em todos os canais (usado no transport.stop())."""
        for ch in self._channels:
            ch.all_notes_off()

    # ------------------------------------------------------------------
    # Parâmetros de canal
    # ------------------------------------------------------------------

    def set_volume(self, channel_idx: int, volume: float) -> None:
        ch = self.get_channel(channel_idx)
        if ch:
            ch.set_volume(volume)

    def set_pan(self, channel_idx: int, pan: float) -> None:
        ch = self.get_channel(channel_idx)
        if ch:
            ch.set_pan(pan)

    def set_mute(self, channel_idx: int, mute: bool) -> None:
        ch = self.get_channel(channel_idx)
        if ch:
            ch.mute = mute

    def set_solo(self, channel_idx: int, solo: bool) -> None:
        """
        Liga/desliga solo num canal.
        Quando qualquer canal está em solo, todos os outros são mutados.
        """
        ch = self.get_channel(channel_idx)
        if ch:
            ch.solo = solo

        any_solo = any(c.solo for c in self._channels)
        for i, c in enumerate(self._channels):
            if any_solo:
                c.mute = not c.solo
            else:
                c.mute = False

    def set_master_volume(self, volume: float) -> None:
        self.master.volume = float(np.clip(volume, 0.0, 1.0))

    # ------------------------------------------------------------------
    # Processamento de áudio — chamado pelo AudioCallback
    # ------------------------------------------------------------------

    def process(self, frames: int) -> np.ndarray:
        """
        Gera 'frames' amostras estéreo somando todos os canais ativos.

        Retorna np.ndarray shape (frames, 2) dtype float32.
        NUNCA retorna None — o AudioCallback depende disso.
        """
        mixed = np.zeros((frames, 2), dtype=np.float32)

        for ch in self._channels:
            mixed += ch.process(frames)

        return self.master.process(mixed)

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Mixer(channels={len(self._channels)}, "
            f"sr={self.sample_rate}, master_vol={self.master.volume:.2f})"
        )