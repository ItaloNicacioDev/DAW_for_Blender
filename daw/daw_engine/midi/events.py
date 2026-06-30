# midi/events.py
"""
Eventos MIDI da DAW.

Por que reescrever:
- NoteEvent só tinha (on, track, note, velocity) — sem campo de tempo,
  impossível agendar ou ordenar eventos na timeline.
- Sem outros tipos de evento: CC, pitch bend, program change, aftertouch,
  clock — eventos que qualquer DAW real precisa tratar.
- Sem validação de range MIDI (0–127 para note/velocity/channel, etc).
- Sem distinção clara entre NoteOn e NoteOff — o campo booleano `on`
  é frágil em serialização e comparação.

Esta versão:
- Define uma hierarquia de MidiEvent com tempo (time_sec e tick).
- Cobre os tipos de mensagem MIDI 1.0 mais usados numa DAW.
- Inclui helpers de conversão (bytes raw <-> dataclass) para integração
  com dispositivos físicos via python-rtmidi ou mido.
- MidiSequence: lista ordenada de eventos que representa um clip MIDI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple


# ------------------------------------------------------------------
# Status bytes MIDI 1.0 (nibble alto; nibble baixo = canal 0-15)
# ------------------------------------------------------------------

class MidiStatus(IntEnum):
    NOTE_OFF        = 0x80
    NOTE_ON         = 0x90
    AFTERTOUCH      = 0xA0   # Polyphonic key pressure
    CONTROL_CHANGE  = 0xB0
    PROGRAM_CHANGE  = 0xC0
    CHANNEL_PRESSURE = 0xD0  # Channel aftertouch
    PITCH_BEND      = 0xE0
    SYSEX           = 0xF0
    CLOCK           = 0xF8
    START           = 0xFA
    CONTINUE        = 0xFB
    STOP            = 0xFC


# ------------------------------------------------------------------
# Números de CC comuns (para autocompletar/UI)
# ------------------------------------------------------------------

class CC(IntEnum):
    MODULATION    = 1
    VOLUME        = 7
    PAN           = 10
    EXPRESSION    = 11
    SUSTAIN_PEDAL = 64
    ALL_SOUND_OFF = 120
    ALL_NOTES_OFF = 123


# ------------------------------------------------------------------
# Base
# ------------------------------------------------------------------

@dataclass
class MidiEvent:
    """
    Evento MIDI base com posição temporal.

    time_sec: posição em segundos na timeline do projeto
    tick:     posição em ticks MIDI (depende de PPQ e BPM)
    channel:  canal MIDI 0–15 (0 = canal 1 na notação 1-based)
    """
    time_sec: float = 0.0
    tick:     int   = 0
    channel:  int   = 0

    def __post_init__(self) -> None:
        self.channel = int(self.channel) & 0x0F   # garante 0–15

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type":     self.__class__.__name__,
            "time_sec": self.time_sec,
            "tick":     self.tick,
            "channel":  self.channel,
        }


# ------------------------------------------------------------------
# Note On / Note Off
# ------------------------------------------------------------------

@dataclass
class NoteOnEvent(MidiEvent):
    """Nota pressionada."""
    note:     int = 60   # 0–127
    velocity: int = 100  # 0–127  (velocity=0 equivale a NoteOff)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.note     = int(self.note)     & 0x7F
        self.velocity = int(self.velocity) & 0x7F

    @property
    def is_note_off(self) -> bool:
        """NoteOn com velocity 0 é tratado como NoteOff no protocolo MIDI."""
        return self.velocity == 0

    def to_raw(self) -> Tuple[int, int, int]:
        return (MidiStatus.NOTE_ON | self.channel, self.note, self.velocity)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({"note": self.note, "velocity": self.velocity})
        return d


@dataclass
class NoteOffEvent(MidiEvent):
    """Nota solta."""
    note:     int = 60
    velocity: int = 0    # velocity de release (maioria dos sinths ignora)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.note     = int(self.note)     & 0x7F
        self.velocity = int(self.velocity) & 0x7F

    def to_raw(self) -> Tuple[int, int, int]:
        return (MidiStatus.NOTE_OFF | self.channel, self.note, self.velocity)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({"note": self.note, "velocity": self.velocity})
        return d


# ------------------------------------------------------------------
# Control Change
# ------------------------------------------------------------------

@dataclass
class ControlChangeEvent(MidiEvent):
    """Mudança de controlador (CC): volume, pan, modulação, sustain..."""
    controller: int = 0    # 0–127 (ver CC enum acima)
    value:      int = 0    # 0–127

    def __post_init__(self) -> None:
        super().__post_init__()
        self.controller = int(self.controller) & 0x7F
        self.value      = int(self.value)      & 0x7F

    def to_raw(self) -> Tuple[int, int, int]:
        return (MidiStatus.CONTROL_CHANGE | self.channel, self.controller, self.value)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({"controller": self.controller, "value": self.value})
        return d


# ------------------------------------------------------------------
# Pitch Bend
# ------------------------------------------------------------------

@dataclass
class PitchBendEvent(MidiEvent):
    """
    Pitch bend: valor de -8192 a +8191 (centro = 0).
    O protocolo MIDI usa dois bytes de 7 bits (LSB + MSB),
    mas aqui trabalhamos com o valor signed já decodificado.
    """
    value: int = 0   # -8192 a +8191

    def __post_init__(self) -> None:
        super().__post_init__()
        self.value = int(max(-8192, min(8191, self.value)))

    @property
    def normalized(self) -> float:
        """Valor normalizado no range -1.0 a +1.0."""
        return self.value / 8191.0 if self.value != 0 else 0.0

    def to_raw(self) -> Tuple[int, int, int]:
        v = self.value + 8192   # unsigned 0–16383
        lsb = v & 0x7F
        msb = (v >> 7) & 0x7F
        return (MidiStatus.PITCH_BEND | self.channel, lsb, msb)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({"value": self.value})
        return d


# ------------------------------------------------------------------
# Program Change
# ------------------------------------------------------------------

@dataclass
class ProgramChangeEvent(MidiEvent):
    """Troca de preset/patch (0–127)."""
    program: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        self.program = int(self.program) & 0x7F

    def to_raw(self) -> Tuple[int, int]:
        return (MidiStatus.PROGRAM_CHANGE | self.channel, self.program)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({"program": self.program})
        return d


# ------------------------------------------------------------------
# Aftertouch (por tecla)
# ------------------------------------------------------------------

@dataclass
class AftertouchEvent(MidiEvent):
    """Pressão pós-nota (polyphonic aftertouch)."""
    note:     int = 60
    pressure: int = 0    # 0–127

    def __post_init__(self) -> None:
        super().__post_init__()
        self.note     = int(self.note)     & 0x7F
        self.pressure = int(self.pressure) & 0x7F

    def to_raw(self) -> Tuple[int, int, int]:
        return (MidiStatus.AFTERTOUCH | self.channel, self.note, self.pressure)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({"note": self.note, "pressure": self.pressure})
        return d


# ------------------------------------------------------------------
# Factory — reconstrói evento a partir de dict (para carregar projeto)
# ------------------------------------------------------------------

_EVENT_CLASSES = {
    "NoteOnEvent":       NoteOnEvent,
    "NoteOffEvent":      NoteOffEvent,
    "ControlChangeEvent": ControlChangeEvent,
    "PitchBendEvent":    PitchBendEvent,
    "ProgramChangeEvent": ProgramChangeEvent,
    "AftertouchEvent":   AftertouchEvent,
}


def event_from_dict(data: Dict[str, Any]) -> Optional[MidiEvent]:
    """
    Reconstrói um MidiEvent a partir de um dicionário (carregado do JSON).
    Retorna None se o tipo for desconhecido.
    """
    cls = _EVENT_CLASSES.get(data.get("type", ""))
    if cls is None:
        return None
    kwargs = {k: v for k, v in data.items() if k != "type"}
    return cls(**kwargs)


def event_from_raw(
    status: int,
    data1:  int,
    data2:  int = 0,
    time_sec: float = 0.0,
    tick: int = 0,
) -> Optional[MidiEvent]:
    """
    Constrói um MidiEvent a partir de bytes MIDI crus
    (útil para integração com rtmidi/mido que entregam bytes).

    Exemplo:
        msg = [0x90, 60, 100]   # NoteOn, C4, vel 100
        event = event_from_raw(*msg, time_sec=1.5)
    """
    channel = status & 0x0F
    status_type = status & 0xF0

    base = {"time_sec": time_sec, "tick": tick, "channel": channel}

    if status_type == MidiStatus.NOTE_ON:
        if data2 == 0:
            return NoteOffEvent(**base, note=data1, velocity=0)
        return NoteOnEvent(**base, note=data1, velocity=data2)

    elif status_type == MidiStatus.NOTE_OFF:
        return NoteOffEvent(**base, note=data1, velocity=data2)

    elif status_type == MidiStatus.CONTROL_CHANGE:
        return ControlChangeEvent(**base, controller=data1, value=data2)

    elif status_type == MidiStatus.PITCH_BEND:
        value = ((data2 << 7) | data1) - 8192
        return PitchBendEvent(**base, value=value)

    elif status_type == MidiStatus.PROGRAM_CHANGE:
        return ProgramChangeEvent(**base, program=data1)

    elif status_type == MidiStatus.AFTERTOUCH:
        return AftertouchEvent(**base, note=data1, pressure=data2)

    return None


# ------------------------------------------------------------------
# MidiSequence — lista ordenada de eventos (conteúdo de um clip MIDI)
# ------------------------------------------------------------------

class MidiSequence:
    """
    Sequência de eventos MIDI ordenada por tempo.

    Representa o conteúdo de um Clip MIDI na Timeline.
    Suporta serialização para salvar no projeto.
    """

    def __init__(self) -> None:
        self._events: List[MidiEvent] = []

    # ------------------------------------------------------------------
    # Edição
    # ------------------------------------------------------------------

    def add(self, event: MidiEvent) -> None:
        """Adiciona e mantém a lista ordenada por time_sec."""
        self._events.append(event)
        self._events.sort(key=lambda e: e.time_sec)

    def remove(self, event: MidiEvent) -> bool:
        try:
            self._events.remove(event)
            return True
        except ValueError:
            return False

    def clear(self) -> None:
        self._events.clear()

    def add_note(
        self,
        note:      int,
        start:     float,
        duration:  float,
        velocity:  int   = 100,
        channel:   int   = 0,
        tick_on:   int   = 0,
        tick_off:  int   = 0,
    ) -> Tuple[NoteOnEvent, NoteOffEvent]:
        """
        Atalho conveniente: adiciona um par NoteOn + NoteOff.
        Retorna a tupla (on, off) para referência futura.
        """
        on  = NoteOnEvent( time_sec=start,          tick=tick_on,  channel=channel, note=note, velocity=velocity)
        off = NoteOffEvent(time_sec=start + duration, tick=tick_off, channel=channel, note=note)
        self.add(on)
        self.add(off)
        return on, off

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def get_events_in_range(self, start: float, end: float) -> List[MidiEvent]:
        """Retorna eventos no intervalo [start, end) em segundos."""
        return [e for e in self._events if start <= e.time_sec < end]

    def get_notes(self) -> List[Tuple[NoteOnEvent, Optional[NoteOffEvent]]]:
        """
        Retorna pares (NoteOn, NoteOff) para exibição no piano roll.
        NoteOff pode ser None se a nota não tiver fim explícito.
        """
        pairs: List[Tuple[NoteOnEvent, Optional[NoteOffEvent]]] = []
        pending: Dict[int, NoteOnEvent] = {}

        for event in self._events:
            if isinstance(event, NoteOnEvent) and not event.is_note_off:
                pending[event.note] = event
            elif isinstance(event, (NoteOffEvent,)) or (
                isinstance(event, NoteOnEvent) and event.is_note_off
            ):
                note_num = event.note
                if note_num in pending:
                    pairs.append((pending.pop(note_num), event))

        # Notas sem NoteOff correspondente
        for on in pending.values():
            pairs.append((on, None))

        return pairs

    @property
    def duration(self) -> float:
        """Duração total da sequência em segundos."""
        if not self._events:
            return 0.0
        return max(e.time_sec for e in self._events)

    @property
    def events(self) -> List[MidiEvent]:
        """Lista de eventos (somente leitura — use add/remove para editar)."""
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)

    # ------------------------------------------------------------------
    # Serialização
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {"events": [e.to_dict() for e in self._events]}

    def from_dict(self, data: Dict[str, Any]) -> None:
        self._events = []
        for ed in data.get("events", []):
            ev = event_from_dict(ed)
            if ev is not None:
                self._events.append(ev)

    def __repr__(self) -> str:
        return f"MidiSequence(events={len(self._events)}, duration={self.duration:.2f}s)"


# ------------------------------------------------------------------
# Compat: NoteEvent mantido para não quebrar código existente
# ------------------------------------------------------------------

@dataclass
class NoteEvent:
    """
    Alias de compatibilidade com a versão anterior.
    Prefira NoteOnEvent / NoteOffEvent para código novo.
    """
    on:       bool
    track:    int
    note:     int
    velocity: int = 100

    def to_midi_event(self, time_sec: float = 0.0) -> MidiEvent:
        if self.on:
            return NoteOnEvent(time_sec=time_sec, note=self.note, velocity=self.velocity)
        return NoteOffEvent(time_sec=time_sec, note=self.note)