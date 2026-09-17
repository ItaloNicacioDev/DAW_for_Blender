"""
vst3_host_step6_midi_input.py

PASSO 6 do host VST3 nativo (continuação do step1 -> step5).

O que faltava no passo 5: o `ProcessData.inputEvents` sempre ia NULL.
Ou seja, o plugin só fazia som quando o clique acontecia DENTRO da GUI
dele (teclado embutido). Aqui fechamos o buraco:

  1. Implementamos a `Event` (ivstevents.h) com layout EXATO -- inclusive
     a union, que precisa estar alinhada em 8 bytes por causa dos
     membros com ponteiro (kDataEvent/kChordEvent). Errar isso é crash
     na certa dentro do plugin.
  2. Implementamos uma `IEventList` DO LADO DO HOST (`HostEventList`),
     no mesmo padrão dos outros objetos COM mínimos dos passos
     anteriores (MemoryBStream, HostPlugFrame, HostComponentHandler):
     vtable montada na mão, callbacks guardados como atributos da
     instância pra não serem coletados pelo GC.
  3. Estendemos o `LiveAudioEngine` do passo 5 pra, a cada bloco:
       - publicar os eventos pendentes em `data.inputEvents`;
       - publicar mudanças de parâmetro pendentes em
         `data.inputParameterChanges` (usado pelo native_host quando
         a GUI está aberta e alguém mexe num knob pela UI do Blender);
       - LIMPAR a lista depois do process(), pra uma nota tocar uma
         vez só e não retriggar a cada 1024 amostras.
     A classe nova é instalada por cima de `step5.LiveAudioEngine`
     (monkeypatch consciente), então tudo que já chamava
     `step5.LiveAudioEngine(...)` ganha suporte a eventos de graça --
     é assim que o `native_host.py` usa.
  4. Lemos MIDI de verdade de um teclado físico via `winmm.dll`
     (midiInOpen/midiInStart com CALLBACK_FUNCTION), traduzindo
     Note On/Note Off/All Notes Off pra eventos VST3. Sem
     python-rtmidi, sem mido -- mesma regra de "zero dependência
     externa" do resto do host.

Quem usa isso em produção é o `native_host.py`:
    step6.HostEventList()          -> lista viva de eventos
    step6.Event() / step6.kIsLive  -> render offline (render_instrument)
    step6.kNoteOnEvent / kNoteOffEvent

USO (demo standalone):
    python vst3_host_step6_midi_input.py "C:\\Caminho\\Para\\O\\Plugin.vst3"
    python vst3_host_step6_midi_input.py "...Plugin.vst3" --midi-device 1
    python vst3_host_step6_midi_input.py "...Plugin.vst3" --demo

  --midi-device N : escolhe a entrada MIDI (default: a primeira que
                    existir; se não existir nenhuma, cai no --demo).
  --demo          : ignora MIDI e toca um arpejo automático, útil pra
                    testar num PC sem teclado plugado.
"""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vst3_host_step1_list_classes as step1  # noqa: E402
import vst3_host_step2_instantiate as step2  # noqa: E402
import vst3_host_step3_processor_controller as step3  # noqa: E402
import vst3_host_step4_open_gui as step4  # noqa: E402
import vst3_host_step5_process_audio as step5  # noqa: E402


# ═══════════════════════════════════════════════════════════════
#  Event (pluginterfaces/vst/ivstevents.h)
#
#  struct Event {
#      int32  busIndex;
#      int32  sampleOffset;
#      double ppqPosition;     // TQuarterNotes
#      uint16 flags;
#      uint16 type;
#      union { NoteOnEvent noteOn; NoteOffEvent noteOff; ... };
#  };
#
#  A union tem membros com ponteiro (DataEvent.bytes,
#  ChordEvent.text), então ela alinha em 8 bytes no x64 -- o que
#  empurra o início dela pro offset 24 (4+4+8+2+2 = 20, +4 de
#  padding). O ctypes faz essa conta sozinho DESDE QUE a union
#  realmente declare os membros com ponteiro. Por isso declaramos
#  DataEvent/ChordEvent/ScaleEvent aqui, mesmo sem usar: eles
#  existem só pra o sizeof/alinhamento bater com o do plugin.
# ═══════════════════════════════════════════════════════════════

# EventTypes
kNoteOnEvent = 0
kNoteOffEvent = 1
kDataEvent = 2
kPolyPressureEvent = 3
kNoteExpressionValueEvent = 4
kNoteExpressionTextEvent = 5
kChordEvent = 6
kScaleEvent = 7
kLegacyMIDICCOutEvent = 65535

# EventFlags
kIsLive = 1 << 0
kUserReserved1 = 1 << 14
kUserReserved2 = 1 << 15


class NoteOnEvent(ctypes.Structure):
    _fields_ = [
        ("channel", ctypes.c_int16),
        ("pitch", ctypes.c_int16),
        ("tuning", ctypes.c_float),
        ("velocity", ctypes.c_float),
        ("length", ctypes.c_int32),
        ("noteId", ctypes.c_int32),
    ]


class NoteOffEvent(ctypes.Structure):
    _fields_ = [
        ("channel", ctypes.c_int16),
        ("pitch", ctypes.c_int16),
        ("velocity", ctypes.c_float),
        ("noteId", ctypes.c_int32),
        ("tuning", ctypes.c_float),
    ]


class DataEvent(ctypes.Structure):
    _fields_ = [
        ("size", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("bytes", ctypes.POINTER(ctypes.c_uint8)),
    ]


class PolyPressureEvent(ctypes.Structure):
    _fields_ = [
        ("channel", ctypes.c_int16),
        ("pitch", ctypes.c_int16),
        ("pressure", ctypes.c_float),
        ("noteId", ctypes.c_int32),
    ]


class NoteExpressionValueEvent(ctypes.Structure):
    _fields_ = [
        ("typeId", ctypes.c_uint32),
        ("noteId", ctypes.c_int32),
        ("value", ctypes.c_double),
    ]


class NoteExpressionTextEvent(ctypes.Structure):
    _fields_ = [
        ("typeId", ctypes.c_uint32),
        ("noteId", ctypes.c_int32),
        ("textLen", ctypes.c_uint32),
        ("text", ctypes.c_wchar_p),
    ]


class ChordEvent(ctypes.Structure):
    _fields_ = [
        ("root", ctypes.c_int16),
        ("bassNote", ctypes.c_int16),
        ("mask", ctypes.c_int16),
        ("textLen", ctypes.c_uint16),
        ("text", ctypes.c_wchar_p),
    ]


class ScaleEvent(ctypes.Structure):
    _fields_ = [
        ("root", ctypes.c_int16),
        ("mask", ctypes.c_int16),
        ("textLen", ctypes.c_uint16),
        ("text", ctypes.c_wchar_p),
    ]


class LegacyMIDICCOutEvent(ctypes.Structure):
    _fields_ = [
        ("controlNumber", ctypes.c_uint8),
        ("channel", ctypes.c_int8),
        ("value", ctypes.c_int8),
        ("value2", ctypes.c_int8),
    ]


class EventUnion(ctypes.Union):
    _fields_ = [
        ("noteOn", NoteOnEvent),
        ("noteOff", NoteOffEvent),
        ("data", DataEvent),
        ("polyPressure", PolyPressureEvent),
        ("noteExpressionValue", NoteExpressionValueEvent),
        ("noteExpressionText", NoteExpressionTextEvent),
        ("chord", ChordEvent),
        ("scale", ScaleEvent),
        ("midiCCOut", LegacyMIDICCOutEvent),
    ]


class Event(ctypes.Structure):
    _fields_ = [
        ("busIndex", ctypes.c_int32),
        ("sampleOffset", ctypes.c_int32),
        ("ppqPosition", ctypes.c_double),
        ("flags", ctypes.c_uint16),
        ("type", ctypes.c_uint16),
        ("event", EventUnion),
    ]


def make_note_on(pitch: int, velocity: float, channel: int = 0,
                 sample_offset: int = 0, note_id: int = -1, bus_index: int = 0) -> Event:
    """Atalho pra montar um Note On já com os campos que plugin
    nenhum gosta de ver com lixo dentro (tuning/length/noteId)."""
    e = Event()
    e.busIndex = bus_index
    e.sampleOffset = int(sample_offset)
    e.ppqPosition = 0.0
    e.flags = kIsLive
    e.type = kNoteOnEvent
    e.event.noteOn.channel = int(channel)
    e.event.noteOn.pitch = int(pitch)
    e.event.noteOn.tuning = 0.0
    e.event.noteOn.velocity = float(velocity)
    e.event.noteOn.length = 0
    e.event.noteOn.noteId = int(note_id) if note_id >= 0 else int(pitch)
    return e


def make_note_off(pitch: int, velocity: float = 0.0, channel: int = 0,
                  sample_offset: int = 0, note_id: int = -1, bus_index: int = 0) -> Event:
    e = Event()
    e.busIndex = bus_index
    e.sampleOffset = int(sample_offset)
    e.ppqPosition = 0.0
    e.flags = kIsLive
    e.type = kNoteOffEvent
    e.event.noteOff.channel = int(channel)
    e.event.noteOff.pitch = int(pitch)
    e.event.noteOff.velocity = float(velocity)
    e.event.noteOff.noteId = int(note_id) if note_id >= 0 else int(pitch)
    e.event.noteOff.tuning = 0.0
    return e


# ═══════════════════════════════════════════════════════════════
#  IEventList (ivstevents.h) -- implementada PELO HOST. O plugin
#  recebe isso em ProcessData.inputEvents e chama getEventCount()/
#  getEvent() de dentro do process(), na thread de áudio.
# ═══════════════════════════════════════════════════════════════

# DECLARE_CLASS_IID (IEventList, 0x3A2C4214, 0x346349FE, 0xB2C4F397, 0xB9695A44)
IID_IEventList = step1._uid_from_four_u32(0x3A2C4214, 0x346349FE, 0xB2C4F397, 0xB9695A44)

GetEventCountFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p)
GetEventFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(Event))
AddEventFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(Event))


class IEventListVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("getEventCount", GetEventCountFunc),
        ("getEvent", GetEventFunc),
        ("addEvent", AddEventFunc),
    ]


class IEventListObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IEventListVtbl))]


MAX_EVENTS_PER_BLOCK = 512


class HostEventList:
    """IEventList em memória.

    Dois compartimentos de propósito:
      - `_events`: o que o plugin ENXERGA no bloco atual. Quem
        preenche é quem monta o ProcessData (render offline no
        native_host escreve direto aqui, dentro do `with _lock`).
      - `_pending`: fila de quem empurra nota de OUTRA thread
        (teclado MIDI, GUI do Blender, trigger_live_note). O motor
        de áudio chama `flush_pending()` antes do process() e
        `clear()` depois -- assim a nota dispara exatamente uma vez.

    `_lock` é RLock de propósito: o plugin chama getEventCount/
    getEvent de dentro do process(), e process() pode estar sendo
    chamado pela mesma thread que acabou de mexer na lista.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._events: list[Event] = []
        self._pending: list[Event] = []

        self._qi = step1.QueryInterfaceFunc(self._query_interface)
        self._ar = step1.AddRefFunc(self._add_ref)
        self._rel = step1.ReleaseFunc(self._release)
        self._get_count = GetEventCountFunc(self._get_event_count)
        self._get_event = GetEventFunc(self._get_event_impl)
        self._add_event = AddEventFunc(self._add_event_impl)

        self._vtbl = IEventListVtbl(
            self._qi, self._ar, self._rel,
            self._get_count, self._get_event, self._add_event,
        )
        self._obj = IEventListObj(ctypes.pointer(self._vtbl))
        self.ptr = ctypes.cast(ctypes.pointer(self._obj), ctypes.c_void_p)

    # ---- FUnknown ------------------------------------------------

    def _query_interface(self, this, iid_ptr, obj_ptr_ptr):
        out = ctypes.cast(obj_ptr_ptr, ctypes.POINTER(ctypes.c_void_p))
        requested = bytes(iid_ptr.contents)
        if requested in (bytes(IID_IEventList), bytes(step1.IID_FUnknown)):
            out[0] = this
            return step1.kResultOk
        out[0] = None
        return step1.kNoInterface

    def _add_ref(self, this):
        # Tempo de vida é do Python (o objeto vive enquanto o
        # HostEventList existir) -- mesmo esquema dos outros objetos
        # de host dos passos anteriores.
        return 1

    def _release(self, this):
        return 1

    # ---- IEventList ---------------------------------------------

    def _get_event_count(self, this):
        with self._lock:
            return len(self._events)

    def _get_event_impl(self, this, index, event_ptr):
        with self._lock:
            if index < 0 or index >= len(self._events) or not event_ptr:
                return step1.kNoInterface  # kInvalidArgument no SDK; qualquer != ok serve
            ctypes.memmove(event_ptr, ctypes.byref(self._events[index]), ctypes.sizeof(Event))
        return step1.kResultOk

    def _add_event_impl(self, this, event_ptr):
        if not event_ptr:
            return step1.kNoInterface
        copy = Event()
        ctypes.memmove(ctypes.byref(copy), event_ptr, ctypes.sizeof(Event))
        with self._lock:
            if len(self._events) >= MAX_EVENTS_PER_BLOCK:
                return step1.kNoInterface
            self._events.append(copy)
        return step1.kResultOk

    # ---- API do host --------------------------------------------

    def clear(self):
        with self._lock:
            self._events.clear()

    def push_event(self, event: Event):
        """Enfileira pro PRÓXIMO bloco (thread-safe, chamável de
        qualquer thread: MIDI, UI, timer)."""
        with self._lock:
            if len(self._pending) >= MAX_EVENTS_PER_BLOCK:
                # Fila estourou (ex: motor de áudio parado). Descarta o
                # mais antigo em vez de crescer sem limite.
                self._pending.pop(0)
            self._pending.append(event)

    def push_note_on(self, channel: int, pitch: int, velocity: float, sample_offset: int = 0):
        self.push_event(make_note_on(pitch, velocity, channel, sample_offset))

    def push_note_off(self, channel: int, pitch: int, velocity: float = 0.0, sample_offset: int = 0):
        self.push_event(make_note_off(pitch, velocity, channel, sample_offset))

    def push_all_notes_off(self, channel: int = 0):
        for pitch in range(128):
            self.push_event(make_note_off(pitch, 0.0, channel))

    def flush_pending(self) -> int:
        """Move a fila pendente pra lista visível do bloco atual.
        Devolve quantos eventos entraram."""
        with self._lock:
            if not self._pending:
                return 0
            room = MAX_EVENTS_PER_BLOCK - len(self._events)
            if room <= 0:
                return 0
            moving = self._pending[:room]
            del self._pending[:len(moving)]
            self._events.extend(moving)
            return len(moving)

    def has_events(self) -> bool:
        with self._lock:
            return bool(self._events or self._pending)


# ═══════════════════════════════════════════════════════════════
#  LiveAudioEngine com eventos -- o motor do passo 5 só que agora
#  publicando inputEvents e inputParameterChanges a cada bloco.
#
#  Herda de step5.LiveAudioEngine (mesmos buffers, mesmo winmm,
#  mesmo double buffering) e sobrescreve só o _run(), que é onde a
#  diferença mora.
# ═══════════════════════════════════════════════════════════════

class LiveAudioEngineWithEvents(step5.LiveAudioEngine):

    def __init__(self, ap_vtbl, ap_self, out_channels: int, input_event_list: "HostEventList | None" = None):
        super().__init__(ap_vtbl, ap_self, out_channels)
        self.input_event_list = input_event_list
        # Lido a cada bloco e zerado depois -- quem escreve aqui é o
        # native_host quando alguém mexe num parâmetro com a GUI aberta.
        self.pending_input_param_changes = None
        if input_event_list is not None:
            self._data.inputEvents = input_event_list.ptr
        else:
            self._data.inputEvents = None

    def _run(self):
        bytes_per_block = self.BLOCK_SIZE * self.out_channels * 2  # 16-bit
        headers = []
        int_bufs = []
        for _ in range(self.NUM_BUFFERS):
            buf = (ctypes.c_int16 * (self.BLOCK_SIZE * self.out_channels))()
            hdr = step5.WAVEHDR()
            hdr.lpData = ctypes.cast(buf, ctypes.c_void_p)
            hdr.dwBufferLength = bytes_per_block
            hdr.dwFlags = 0
            step5.winmm.waveOutPrepareHeader(self._hwo, ctypes.byref(hdr), ctypes.sizeof(step5.WAVEHDR))
            headers.append(hdr)
            int_bufs.append(buf)

        first_use = [True] * self.NUM_BUFFERS
        idx = 0
        project_samples = 0

        while not self._stop.is_set():
            hdr = headers[idx]
            buf = int_bufs[idx]

            if not first_use[idx]:
                while not (hdr.dwFlags & step5.WHDR_DONE) and not self._stop.is_set():
                    time.sleep(0.001)
            first_use[idx] = False

            if self._stop.is_set():
                break

            # ─── NOVO: eventos pendentes viram inputEvents do bloco ──
            evt_list = self.input_event_list
            if evt_list is not None:
                evt_list.flush_pending()
                self._data.inputEvents = evt_list.ptr
            else:
                self._data.inputEvents = None

            # ─── NOVO: parâmetros pendentes (knob mexido na UI) ──────
            pc = self.pending_input_param_changes
            self._data.inputParameterChanges = pc.ptr if pc is not None else None

            # Transporte andando de verdade -- alguns plugins usam
            # projectTimeSamples pra LFO sincronizado/delay.
            self._ctx.projectTimeSamples = project_samples
            self._ctx.continousTimeSamples = project_samples
            self._ctx.projectTimeMusic = (project_samples / float(self.SAMPLE_RATE)) * (self._ctx.tempo / 60.0)

            hr = self.ap_vtbl.process(self.ap_self, ctypes.byref(self._data))

            # Consumidos: nota dispara uma vez, não a cada bloco.
            if evt_list is not None:
                evt_list.clear()
            if pc is not None and pc is self.pending_input_param_changes:
                self.pending_input_param_changes = None

            if hr != step1.kResultOk:
                for arr in self._chan_arrays:
                    ctypes.memset(arr, 0, ctypes.sizeof(arr))

            for i in range(self.BLOCK_SIZE):
                base = i * self.out_channels
                for ch, arr in enumerate(self._chan_arrays):
                    v = arr[i]
                    if v > 1.0:
                        v = 1.0
                    elif v < -1.0:
                        v = -1.0
                    buf[base + ch] = int(v * 32767.0)

            step5.winmm.waveOutWrite(self._hwo, ctypes.byref(hdr), ctypes.sizeof(step5.WAVEHDR))
            project_samples += self.BLOCK_SIZE
            idx = (idx + 1) % self.NUM_BUFFERS

        for hdr in headers:
            step5.winmm.waveOutUnprepareHeader(self._hwo, ctypes.byref(hdr), ctypes.sizeof(step5.WAVEHDR))


# Instala por cima do motor do passo 5: a partir do momento que
# alguém importa o passo 6, `step5.LiveAudioEngine(...)` já aceita
# `input_event_list=` e respeita `pending_input_param_changes`.
# É de propósito -- assim o native_host.py não precisa saber de qual
# passo veio cada pedaço, e o passo 5 continua rodando sozinho pra
# quem for ler o tutorial na ordem.
step5.LiveAudioEngine = LiveAudioEngineWithEvents
LiveAudioEngine = LiveAudioEngineWithEvents


# ═══════════════════════════════════════════════════════════════
#  Entrada MIDI de verdade via winmm.dll (midiIn*) -- mesma DLL que
#  o passo 5 já usa pra saída de áudio (waveOut*). Sem rtmidi/mido.
# ═══════════════════════════════════════════════════════════════

winmm = step5.winmm

MIM_OPEN = 0x3C1
MIM_CLOSE = 0x3C2
MIM_DATA = 0x3C3
MIM_LONGDATA = 0x3C4
MIM_ERROR = 0x3C5

CALLBACK_FUNCTION = 0x00030000
MAXPNAMELEN = 32


class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.c_uint16),
        ("wPid", ctypes.c_uint16),
        ("vDriverVersion", ctypes.c_uint32),
        ("szPname", ctypes.c_wchar * MAXPNAMELEN),
        ("dwSupport", ctypes.c_uint32),
    ]


MidiInProc = ctypes.WINFUNCTYPE(
    None, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t
)

winmm.midiInGetNumDevs.restype = ctypes.c_uint32
winmm.midiInGetDevCapsW.argtypes = [ctypes.c_size_t, ctypes.POINTER(MIDIINCAPSW), ctypes.c_uint32]
winmm.midiInGetDevCapsW.restype = ctypes.c_uint32
winmm.midiInOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
winmm.midiInOpen.restype = ctypes.c_uint32
winmm.midiInStart.argtypes = [ctypes.c_void_p]
winmm.midiInStart.restype = ctypes.c_uint32
winmm.midiInStop.argtypes = [ctypes.c_void_p]
winmm.midiInStop.restype = ctypes.c_uint32
winmm.midiInReset.argtypes = [ctypes.c_void_p]
winmm.midiInReset.restype = ctypes.c_uint32
winmm.midiInClose.argtypes = [ctypes.c_void_p]
winmm.midiInClose.restype = ctypes.c_uint32


def list_midi_inputs() -> list[str]:
    names = []
    for i in range(winmm.midiInGetNumDevs()):
        caps = MIDIINCAPSW()
        if winmm.midiInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
            names.append(caps.szPname)
        else:
            names.append(f"<dispositivo {i} não respondeu>")
    return names


class MidiInputDevice:
    """Teclado MIDI físico -> HostEventList.

    A callback do winmm roda numa thread do driver de áudio do
    Windows, NÃO na nossa. Por isso ela faz o mínimo possível:
    traduz o status byte e empurra o evento na fila (que é
    protegida por lock). Quem realmente entrega pro plugin é o
    motor de áudio, no próximo bloco.
    """

    def __init__(self, event_list: HostEventList, device_index: int = 0, channel_filter: int | None = None):
        self.event_list = event_list
        self.device_index = device_index
        self.channel_filter = channel_filter
        self._handle = ctypes.c_void_p()
        self._proc = MidiInProc(self._callback)  # manter vivo!
        self._open = False
        self.name = "<desconhecido>"

    def open(self) -> bool:
        n = winmm.midiInGetNumDevs()
        if n == 0:
            print("Nenhuma entrada MIDI encontrada no Windows.")
            return False
        if self.device_index >= n:
            print(f"Dispositivo MIDI {self.device_index} não existe (só tem {n}).")
            return False

        caps = MIDIINCAPSW()
        if winmm.midiInGetDevCapsW(self.device_index, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
            self.name = caps.szPname

        res = winmm.midiInOpen(
            ctypes.byref(self._handle), self.device_index,
            ctypes.cast(self._proc, ctypes.c_void_p), 0, CALLBACK_FUNCTION,
        )
        if res != 0:
            print(f"midiInOpen() falhou (mmresult={res}) -- outro programa pode estar segurando o teclado.")
            return False

        res = winmm.midiInStart(self._handle)
        if res != 0:
            winmm.midiInClose(self._handle)
            print(f"midiInStart() falhou (mmresult={res}).")
            return False

        self._open = True
        print(f"Entrada MIDI aberta: [{self.device_index}] {self.name}")
        return True

    def close(self):
        if not self._open:
            return
        winmm.midiInStop(self._handle)
        winmm.midiInReset(self._handle)
        winmm.midiInClose(self._handle)
        self._open = False
        self.event_list.push_all_notes_off()
        print("Entrada MIDI fechada.")

    def _callback(self, handle, msg, instance, param1, param2):
        if msg != MIM_DATA:
            return
        # param1 = mensagem MIDI empacotada: status | data1<<8 | data2<<16
        status = param1 & 0xFF
        data1 = (param1 >> 8) & 0x7F
        data2 = (param1 >> 16) & 0x7F
        command = status & 0xF0
        channel = status & 0x0F

        if self.channel_filter is not None and channel != self.channel_filter:
            return

        try:
            if command == 0x90 and data2 > 0:          # Note On
                self.event_list.push_note_on(channel, data1, data2 / 127.0)
            elif command == 0x80 or (command == 0x90 and data2 == 0):
                # Note Off (ou Note On com velocity 0, que é a forma
                # que MUITO teclado usa pra soltar a tecla)
                self.event_list.push_note_off(channel, data1, data2 / 127.0)
            elif command == 0xB0 and data1 == 123:     # All Notes Off
                self.event_list.push_all_notes_off(channel)
        except Exception:
            # Nunca deixar exceção vazar pra dentro do driver do
            # Windows -- isso derruba o processo inteiro.
            pass


def start_demo_arpeggio(event_list: HostEventList, stop_event: threading.Event,
                        notes=(60, 64, 67, 72), step_time: float = 0.35) -> threading.Thread:
    """Plano B pra quem não tem teclado plugado: fica tocando um
    arpejo pra provar que o caminho inputEvents -> plugin funciona."""

    def _run():
        i = 0
        while not stop_event.is_set():
            pitch = notes[i % len(notes)]
            event_list.push_note_on(0, pitch, 100 / 127.0)
            if stop_event.wait(step_time * 0.9):
                event_list.push_note_off(0, pitch)
                break
            event_list.push_note_off(0, pitch)
            stop_event.wait(step_time * 0.1)
            i += 1

    t = threading.Thread(target=_run, name="demo-arpeggio", daemon=True)
    t.start()
    return t


# ═══════════════════════════════════════════════════════════════
#  Demo standalone -- mesmo fluxo do passo 5 (GUI + áudio ao vivo),
#  agora com a IEventList plugada e uma fonte de notas de fora.
# ═══════════════════════════════════════════════════════════════

def _main_body(vst3_path: str, midi_device: int | None = 0, force_demo: bool = False):
    dll, factory = step1.load_vst3_factory(vst3_path)
    classes = step1.list_classes(factory)
    audio_class = step2.find_audio_module_class(classes)
    print(f"Usando classe: nome={audio_class['name']!r} cid={audio_class['cid']}")

    component_ptr = step2.create_component(factory, audio_class["cid"])
    component_vtbl = component_ptr.contents.lpVtbl.contents
    component_self = ctypes.cast(component_ptr, ctypes.c_void_p)

    host_context = step4.HostApplicationContext()
    hr = component_vtbl.initialize(component_self, host_context.ptr)
    if hr != step1.kResultOk:
        raise RuntimeError(f"initialize() do componente falhou (hr={hr:#x})")
    print("Componente inicializado.")

    ctrl_vtbl, ctrl_self, ctrl_is_separate = step3.get_or_create_controller(
        factory, component_vtbl, component_self, host_context
    )

    def teardown_component_only():
        component_vtbl.terminate(component_self)
        component_vtbl.release(component_self)
        step1.unload_vst3_module(dll)

    if ctrl_vtbl is None:
        print("Esse plugin não expõe IEditController -- sem GUI pra abrir.")
        teardown_component_only()
        return

    ctrl_full_ptr = ctypes.cast(ctrl_self, ctypes.POINTER(step4.IEditControllerObjFull))
    ctrl_full_vtbl = ctrl_full_ptr.contents.lpVtbl.contents
    component_full_ptr = ctypes.cast(component_self, ctypes.POINTER(step5.IComponentObjFull2))
    component_full_vtbl = component_full_ptr.contents.lpVtbl.contents

    connected = False
    comp_cp_vtbl = comp_cp_self = ctrl_cp_vtbl = ctrl_cp_self = None
    if ctrl_is_separate:
        print("\nConectando IComponent <-> IEditController...")
        comp_cp_obj = ctypes.c_void_p()
        hr_comp_cp = component_vtbl.queryInterface(component_self, ctypes.byref(step4.IID_IConnectionPoint), ctypes.byref(comp_cp_obj))
        ctrl_cp_obj = ctypes.c_void_p()
        hr_ctrl_cp = ctrl_vtbl.queryInterface(ctrl_self, ctypes.byref(step4.IID_IConnectionPoint), ctypes.byref(ctrl_cp_obj))

        if hr_comp_cp == step1.kResultOk and hr_ctrl_cp == step1.kResultOk:
            comp_cp_ptr = ctypes.cast(comp_cp_obj, ctypes.POINTER(step4.IConnectionPointObj))
            comp_cp_vtbl = comp_cp_ptr.contents.lpVtbl.contents
            comp_cp_self = ctypes.cast(comp_cp_ptr, ctypes.c_void_p)

            ctrl_cp_ptr = ctypes.cast(ctrl_cp_obj, ctypes.POINTER(step4.IConnectionPointObj))
            ctrl_cp_vtbl = ctrl_cp_ptr.contents.lpVtbl.contents
            ctrl_cp_self = ctypes.cast(ctrl_cp_ptr, ctypes.c_void_p)

            hr1 = comp_cp_vtbl.connect(comp_cp_self, ctrl_cp_self)
            hr2 = ctrl_cp_vtbl.connect(ctrl_cp_self, comp_cp_self)
            print(f"  connect() -> componente={hr1:#x} controller={hr2:#x}")
            connected = hr1 == step1.kResultOk and hr2 == step1.kResultOk
        else:
            print("  Esse plugin não suporta IConnectionPoint -- pulando.")

        print("Sincronizando estado (component.getState -> controller.setComponentState)...")
        state_stream = step4.MemoryBStream()
        hr_get = component_full_vtbl.getState(component_self, state_stream.ptr)
        if hr_get == step1.kResultOk:
            state_stream.rewind()
            hr_set = ctrl_full_vtbl.setComponentState(ctrl_self, state_stream.ptr)
            print(f"  getState() -> hr={hr_get:#x}, setComponentState() -> hr={hr_set:#x}")

    print("\nsetComponentHandler()...")
    handler = step4.HostComponentHandler()
    hr_handler = ctrl_full_vtbl.setComponentHandler(ctrl_self, handler.ptr)
    print(f"  setComponentHandler() -> hr={hr_handler:#x}")

    print("\nqueryInterface(IAudioProcessor)...")
    ap_obj = ctypes.c_void_p()
    hr_ap = component_vtbl.queryInterface(component_self, ctypes.byref(step3.IID_IAudioProcessor), ctypes.byref(ap_obj))
    if hr_ap != step1.kResultOk or not ap_obj:
        print(f"  Esse plugin não implementa IAudioProcessor (hr={hr_ap:#x}).")
        ap_vtbl = ap_self = None
    else:
        ap_ptr = ctypes.cast(ap_obj, ctypes.POINTER(step5.IAudioProcessorObjFull))
        ap_vtbl = ap_ptr.contents.lpVtbl.contents
        ap_self = ctypes.cast(ap_ptr, ctypes.c_void_p)
        print("  queryInterface(IAudioProcessor) OK.")

    engine = None
    event_list = None
    midi_in = None
    demo_stop = threading.Event()

    if ap_vtbl is not None:
        out_channels = 2
        n_out_buses = component_vtbl.getBusCount(component_self, step2.kAudio, step2.kOutput)
        if n_out_buses > 0:
            info = step2.BusInfo()
            if component_vtbl.getBusInfo(component_self, step2.kAudio, step2.kOutput, 0, ctypes.byref(info)) == step1.kResultOk:
                out_channels = info.channelCount or 2
        print(f"Bus de saída principal: {out_channels} canal(is).")

        setup = step5.ProcessSetup(
            processMode=step5.kRealtime,
            symbolicSampleSize=step5.kSample32,
            maxSamplesPerBlock=LiveAudioEngineWithEvents.BLOCK_SIZE,
            sampleRate=float(LiveAudioEngineWithEvents.SAMPLE_RATE),
        )
        hr = ap_vtbl.setupProcessing(ap_self, ctypes.byref(setup))
        print(f"setupProcessing() -> hr={hr:#x}")

        if n_out_buses > 0:
            hr = component_full_vtbl.activateBus(component_self, step2.kAudio, step2.kOutput, 0, 1)
            print(f"activateBus(Audio, Output, 0) -> hr={hr:#x}")

        n_evt_in_buses = component_vtbl.getBusCount(component_self, step2.kEvent, step2.kInput)
        has_event_in = n_evt_in_buses > 0
        if has_event_in:
            hr = component_full_vtbl.activateBus(component_self, step2.kEvent, step2.kInput, 0, 1)
            print(f"activateBus(Event, Input, 0) -> hr={hr:#x}")
        else:
            print("Esse plugin NÃO tem bus de evento de entrada (provavelmente é um efeito, não um instrumento).")

        hr = component_full_vtbl.setActive(component_self, 1)
        print(f"setActive(true) -> hr={hr:#x}")
        hr = ap_vtbl.setProcessing(ap_self, 1)
        print(f"setProcessing(true) -> hr={hr:#x}")

        event_list = HostEventList() if has_event_in else None
        engine = LiveAudioEngineWithEvents(ap_vtbl, ap_self, out_channels, input_event_list=event_list)
        engine.start()

        if event_list is not None:
            devices = list_midi_inputs()
            print("\nEntradas MIDI disponíveis:")
            if devices:
                for i, nm in enumerate(devices):
                    print(f"  [{i}] {nm}")
            else:
                print("  (nenhuma)")

            if not force_demo and devices and midi_device is not None:
                midi_in = MidiInputDevice(event_list, device_index=midi_device)
                if not midi_in.open():
                    midi_in = None

            if midi_in is None:
                print("Sem teclado MIDI -- ligando o arpejo de demonstração.")
                start_demo_arpeggio(event_list, demo_stop)

    # ─── GUI (igual passo 4/5) ────────────────────────────────────

    view_ptr_raw = ctrl_full_vtbl.createView(ctrl_self, step4.kEditor)
    if not view_ptr_raw:
        print("createView('editor') devolveu NULL -- esse plugin não tem editor gráfico.")
        demo_stop.set()
        if midi_in:
            midi_in.close()
        if engine:
            engine.stop()
        if ctrl_is_separate:
            ctrl_vtbl.terminate(ctrl_self)
        ctrl_vtbl.release(ctrl_self)
        teardown_component_only()
        return

    view_ptr = ctypes.cast(view_ptr_raw, ctypes.POINTER(step4.IPlugViewObj))
    view_vtbl = view_ptr.contents.lpVtbl.contents
    view_self = ctypes.cast(view_ptr, ctypes.c_void_p)

    if view_vtbl.isPlatformTypeSupported(view_self, step4.kPlatformTypeHWND) != step1.kResultOk:
        raise RuntimeError("Esse plugin não suporta HWND nessa build.")

    size = step4.ViewRect()
    view_vtbl.getSize(view_self, ctypes.byref(size))
    w, h = size.right - size.left, size.bottom - size.top

    hwnd, wndproc_keepalive = step4.create_host_window(w, h, audio_class["name"] + " (MIDI ao vivo)")
    step4.resize_host_window(hwnd, w, h)

    frame = step4.HostPlugFrame(hwnd)
    view_vtbl.setFrame(view_self, frame.ptr)

    hr = view_vtbl.attached(view_self, ctypes.c_void_p(hwnd), step4.kPlatformTypeHWND)
    print(f"attached() -> hr={hr:#x}")
    if hr != step1.kResultOk:
        demo_stop.set()
        if midi_in:
            midi_in.close()
        if engine:
            engine.stop()
        raise RuntimeError(f"attached() falhou (hr={hr:#x})")

    frame.view_vtbl = view_vtbl
    frame.view_self = view_self

    step4.user32.ShowWindow(hwnd, step4.SW_SHOWNORMAL)
    step4.user32.UpdateWindow(hwnd)

    print("\nJanela aberta. Toca no teclado MIDI (ou escuta o arpejo) -- as notas")
    print("agora vão pelo ProcessData.inputEvents, não pelo teclado da GUI.")
    print("Feche a janela do plugin pra parar tudo.")
    step4.run_message_loop()

    print("\nJanela fechada, desfazendo tudo...")
    demo_stop.set()
    if midi_in:
        midi_in.close()

    view_vtbl.removed(view_self)
    view_vtbl.release(view_self)

    if engine:
        hr = ap_vtbl.setProcessing(ap_self, 0)
        print(f"setProcessing(false) -> hr={hr:#x}")
        engine.stop()
        hr = component_full_vtbl.setActive(component_self, 0)
        print(f"setActive(false) -> hr={hr:#x}")

    if connected:
        comp_cp_vtbl.disconnect(comp_cp_self, ctrl_cp_self)
        ctrl_cp_vtbl.disconnect(ctrl_cp_self, comp_cp_self)
        comp_cp_vtbl.release(comp_cp_self)
        ctrl_cp_vtbl.release(ctrl_cp_self)

    if ctrl_is_separate:
        ctrl_vtbl.terminate(ctrl_self)
    ctrl_vtbl.release(ctrl_self)

    teardown_component_only()
    print("Passo 6 concluído sem crash.")


def main():
    args = sys.argv[1:]
    if not args:
        print('Uso: python vst3_host_step6_midi_input.py "C:\\caminho\\pro\\Plugin.vst3" [--midi-device N] [--demo]')
        print("\nEntradas MIDI vistas agora:")
        for i, nm in enumerate(list_midi_inputs()):
            print(f"  [{i}] {nm}")
        sys.exit(1)

    vst3_path = args[0]
    midi_device = 0
    force_demo = False
    if "--demo" in args:
        force_demo = True
    if "--midi-device" in args:
        try:
            midi_device = int(args[args.index("--midi-device") + 1])
        except (IndexError, ValueError):
            print("--midi-device precisa de um número (ex: --midi-device 1).")
            sys.exit(1)

    print(f"Carregando: {vst3_path}")
    _main_body(vst3_path, midi_device=midi_device, force_demo=force_demo)


if __name__ == "__main__":
    main()