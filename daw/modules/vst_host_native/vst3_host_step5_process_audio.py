"""
vst3_host_step5_process_audio.py

PASSO 5 do host VST3 nativo (continuação do step1 + step2 + step3 + step4).

O que esse script faz, e SÓ isso:
  1. Reusa o passo 4 inteiro (import vst3_host_step4_open_gui as step4)
     pra abrir a GUI do plugin exatamente como antes -- componente,
     controller, handshake, janela Win32, tudo igual.
  2. ANTES de mostrar a janela, monta o lado de processamento de
     áudio de verdade:
       - IAudioProcessor.setupProcessing(ProcessSetup) -- avisa o
         plugin qual sample rate/tamanho de bloco vamos usar.
       - IComponent.activateBus(...) no bus de áudio de saída
         principal (buses começam INATIVOS por spec).
       - IComponent.setActive(true).
       - IAudioProcessor.setProcessing(true).
  3. Sobe uma thread separada que fica chamando process() num loop
     contínuo (como a "callback de áudio" de qualquer host de
     verdade) e manda o resultado pra saída de áudio via winmm.dll
     (waveOutOpen/waveOutWrite) -- API crua do Windows, sem
     sounddevice/pyaudio/JUCE, mesmo espírito do resto do host.
  4. Mostra a janela do plugin e roda o message loop (igual ao passo
     4). Como a thread de áudio já está rodando, clicar no teclado
     embutido da GUI do plugin agora produz som de verdade -- o
     clique é tratado inteiramente DENTRO do plugin (não precisamos
     mandar um Event de Note On pra isso), a única peça que faltava
     era ter alguém chamando process() em loop e tocando o resultado.
  5. Ao fechar a janela: para a thread de áudio, setProcessing(false),
     setActive(false), depois desfaz tudo igual ao passo 4.

O que esse script NÃO faz ainda:
  - Não manda eventos de MIDI/Note On pra fora (ex: de um teclado
    MIDI de verdade plugado no PC) -- só deixa o teclado embutido DO
    PLUGIN funcionar. Mandar eventos externos é o próximo passo
    natural (IEventList preenchida de verdade com NoteOnEvent).
  - processContext é preenchido com valores fixos (120 BPM, 4/4,
    "tocando") -- não sincroniza com nenhum transporte real ainda.

USO:
    python vst3_host_step5_process_audio.py "C:\\Caminho\\Para\\O\\Plugin.vst3"
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


# ═══════════════════════════════════════════════════════════════
#  Structs do SDK pra processamento de áudio (layout EXATO --
#  ctypes já respeita o alinhamento natural de 8 bytes pra
#  double/int64/ponteiro, igual o MSVC, então não precisamos de
#  padding manual).
# ═══════════════════════════════════════════════════════════════

kRealtime = 0            # ProcessModes::kRealtime
kSample32 = 0             # SymbolicSampleSizes::kSample32
kPlayingFlag = 1 << 1     # ProcessContext::StatesAndFlags::kPlaying


class ProcessSetup(ctypes.Structure):
    _fields_ = [
        ("processMode", ctypes.c_int32),
        ("symbolicSampleSize", ctypes.c_int32),
        ("maxSamplesPerBlock", ctypes.c_int32),
        ("sampleRate", ctypes.c_double),
    ]


class AudioBusBuffers(ctypes.Structure):
    _fields_ = [
        ("numChannels", ctypes.c_int32),
        ("silenceFlags", ctypes.c_uint64),
        ("channelBuffers32", ctypes.POINTER(ctypes.POINTER(ctypes.c_float))),
    ]


class Chord(ctypes.Structure):
    _fields_ = [
        ("keyNote", ctypes.c_uint8),
        ("rootNote", ctypes.c_uint8),
        ("chordMask", ctypes.c_int16),
    ]


class FrameRate(ctypes.Structure):
    _fields_ = [
        ("framesPerSecond", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
    ]


class ProcessContext(ctypes.Structure):
    """ivstprocesscontext.h -- preenchemos só o suficiente pra ser um
    contexto VÁLIDO (não NULL). Vários plugins leem daqui sem checar
    -- passar NULL é uma causa comum de crash em hosts minimalistas,
    igual vimos no Serum 2 com outras estruturas."""
    _fields_ = [
        ("state", ctypes.c_uint32),
        ("sampleRate", ctypes.c_double),
        ("projectTimeSamples", ctypes.c_int64),
        ("systemTime", ctypes.c_int64),
        ("continousTimeSamples", ctypes.c_int64),
        ("projectTimeMusic", ctypes.c_double),
        ("barPositionMusic", ctypes.c_double),
        ("cycleStartMusic", ctypes.c_double),
        ("cycleEndMusic", ctypes.c_double),
        ("tempo", ctypes.c_double),
        ("timeSigNumerator", ctypes.c_int32),
        ("timeSigDenominator", ctypes.c_int32),
        ("chord", Chord),
        ("smpteOffsetSubframes", ctypes.c_int32),
        ("frameRate", FrameRate),
        ("samplesToNextClock", ctypes.c_int32),
    ]


class ProcessData(ctypes.Structure):
    _fields_ = [
        ("processMode", ctypes.c_int32),
        ("symbolicSampleSize", ctypes.c_int32),
        ("numSamples", ctypes.c_int32),
        ("numInputs", ctypes.c_int32),
        ("numOutputs", ctypes.c_int32),
        ("inputs", ctypes.POINTER(AudioBusBuffers)),
        ("outputs", ctypes.POINTER(AudioBusBuffers)),
        ("inputParameterChanges", ctypes.c_void_p),
        ("outputParameterChanges", ctypes.c_void_p),
        ("inputEvents", ctypes.c_void_p),
        ("outputEvents", ctypes.c_void_p),
        ("processContext", ctypes.POINTER(ProcessContext)),
    ]


SetupProcessingFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(ProcessSetup))
SetProcessingFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint8)
ProcessFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(ProcessData))

# Reaproveita a vtable do passo 3 (mesmos 11 slots, mesma ordem), só
# trocando a assinatura dos 3 métodos que vamos chamar de verdade
# agora -- mesmo padrão usado no passo 4 pro IEditController/IComponent.
_ap_fields = list(step3.IAudioProcessorVtbl._fields_)
_ap_fields[7] = ("setupProcessing", SetupProcessingFunc)  # qi,ar,rel,setBusArrangements,getBusArrangement,canProcessSampleSize,getLatencySamples,setupProcessing,...
_ap_fields[8] = ("setProcessing", SetProcessingFunc)
_ap_fields[9] = ("process", ProcessFunc)


class IAudioProcessorVtblFull(ctypes.Structure):
    _fields_ = _ap_fields


class IAudioProcessorObjFull(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IAudioProcessorVtblFull))]


# activateBus também só tinha slot genérico até agora (passo 2 não
# precisava chamar). Reaproveita a IComponentVtblFull do passo 4
# (que já tem getState typado) e soma activateBus typado.
ActivateBusFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_uint8)
_component_fields = list(step4.IComponentVtblFull._fields_)
_component_fields[10] = ("activateBus", ActivateBusFunc)  # qi,ar,rel,init,term,getControllerClassId,setIoMode,getBusCount,getBusInfo,getRoutingInfo,activateBus,...


class IComponentVtblFull2(ctypes.Structure):
    _fields_ = _component_fields


class IComponentObjFull2(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IComponentVtblFull2))]


# ═══════════════════════════════════════════════════════════════
#  Saída de áudio via winmm.dll (waveOut*) -- API de áudio nativa
#  do Windows, existe desde sempre, sem instalar nada. Não é a API
#  mais moderna (WASAPI seria o "certo" hoje em dia), mas é a mais
#  simples de chamar via ctypes puro e já resolve o objetivo: ouvir
#  o plugin tocando.
# ═══════════════════════════════════════════════════════════════

winmm = ctypes.windll.winmm

WAVE_MAPPER = 0xFFFFFFFF
WAVE_FORMAT_PCM = 1
CALLBACK_NULL = 0x00000000
WHDR_DONE = 0x00000001


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", ctypes.c_uint16),
        ("nChannels", ctypes.c_uint16),
        ("nSamplesPerSec", ctypes.c_uint32),
        ("nAvgBytesPerSec", ctypes.c_uint32),
        ("nBlockAlign", ctypes.c_uint16),
        ("wBitsPerSample", ctypes.c_uint16),
        ("cbSize", ctypes.c_uint16),
    ]


class WAVEHDR(ctypes.Structure):
    pass


WAVEHDR._fields_ = [
    ("lpData", ctypes.c_void_p),
    ("dwBufferLength", ctypes.c_uint32),
    ("dwBytesRecorded", ctypes.c_uint32),
    ("dwUser", ctypes.c_size_t),
    ("dwFlags", ctypes.c_uint32),
    ("dwLoops", ctypes.c_uint32),
    ("lpNext", ctypes.POINTER(WAVEHDR)),
    ("reserved", ctypes.c_size_t),
]

winmm.waveOutOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint32, ctypes.POINTER(WAVEFORMATEX), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
winmm.waveOutOpen.restype = ctypes.c_uint32
winmm.waveOutPrepareHeader.argtypes = [ctypes.c_void_p, ctypes.POINTER(WAVEHDR), ctypes.c_uint32]
winmm.waveOutPrepareHeader.restype = ctypes.c_uint32
winmm.waveOutUnprepareHeader.argtypes = [ctypes.c_void_p, ctypes.POINTER(WAVEHDR), ctypes.c_uint32]
winmm.waveOutUnprepareHeader.restype = ctypes.c_uint32
winmm.waveOutWrite.argtypes = [ctypes.c_void_p, ctypes.POINTER(WAVEHDR), ctypes.c_uint32]
winmm.waveOutWrite.restype = ctypes.c_uint32
winmm.waveOutReset.argtypes = [ctypes.c_void_p]
winmm.waveOutReset.restype = ctypes.c_uint32
winmm.waveOutClose.argtypes = [ctypes.c_void_p]
winmm.waveOutClose.restype = ctypes.c_uint32


class LiveAudioEngine:
    """A "thread de áudio". Fica chamando process() no plugin e
    jogando o resultado pro winmm continuamente, até stop()."""

    SAMPLE_RATE = 44100
    BLOCK_SIZE = 1024
    NUM_BUFFERS = 4

    def __init__(self, ap_vtbl, ap_self, out_channels: int):
        self.ap_vtbl = ap_vtbl
        self.ap_self = ap_self
        self.out_channels = max(1, out_channels)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._hwo = ctypes.c_void_p()

        # Buffers float32 que o process() escreve (um array por canal).
        self._chan_arrays = [(ctypes.c_float * self.BLOCK_SIZE)() for _ in range(self.out_channels)]
        self._chan_ptrs = (ctypes.POINTER(ctypes.c_float) * self.out_channels)()
        for ch, arr in enumerate(self._chan_arrays):
            self._chan_ptrs[ch] = ctypes.cast(arr, ctypes.POINTER(ctypes.c_float))

        self._bus = AudioBusBuffers(numChannels=self.out_channels, silenceFlags=0, channelBuffers32=self._chan_ptrs)

        self._ctx = ProcessContext()
        self._ctx.state = kPlayingFlag
        self._ctx.sampleRate = float(self.SAMPLE_RATE)
        self._ctx.tempo = 120.0
        self._ctx.timeSigNumerator = 4
        self._ctx.timeSigDenominator = 4

        self._data = ProcessData()
        self._data.processMode = kRealtime
        self._data.symbolicSampleSize = kSample32
        self._data.numSamples = self.BLOCK_SIZE
        self._data.numInputs = 0
        self._data.numOutputs = 1
        self._data.inputs = None
        self._data.outputs = ctypes.pointer(self._bus)
        self._data.inputParameterChanges = None
        self._data.outputParameterChanges = None
        self._data.inputEvents = None
        self._data.outputEvents = None
        self._data.processContext = ctypes.pointer(self._ctx)

    def start(self):
        wfx = WAVEFORMATEX()
        wfx.wFormatTag = WAVE_FORMAT_PCM
        wfx.nChannels = self.out_channels
        wfx.nSamplesPerSec = self.SAMPLE_RATE
        wfx.wBitsPerSample = 16
        wfx.nBlockAlign = self.out_channels * 2
        wfx.nAvgBytesPerSec = wfx.nSamplesPerSec * wfx.nBlockAlign
        wfx.cbSize = 0

        mmresult = winmm.waveOutOpen(ctypes.byref(self._hwo), WAVE_MAPPER, ctypes.byref(wfx), None, None, CALLBACK_NULL)
        if mmresult != 0:
            raise RuntimeError(f"waveOutOpen() falhou (mmresult={mmresult}) -- confere se tem algum dispositivo de saída de áudio padrão configurado no Windows.")

        self._thread = threading.Thread(target=self._run, name="vst3-audio-engine", daemon=True)
        self._thread.start()
        print(f"Motor de áudio ao vivo iniciado: {self.SAMPLE_RATE} Hz, {self.out_channels} canal(is), bloco de {self.BLOCK_SIZE} amostras.")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._hwo:
            winmm.waveOutReset(self._hwo)
            winmm.waveOutClose(self._hwo)
        print("Motor de áudio parado.")

    def _run(self):
        bytes_per_block = self.BLOCK_SIZE * self.out_channels * 2  # 16-bit
        headers = []
        int_bufs = []
        for _ in range(self.NUM_BUFFERS):
            buf = (ctypes.c_int16 * (self.BLOCK_SIZE * self.out_channels))()
            hdr = WAVEHDR()
            hdr.lpData = ctypes.cast(buf, ctypes.c_void_p)
            hdr.dwBufferLength = bytes_per_block
            hdr.dwFlags = 0
            winmm.waveOutPrepareHeader(self._hwo, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
            headers.append(hdr)
            int_bufs.append(buf)

        first_use = [True] * self.NUM_BUFFERS
        idx = 0

        while not self._stop.is_set():
            hdr = headers[idx]
            buf = int_bufs[idx]

            # "Double buffering" clássico: só reescreve um buffer
            # depois que o winmm avisa (WHDR_DONE) que já terminou
            # de tocar ele. Na primeira volta o buffer nunca foi
            # escrito ainda, então não há o que esperar.
            if not first_use[idx]:
                while not (hdr.dwFlags & WHDR_DONE) and not self._stop.is_set():
                    time.sleep(0.001)
            first_use[idx] = False

            if self._stop.is_set():
                break

            hr = self.ap_vtbl.process(self.ap_self, ctypes.byref(self._data))
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

            winmm.waveOutWrite(self._hwo, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
            idx = (idx + 1) % self.NUM_BUFFERS

        for hdr in headers:
            winmm.waveOutUnprepareHeader(self._hwo, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))


# ═══════════════════════════════════════════════════════════════
#  Lógica principal -- reaproveita o passo 4 quase inteiro, só
#  inserindo o setup/start/stop do motor de áudio ao redor da GUI.
# ═══════════════════════════════════════════════════════════════

def _main_body(vst3_path: str):
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
        print("Esse plugin não expõe IEditController -- não dá pra abrir GUI nem tocar teclado embutido.")
        teardown_component_only()
        return

    ctrl_full_ptr = ctypes.cast(ctrl_self, ctypes.POINTER(step4.IEditControllerObjFull))
    ctrl_full_vtbl = ctrl_full_ptr.contents.lpVtbl.contents
    component_full_ptr = ctypes.cast(component_self, ctypes.POINTER(IComponentObjFull2))
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
            print(f"  getState() -> hr={hr_get:#x} ({len(state_stream._buf)} bytes), setComponentState() -> hr={hr_set:#x}")
        else:
            print(f"  getState() falhou (hr={hr_get:#x}) -- seguindo sem sincronizar estado.")

    print("\nsetComponentHandler()...")
    handler = step4.HostComponentHandler()
    hr_handler = ctrl_full_vtbl.setComponentHandler(ctrl_self, handler.ptr)
    print(f"  setComponentHandler() -> hr={hr_handler:#x}")

    # ─── Aqui começa a parte NOVA do passo 5: ligar o processamento
    # de áudio antes de abrir a janela. ────────────────────────────

    print("\nqueryInterface(IAudioProcessor)...")
    ap_obj = ctypes.c_void_p()
    hr_ap = component_vtbl.queryInterface(component_self, ctypes.byref(step3.IID_IAudioProcessor), ctypes.byref(ap_obj))
    if hr_ap != step1.kResultOk or not ap_obj:
        print(f"  Esse plugin não implementa IAudioProcessor (hr={hr_ap:#x}) -- não processa áudio, só abre a GUI.")
        ap_vtbl = ap_self = None
    else:
        ap_ptr = ctypes.cast(ap_obj, ctypes.POINTER(IAudioProcessorObjFull))
        ap_vtbl = ap_ptr.contents.lpVtbl.contents
        ap_self = ctypes.cast(ap_ptr, ctypes.c_void_p)
        print("  queryInterface(IAudioProcessor) OK.")

    engine = None
    if ap_vtbl is not None:
        out_channels = 2
        n_out_buses = component_vtbl.getBusCount(component_self, step2.kAudio, step2.kOutput)
        if n_out_buses > 0:
            info = step2.BusInfo()
            if component_vtbl.getBusInfo(component_self, step2.kAudio, step2.kOutput, 0, ctypes.byref(info)) == step1.kResultOk:
                out_channels = info.channelCount or 2
        print(f"Bus de saída principal: {out_channels} canal(is).")

        setup = ProcessSetup(
            processMode=kRealtime,
            symbolicSampleSize=kSample32,
            maxSamplesPerBlock=LiveAudioEngine.BLOCK_SIZE,
            sampleRate=float(LiveAudioEngine.SAMPLE_RATE),
        )
        hr = ap_vtbl.setupProcessing(ap_self, ctypes.byref(setup))
        print(f"setupProcessing({LiveAudioEngine.SAMPLE_RATE} Hz, bloco={LiveAudioEngine.BLOCK_SIZE}) -> hr={hr:#x}")

        if n_out_buses > 0:
            hr = component_full_vtbl.activateBus(component_self, step2.kAudio, step2.kOutput, 0, 1)
            print(f"activateBus(Audio, Output, 0, ativo) -> hr={hr:#x}")

        n_evt_in_buses = component_vtbl.getBusCount(component_self, step2.kEvent, step2.kInput)
        if n_evt_in_buses > 0:
            hr = component_full_vtbl.activateBus(component_self, step2.kEvent, step2.kInput, 0, 1)
            print(f"activateBus(Event, Input, 0, ativo) -> hr={hr:#x}")

        hr = component_full_vtbl.setActive(component_self, 1)
        print(f"setActive(true) -> hr={hr:#x}")

        hr = ap_vtbl.setProcessing(ap_self, 1)
        print(f"setProcessing(true) -> hr={hr:#x}")

        engine = LiveAudioEngine(ap_vtbl, ap_self, out_channels)
        engine.start()

    # ─── Daqui pra baixo é o mesmo fluxo de abrir GUI do passo 4. ──

    view_ptr_raw = ctrl_full_vtbl.createView(ctrl_self, step4.kEditor)
    if not view_ptr_raw:
        print("createView('editor') devolveu NULL -- esse plugin não tem editor gráfico.")
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
    print("createView('editor') OK.")

    supported = view_vtbl.isPlatformTypeSupported(view_self, step4.kPlatformTypeHWND)
    if supported != step1.kResultOk:
        raise RuntimeError("Esse plugin não suporta HWND nessa build.")

    size = step4.ViewRect()
    view_vtbl.getSize(view_self, ctypes.byref(size))
    w, h = size.right - size.left, size.bottom - size.top

    hwnd, wndproc_keepalive = step4.create_host_window(w, h, audio_class["name"] + " (áudio ao vivo)")
    step4.resize_host_window(hwnd, w, h)

    frame = step4.HostPlugFrame(hwnd)
    view_vtbl.setFrame(view_self, frame.ptr)

    hr = view_vtbl.attached(view_self, ctypes.c_void_p(hwnd), step4.kPlatformTypeHWND)
    print(f"attached() -> hr={hr:#x}")
    if hr != step1.kResultOk:
        if engine:
            engine.stop()
        raise RuntimeError(f"attached() falhou (hr={hr:#x})")

    frame.view_vtbl = view_vtbl
    frame.view_self = view_self

    step4.user32.ShowWindow(hwnd, step4.SW_SHOWNORMAL)
    step4.user32.UpdateWindow(hwnd)

    print("\nJanela aberta com áudio ao vivo -- clica no teclado embutido do plugin pra ouvir som.")
    print("Feche a janela do plugin pra parar tudo e desfazer direito.")
    step4.run_message_loop()

    print("\nJanela fechada, desfazendo tudo...")
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
    print("Passo 5 concluído sem crash.")


def main():
    if len(sys.argv) < 2:
        print("Uso: python vst3_host_step5_process_audio.py \"C:\\caminho\\pro\\Plugin.vst3\"")
        sys.exit(1)

    vst3_path = sys.argv[1]
    print(f"Carregando: {vst3_path}")
    try:
        _main_body(vst3_path)
    finally:
        pass


if __name__ == "__main__":
    main()