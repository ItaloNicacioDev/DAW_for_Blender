"""
native_host.py

Motor VST3 nativo REUTILIZÁVEL (biblioteca pura, sem bpy/numpy
obrigatório) -- consolida tudo que os steps 1-6 tutoriais construíram
e validaram contra plugins reais (Vital) numa única classe,
`VST3PluginInstance`, com API não-bloqueante pra ser chamada de
dentro do addon Blender.

Ver modules/vst/native_engine.py pra ponte com bpy/numpy/VSTProgramType
(esse arquivo aqui não sabe nada sobre Blender de propósito, pra
poder ser testado/reusado fora do addon também).

Cobertura:
  - load() / unload()
  - list_parameters() / set_parameter() / get_parameter()
  - process_effect(audio, automation=None)   -- offline, bloco a bloco
  - render_instrument(midi_notes, duration, automation=None) -- offline
  - stream_reset(midi_notes, origin_time) / stream_render_chunk(...)
  - save_state() / load_state()
  - open_editor() / is_editor_open() / close_editor() / trigger_live_note()
"""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vst3_host_step1_list_classes as step1  # noqa: E402
import vst3_host_step2_instantiate as step2  # noqa: E402
import vst3_host_step3_processor_controller as step3  # noqa: E402
import vst3_host_step4_open_gui as step4  # noqa: E402
import vst3_host_step5_process_audio as step5  # noqa: E402
import vst3_host_step6_midi_input as step6  # noqa: E402


# ═══════════════════════════════════════════════════════════════
#  IParameterChanges / IParamValueQueue (ivstparameterchanges.h) --
#  única peça que faltava dos steps anteriores. Sem isso,
#  set_parameter()/automação não chegam de verdade no processador de
#  áudio durante process_effect()/render_instrument() (só mudam o
#  controller, que é só "modelo da GUI").
# ═══════════════════════════════════════════════════════════════

GetParameterIdFunc = ctypes.WINFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p)
GetPointCountFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p)
GetPointFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_double))
AddPointFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32, ctypes.c_double, ctypes.POINTER(ctypes.c_int32))


class IParamValueQueueVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("getParameterId", GetParameterIdFunc),
        ("getPointCount", GetPointCountFunc),
        ("getPoint", GetPointFunc),
        ("addPoint", AddPointFunc),
    ]


class IParamValueQueueObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IParamValueQueueVtbl))]


class HostParamValueQueue:
    def __init__(self, param_id: int):
        self.param_id = param_id
        self.points: List[Tuple[int, float]] = []
        self._qi = step1.QueryInterfaceFunc(self._query_interface)
        self._ar = step1.AddRefFunc(lambda this: 1)
        self._rel = step1.ReleaseFunc(lambda this: 1)
        self._get_id = GetParameterIdFunc(lambda this: self.param_id)
        self._get_count = GetPointCountFunc(lambda this: len(self.points))
        self._get_point = GetPointFunc(self._get_point_impl)
        self._add_point = AddPointFunc(self._add_point_impl)
        self._vtbl = IParamValueQueueVtbl(self._qi, self._ar, self._rel, self._get_id, self._get_count, self._get_point, self._add_point)
        self._obj = IParamValueQueueObj(ctypes.pointer(self._vtbl))
        self.ptr = ctypes.cast(ctypes.pointer(self._obj), ctypes.c_void_p)

    def _query_interface(self, this, iid_ptr, obj_ptr_ptr):
        out = ctypes.cast(obj_ptr_ptr, ctypes.POINTER(ctypes.c_void_p))
        out[0] = this
        return step1.kResultOk

    def _get_point_impl(self, this, index, offset_ptr, value_ptr):
        if index < 0 or index >= len(self.points):
            return 0x80070057  # E_INVALIDARG
        off, val = self.points[index]
        offset_ptr[0] = off
        value_ptr[0] = val
        return step1.kResultOk

    def _add_point_impl(self, this, sample_offset, value, index_ptr):
        self.points.append((sample_offset, value))
        index_ptr[0] = len(self.points) - 1
        return step1.kResultOk


GetParameterCountFuncPC = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p)
GetParameterDataFunc = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32)
AddParameterDataFunc = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_int32))


class IParameterChangesVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("getParameterCount", GetParameterCountFuncPC),
        ("getParameterData", GetParameterDataFunc),
        ("addParameterData", AddParameterDataFunc),
    ]


class IParameterChangesObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IParameterChangesVtbl))]


class HostParameterChanges:
    """Reconstruída a cada bloco de process() -- representa só as
    mudanças de parâmetro daquele bloco (não um histórico)."""

    def __init__(self):
        self._queues: List[HostParamValueQueue] = []
        self._qi = step1.QueryInterfaceFunc(self._query_interface)
        self._ar = step1.AddRefFunc(lambda this: 1)
        self._rel = step1.ReleaseFunc(lambda this: 1)
        self._get_count = GetParameterCountFuncPC(lambda this: len(self._queues))
        self._get_data = GetParameterDataFunc(self._get_data_impl)
        self._add_data = AddParameterDataFunc(self._add_data_impl)
        self._vtbl = IParameterChangesVtbl(self._qi, self._ar, self._rel, self._get_count, self._get_data, self._add_data)
        self._obj = IParameterChangesObj(ctypes.pointer(self._vtbl))
        self.ptr = ctypes.cast(ctypes.pointer(self._obj), ctypes.c_void_p)

    def add_point(self, param_id: int, value: float, sample_offset: int = 0):
        q = HostParamValueQueue(param_id)
        q.points.append((sample_offset, value))
        self._queues.append(q)

    def _query_interface(self, this, iid_ptr, obj_ptr_ptr):
        out = ctypes.cast(obj_ptr_ptr, ctypes.POINTER(ctypes.c_void_p))
        out[0] = this
        return step1.kResultOk

    def _get_data_impl(self, this, index):
        if index < 0 or index >= len(self._queues):
            return None
        return self._queues[index].ptr.value

    def _add_data_impl(self, this, id_ptr, index_ptr):
        param_id = id_ptr[0]
        q = HostParamValueQueue(param_id)
        self._queues.append(q)
        index_ptr[0] = len(self._queues) - 1
        return q.ptr.value


# Win32 extra que os steps anteriores não precisavam (loop de
# mensagens NÃO-bloqueante pra rodar num thread dedicado sem travar
# o Blender).
PM_REMOVE = 0x0001
WM_QUIT = 0x0012
step4.user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
step4.user32.PeekMessageW.restype = wintypes.BOOL
step4.user32.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint32, wintypes.WPARAM, wintypes.LPARAM]
step4.user32.PostMessageW.restype = wintypes.BOOL


class VST3PluginInstance:
    """Uma instância carregada de um plugin VST3. Não sabe nada de
    numpy/bpy -- `process_effect`/`render_instrument` recebem e
    devolvem listas de arrays de float (um por canal); a camada
    Blender (native_engine.py) converte pra numpy."""

    def __init__(self, path: str, sample_rate: int = 44100, block_size: int = 1024):
        self.path = str(path)
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.loaded = False
        self.plugin_name = ""
        self.last_error = ""

        self._dll = None
        self._factory = None
        self._component_vtbl = None
        self._component_self = None
        self._component_full_vtbl = None
        self._ctrl_vtbl = None
        self._ctrl_self = None
        self._ctrl_full_vtbl = None
        self._ctrl_is_separate = False
        self._ap_vtbl = None
        self._ap_self = None
        self._host_context = None
        self._handler = None
        self._connected = False
        self._comp_cp = None  # (vtbl, self)
        self._ctrl_cp = None  # (vtbl, self)
        self._out_channels = 2
        self._in_channels = 0
        self._has_event_in_bus = False
        self._param_defaults: Dict[int, float] = {}

        # Sessão ao vivo (open_editor()).
        self._hwnd = None
        self._wndproc_keepalive = None
        self._view_vtbl = None
        self._view_self = None
        self._frame = None
        self._live_engine = None
        self._live_event_list = None
        self._editor_thread: Optional[threading.Thread] = None
        self._editor_stop: Optional[threading.Event] = None
        self._editor_open = False

    # ------------------------------------------------------------------
    # Carregar / descarregar
    # ------------------------------------------------------------------

    def load(self) -> bool:
        try:
            self._dll, self._factory = step1.load_vst3_factory(self.path)
            classes = step1.list_classes(self._factory)
            audio_class = step2.find_audio_module_class(classes)
            self.plugin_name = audio_class["name"]

            component_ptr = step2.create_component(self._factory, audio_class["cid"])
            self._component_vtbl = component_ptr.contents.lpVtbl.contents
            self._component_self = ctypes.cast(component_ptr, ctypes.c_void_p)

            self._host_context = step4.HostApplicationContext()
            hr = self._component_vtbl.initialize(self._component_self, self._host_context.ptr)
            if hr != step1.kResultOk:
                raise RuntimeError(f"initialize() do componente falhou (hr={hr:#x})")

            self._ctrl_vtbl, self._ctrl_self, self._ctrl_is_separate = step3.get_or_create_controller(
                self._factory, self._component_vtbl, self._component_self, self._host_context
            )

            component_full_ptr = ctypes.cast(self._component_self, ctypes.POINTER(step5.IComponentObjFull2))
            self._component_full_vtbl = component_full_ptr.contents.lpVtbl.contents

            if self._ctrl_vtbl is not None:
                ctrl_full_ptr = ctypes.cast(self._ctrl_self, ctypes.POINTER(step4.IEditControllerObjFull))
                self._ctrl_full_vtbl = ctrl_full_ptr.contents.lpVtbl.contents

                if self._ctrl_is_separate:
                    self._connect_component_controller()
                    self._sync_state()

                self._handler = step4.HostComponentHandler()
                self._ctrl_full_vtbl.setComponentHandler(self._ctrl_self, self._handler.ptr)

            self._setup_audio_processor()

            self.loaded = True
            return True
        except Exception as e:
            self.last_error = str(e)
            self._safe_unload_partial()
            self.loaded = False
            return False

    def _connect_component_controller(self):
        comp_cp_obj = ctypes.c_void_p()
        hr_comp_cp = self._component_vtbl.queryInterface(self._component_self, ctypes.byref(step4.IID_IConnectionPoint), ctypes.byref(comp_cp_obj))
        ctrl_cp_obj = ctypes.c_void_p()
        hr_ctrl_cp = self._ctrl_vtbl.queryInterface(self._ctrl_self, ctypes.byref(step4.IID_IConnectionPoint), ctypes.byref(ctrl_cp_obj))
        if hr_comp_cp != step1.kResultOk or hr_ctrl_cp != step1.kResultOk:
            return

        comp_cp_ptr = ctypes.cast(comp_cp_obj, ctypes.POINTER(step4.IConnectionPointObj))
        comp_cp_vtbl = comp_cp_ptr.contents.lpVtbl.contents
        comp_cp_self = ctypes.cast(comp_cp_ptr, ctypes.c_void_p)

        ctrl_cp_ptr = ctypes.cast(ctrl_cp_obj, ctypes.POINTER(step4.IConnectionPointObj))
        ctrl_cp_vtbl = ctrl_cp_ptr.contents.lpVtbl.contents
        ctrl_cp_self = ctypes.cast(ctrl_cp_ptr, ctypes.c_void_p)

        hr1 = comp_cp_vtbl.connect(comp_cp_self, ctrl_cp_self)
        hr2 = ctrl_cp_vtbl.connect(ctrl_cp_self, comp_cp_self)
        if hr1 == step1.kResultOk and hr2 == step1.kResultOk:
            self._connected = True
            self._comp_cp = (comp_cp_vtbl, comp_cp_self)
            self._ctrl_cp = (ctrl_cp_vtbl, ctrl_cp_self)

    def _sync_state(self):
        state_stream = step4.MemoryBStream()
        hr_get = self._component_full_vtbl.getState(self._component_self, state_stream.ptr)
        if hr_get == step1.kResultOk:
            state_stream.rewind()
            self._ctrl_full_vtbl.setComponentState(self._ctrl_self, state_stream.ptr)

    def _setup_audio_processor(self):
        ap_obj = ctypes.c_void_p()
        hr_ap = self._component_vtbl.queryInterface(self._component_self, ctypes.byref(step3.IID_IAudioProcessor), ctypes.byref(ap_obj))
        if hr_ap != step1.kResultOk or not ap_obj:
            return

        ap_ptr = ctypes.cast(ap_obj, ctypes.POINTER(step5.IAudioProcessorObjFull))
        self._ap_vtbl = ap_ptr.contents.lpVtbl.contents
        self._ap_self = ctypes.cast(ap_ptr, ctypes.c_void_p)

        n_out = self._component_vtbl.getBusCount(self._component_self, step2.kAudio, step2.kOutput)
        if n_out > 0:
            info = step2.BusInfo()
            if self._component_vtbl.getBusInfo(self._component_self, step2.kAudio, step2.kOutput, 0, ctypes.byref(info)) == step1.kResultOk:
                self._out_channels = info.channelCount or 2

        n_in = self._component_vtbl.getBusCount(self._component_self, step2.kAudio, step2.kInput)
        if n_in > 0:
            info_in = step2.BusInfo()
            if self._component_vtbl.getBusInfo(self._component_self, step2.kAudio, step2.kInput, 0, ctypes.byref(info_in)) == step1.kResultOk:
                self._in_channels = info_in.channelCount or 0

        setup = step5.ProcessSetup(
            processMode=step5.kRealtime,
            symbolicSampleSize=step5.kSample32,
            maxSamplesPerBlock=self.block_size,
            sampleRate=float(self.sample_rate),
        )
        self._ap_vtbl.setupProcessing(self._ap_self, ctypes.byref(setup))

        if n_out > 0:
            self._component_full_vtbl.activateBus(self._component_self, step2.kAudio, step2.kOutput, 0, 1)
        if n_in > 0:
            self._component_full_vtbl.activateBus(self._component_self, step2.kAudio, step2.kInput, 0, 1)

        n_evt_in = self._component_vtbl.getBusCount(self._component_self, step2.kEvent, step2.kInput)
        self._has_event_in_bus = n_evt_in > 0
        if self._has_event_in_bus:
            self._component_full_vtbl.activateBus(self._component_self, step2.kEvent, step2.kInput, 0, 1)

        self._component_full_vtbl.setActive(self._component_self, 1)
        self._ap_vtbl.setProcessing(self._ap_self, 1)

    def unload(self):
        self.close_editor()

        if self._ap_vtbl is not None:
            try:
                self._ap_vtbl.setProcessing(self._ap_self, 0)
            except Exception:
                pass
        if self._component_full_vtbl is not None:
            try:
                self._component_full_vtbl.setActive(self._component_self, 0)
            except Exception:
                pass

        if self._connected and self._comp_cp and self._ctrl_cp:
            comp_cp_vtbl, comp_cp_self = self._comp_cp
            ctrl_cp_vtbl, ctrl_cp_self = self._ctrl_cp
            try:
                comp_cp_vtbl.disconnect(comp_cp_self, ctrl_cp_self)
                ctrl_cp_vtbl.disconnect(ctrl_cp_self, comp_cp_self)
                comp_cp_vtbl.release(comp_cp_self)
                ctrl_cp_vtbl.release(ctrl_cp_self)
            except Exception:
                pass

        if self._ctrl_vtbl is not None:
            try:
                if self._ctrl_is_separate:
                    self._ctrl_vtbl.terminate(self._ctrl_self)
                self._ctrl_vtbl.release(self._ctrl_self)
            except Exception:
                pass

        if self._component_vtbl is not None:
            try:
                self._component_vtbl.terminate(self._component_self)
                self._component_vtbl.release(self._component_self)
            except Exception:
                pass

        if self._dll is not None:
            try:
                step1.unload_vst3_module(self._dll)
            except Exception:
                pass

        self.loaded = False

    def _safe_unload_partial(self):
        """Chamado quando load() falha no meio -- desfaz o que já foi
        criado, sem assumir que tudo existe."""
        try:
            self.unload()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Parâmetros
    # ------------------------------------------------------------------

    def list_parameters(self) -> List[Dict[str, Any]]:
        if not self.loaded or self._ctrl_full_vtbl is None:
            return []
        count = self._ctrl_full_vtbl.getParameterCount(self._ctrl_self)
        result = []
        info = step3.ParameterInfo()
        for i in range(count):
            hr = self._ctrl_full_vtbl.getParameterInfo(self._ctrl_self, i, ctypes.byref(info))
            if hr != step1.kResultOk:
                continue
            value = self._ctrl_full_vtbl.getParamNormalized(self._ctrl_self, info.id)
            result.append({
                "id": info.id,
                "name": info.title.decode("utf-16-le", errors="replace").rstrip("\x00") if isinstance(info.title, bytes) else str(info.title),
                "value": float(value),
                "label": "",
            })
        return result

    def set_parameter(self, param_id: int, value: float):
        if not self.loaded:
            return
        value = max(0.0, min(1.0, float(value)))
        self._param_defaults[int(param_id)] = value
        if self._ctrl_full_vtbl is not None:
            try:
                self._ctrl_full_vtbl.setParamNormalized(self._ctrl_self, int(param_id), value)
            except Exception:
                pass
        if self._live_engine is not None:
            # Sessão ao vivo rodando -- aplica já, não só no próximo
            # process_effect()/render_instrument().
            self._push_live_param(int(param_id), value)

    def get_parameter(self, param_id: int) -> float:
        if not self.loaded or self._ctrl_full_vtbl is None:
            return 0.0
        try:
            return float(self._ctrl_full_vtbl.getParamNormalized(self._ctrl_self, int(param_id)))
        except Exception:
            return 0.0

    def _push_live_param(self, param_id: int, value: float):
        # A sessão ao vivo (LiveAudioEngine) não tem input de
        # parâmetros próprio -- então empurra via IParameterChanges
        # direto no próximo process() dela, através de um hook simples.
        if self._live_engine is None:
            return
        pc = HostParameterChanges()
        pc.add_point(param_id, value, 0)
        # Guardamos só o último -- LiveAudioEngine lê isso a cada bloco.
        self._live_engine.pending_input_param_changes = pc

    # ------------------------------------------------------------------
    # Processamento offline (efeito / instrumento)
    # ------------------------------------------------------------------

    def _resolve_automation_value_at(self, automation: Optional[list], t: float) -> Dict[int, float]:
        """`automation` é [[tempo_seg, {param_id_str: valor}], ...]
        (mesmo formato que vst.py já monta). Acha o ponto mais próximo
        <= t (segura o valor entre pontos, igual o schedule original
        já pressupõe -- ver AUTOMATION_HOP_SECONDS em vst.py)."""
        if not automation:
            return {}
        chosen = None
        for point in automation:
            pt_time = point[0]
            if pt_time <= t:
                chosen = point
            else:
                break
        if chosen is None:
            chosen = automation[0]
        return {int(pid): float(val) for pid, val in chosen[1].items()}

    def _run_offline_blocks(
        self,
        n_samples: int,
        input_audio: Optional[List[List[float]]] = None,
        note_events: Optional[List[Tuple[int, int, int, float]]] = None,  # (abs_sample, type, pitch, velocity)
        automation: Optional[list] = None,
    ) -> List[List[float]]:
        """Motor comum de process_effect()/render_instrument(): roda
        process() bloco a bloco (offline, sem winmm) e devolve o
        áudio de saída completo."""
        if self._ap_vtbl is None:
            raise RuntimeError(f"Plugin '{self.plugin_name}' não tem IAudioProcessor.")

        out_bufs = [[0.0] * n_samples for _ in range(self._out_channels)]

        in_channels = self._in_channels if input_audio else 0
        in_arrays = None
        in_ptrs = None
        in_bus = None
        if in_channels > 0:
            in_arrays = [(ctypes.c_float * self.block_size)() for _ in range(in_channels)]
            in_ptrs = (ctypes.POINTER(ctypes.c_float) * in_channels)()
            for ch, arr in enumerate(in_arrays):
                in_ptrs[ch] = ctypes.cast(arr, ctypes.POINTER(ctypes.c_float))
            in_bus = step5.AudioBusBuffers(numChannels=in_channels, silenceFlags=0, channelBuffers32=in_ptrs)

        out_arrays = [(ctypes.c_float * self.block_size)() for _ in range(self._out_channels)]
        out_ptrs = (ctypes.POINTER(ctypes.c_float) * self._out_channels)()
        for ch, arr in enumerate(out_arrays):
            out_ptrs[ch] = ctypes.cast(arr, ctypes.POINTER(ctypes.c_float))
        out_bus = step5.AudioBusBuffers(numChannels=self._out_channels, silenceFlags=0, channelBuffers32=out_ptrs)

        ctx = step5.ProcessContext()
        ctx.state = step5.kPlayingFlag
        ctx.sampleRate = float(self.sample_rate)
        ctx.tempo = 120.0
        ctx.timeSigNumerator = 4
        ctx.timeSigDenominator = 4

        data = step5.ProcessData()
        data.processMode = step5.kRealtime
        data.symbolicSampleSize = step5.kSample32
        data.numInputs = 1 if in_channels > 0 else 0
        data.numOutputs = 1
        data.inputs = ctypes.pointer(in_bus) if in_bus is not None else None
        data.outputs = ctypes.pointer(out_bus)
        data.processContext = ctypes.pointer(ctx)

        event_list = step6.HostEventList() if (self._has_event_in_bus and note_events) else None
        events_sorted = sorted(note_events or [], key=lambda e: e[0])
        evt_idx = 0

        sample_pos = 0
        while sample_pos < n_samples:
            this_block = min(self.block_size, n_samples - sample_pos)
            data.numSamples = this_block

            if in_channels > 0 and input_audio is not None:
                for ch in range(in_channels):
                    src = input_audio[ch] if ch < len(input_audio) else input_audio[0]
                    for i in range(this_block):
                        idx = sample_pos + i
                        in_arrays[ch][i] = src[idx] if idx < len(src) else 0.0

            if event_list is not None:
                event_list.clear()
                while evt_idx < len(events_sorted) and events_sorted[evt_idx][0] < sample_pos + this_block:
                    abs_sample, etype, pitch, velocity = events_sorted[evt_idx]
                    offset = max(0, abs_sample - sample_pos)
                    if abs_sample >= sample_pos:
                        e = step6.Event()
                        e.busIndex = 0
                        e.sampleOffset = offset
                        e.ppqPosition = 0.0
                        e.flags = step6.kIsLive
                        e.type = etype
                        if etype == step6.kNoteOnEvent:
                            e.event.noteOn.channel = 0
                            e.event.noteOn.pitch = pitch
                            e.event.noteOn.tuning = 0.0
                            e.event.noteOn.velocity = velocity
                            e.event.noteOn.length = 0
                            e.event.noteOn.noteId = pitch
                        else:
                            e.event.noteOff.channel = 0
                            e.event.noteOff.pitch = pitch
                            e.event.noteOff.velocity = velocity
                            e.event.noteOff.noteId = pitch
                            e.event.noteOff.tuning = 0.0
                        with event_list._lock:
                            event_list._events.append(e)
                    evt_idx += 1
                data.inputEvents = event_list.ptr
            else:
                data.inputEvents = None

            block_t = sample_pos / float(self.sample_rate)
            param_values = self._resolve_automation_value_at(automation, block_t) if automation else {}
            for pid, val in self._param_defaults.items():
                param_values.setdefault(pid, val)
            param_changes = None
            if param_values:
                param_changes = HostParameterChanges()
                for pid, val in param_values.items():
                    param_changes.add_point(pid, val, 0)
                data.inputParameterChanges = param_changes.ptr
            else:
                data.inputParameterChanges = None

            self._ap_vtbl.process(self._ap_self, ctypes.byref(data))

            for ch in range(self._out_channels):
                for i in range(this_block):
                    out_bufs[ch][sample_pos + i] = out_arrays[ch][i]

            sample_pos += this_block

        return out_bufs

    def process_effect(self, audio: List[List[float]], automation: Optional[list] = None) -> List[List[float]]:
        if not self.loaded:
            raise RuntimeError(f"VST '{self.plugin_name}' não carregado")
        n_samples = len(audio[0]) if audio else 0
        return self._run_offline_blocks(n_samples, input_audio=audio, automation=automation)

    def render_instrument(
        self,
        midi_notes: Sequence[Tuple[int, float, float, int]],  # (pitch, start_s, duration_s, velocity)
        duration: float,
        automation: Optional[list] = None,
    ) -> List[List[float]]:
        if not self.loaded:
            raise RuntimeError(f"VST '{self.plugin_name}' não carregado")
        n_samples = max(1, int(round(duration * self.sample_rate)))
        events: List[Tuple[int, int, int, float]] = []
        for pitch, start_s, dur_s, velocity in midi_notes:
            start_sample = int(round(start_s * self.sample_rate))
            end_sample = int(round((start_s + dur_s) * self.sample_rate))
            vel_norm = velocity / 127.0 if velocity > 1.0 else velocity
            events.append((start_sample, step6.kNoteOnEvent, int(pitch), vel_norm))
            events.append((end_sample, step6.kNoteOffEvent, int(pitch), vel_norm))
        return self._run_offline_blocks(n_samples, note_events=events, automation=automation)

    # ------------------------------------------------------------------
    # Streaming (playback quase-tempo-real via pré-render adiantado)
    # ------------------------------------------------------------------

    def stream_reset(self, midi_notes: Sequence[Tuple[int, float, float, int]], origin_time: float) -> bool:
        if not self.loaded:
            raise RuntimeError(f"VST '{self.plugin_name}' não carregado")
        self._stream_origin = float(origin_time)
        self._stream_elapsed = 0.0
        events: List[Tuple[int, int, int, float]] = []
        for pitch, start_s, dur_s, velocity in midi_notes:
            rel_start = start_s - origin_time
            rel_end = rel_start + dur_s
            if rel_end < 0:
                continue  # nota já teria terminado antes do início do stream
            start_sample = max(0, int(round(rel_start * self.sample_rate)))
            end_sample = max(0, int(round(rel_end * self.sample_rate)))
            vel_norm = velocity / 127.0 if velocity > 1.0 else velocity
            events.append((start_sample, step6.kNoteOnEvent, int(pitch), vel_norm))
            events.append((end_sample, step6.kNoteOffEvent, int(pitch), vel_norm))
        self._stream_events = sorted(events, key=lambda e: e[0])
        self._stream_sample_pos = 0
        return True

    def stream_render_chunk(self, chunk_seconds: float, automation_point: Optional[dict] = None) -> Tuple[List[List[float]], float]:
        if not self.loaded:
            raise RuntimeError(f"VST '{self.plugin_name}' não carregado")
        if not hasattr(self, "_stream_events"):
            self.stream_reset([], 0.0)

        n_samples = max(1, int(round(chunk_seconds * self.sample_rate)))
        start_pos = self._stream_sample_pos
        end_pos = start_pos + n_samples

        chunk_events = []
        remaining = []
        for abs_sample, etype, pitch, velocity in self._stream_events:
            if abs_sample < end_pos:
                chunk_events.append((abs_sample - start_pos, etype, pitch, velocity))
            else:
                remaining.append((abs_sample, etype, pitch, velocity))
        self._stream_events = remaining

        automation = None
        if automation_point:
            automation = [[0.0, {str(k): v for k, v in automation_point.items()}]]

        # Reaproveita _run_offline_blocks, mas com eventos já
        # relativos ao início desse pedaço (sample_pos parte de 0
        # dentro da chamada, então os offsets já batem).
        events_local = [(max(0, e[0]), e[1], e[2], e[3]) for e in chunk_events]
        out = self._run_offline_blocks(n_samples, note_events=events_local, automation=automation)

        self._stream_sample_pos = end_pos
        self._stream_elapsed += n_samples / float(self.sample_rate)
        return out, self._stream_elapsed

    # ------------------------------------------------------------------
    # Estado nativo (save/load)
    # ------------------------------------------------------------------

    def save_state(self) -> bytes:
        if not self.loaded or self._component_full_vtbl is None:
            return b""
        stream = step4.MemoryBStream()
        hr = self._component_full_vtbl.getState(self._component_self, stream.ptr)
        if hr != step1.kResultOk:
            return b""
        return bytes(stream._buf)

    def load_state(self, data: bytes) -> bool:
        if not self.loaded or not data or self._component_full_vtbl is None:
            return False
        stream = step4.MemoryBStream()
        stream._buf = bytearray(data)
        stream.rewind()
        hr = self._component_full_vtbl.setState(self._component_self, stream.ptr)
        ok = hr == step1.kResultOk
        if ok and self._ctrl_is_separate and self._ctrl_full_vtbl is not None:
            stream.rewind()
            self._ctrl_full_vtbl.setComponentState(self._ctrl_self, stream.ptr)
        return ok

    # ------------------------------------------------------------------
    # GUI ao vivo (não-bloqueante -- roda numa thread dedicada)
    # ------------------------------------------------------------------

    def open_editor(self) -> bool:
        if not self.loaded or self._ctrl_full_vtbl is None:
            return False
        if self._editor_open:
            return True

        ready = threading.Event()
        result = [False]
        self._editor_stop = threading.Event()

        def _editor_thread():
            try:
                view_ptr_raw = self._ctrl_full_vtbl.createView(self._ctrl_self, step4.kEditor)
                if not view_ptr_raw:
                    result[0] = False
                    ready.set()
                    return

                view_ptr = ctypes.cast(view_ptr_raw, ctypes.POINTER(step4.IPlugViewObj))
                self._view_vtbl = view_ptr.contents.lpVtbl.contents
                self._view_self = ctypes.cast(view_ptr, ctypes.c_void_p)

                if self._view_vtbl.isPlatformTypeSupported(self._view_self, step4.kPlatformTypeHWND) != step1.kResultOk:
                    result[0] = False
                    ready.set()
                    return

                size = step4.ViewRect()
                self._view_vtbl.getSize(self._view_self, ctypes.byref(size))
                w, h = size.right - size.left, size.bottom - size.top

                self._hwnd, self._wndproc_keepalive = step4.create_host_window(w, h, self.plugin_name)
                step4.resize_host_window(self._hwnd, w, h)

                self._frame = step4.HostPlugFrame(self._hwnd)
                self._view_vtbl.setFrame(self._view_self, self._frame.ptr)

                hr = self._view_vtbl.attached(self._view_self, ctypes.c_void_p(self._hwnd), step4.kPlatformTypeHWND)
                if hr != step1.kResultOk:
                    result[0] = False
                    ready.set()
                    return

                self._frame.view_vtbl = self._view_vtbl
                self._frame.view_self = self._view_self

                step4.user32.ShowWindow(self._hwnd, step4.SW_SHOWNORMAL)
                step4.user32.UpdateWindow(self._hwnd)

                if self._ap_vtbl is not None:
                    self._live_event_list = step6.HostEventList() if self._has_event_in_bus else None
                    self._live_engine = step5.LiveAudioEngine(
                        self._ap_vtbl, self._ap_self, self._out_channels,
                        input_event_list=self._live_event_list,
                    )
                    self._live_engine.pending_input_param_changes = None
                    self._live_engine.start()

                self._editor_open = True
                result[0] = True
                ready.set()

                msg = wintypes.MSG()
                while not self._editor_stop.is_set():
                    has_msg = step4.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE)
                    if has_msg:
                        if msg.message == WM_QUIT:
                            break
                        step4.user32.TranslateMessage(ctypes.byref(msg))
                        step4.user32.DispatchMessageW(ctypes.byref(msg))
                    else:
                        time.sleep(0.01)

                if self._live_engine is not None:
                    try:
                        self._ap_vtbl.setProcessing(self._ap_self, 0)
                    except Exception:
                        pass
                    self._live_engine.stop()
                    self._live_engine = None
                    try:
                        self._ap_vtbl.setProcessing(self._ap_self, 1)
                    except Exception:
                        pass

                try:
                    self._view_vtbl.removed(self._view_self)
                    self._view_vtbl.release(self._view_self)
                except Exception:
                    pass
                self._view_vtbl = None
                self._view_self = None
                self._hwnd = None
                self._editor_open = False
            except Exception as e:
                self.last_error = str(e)
                result[0] = False
                self._editor_open = False
                ready.set()

        self._editor_thread = threading.Thread(target=_editor_thread, name=f"vst3-editor-{self.plugin_name}", daemon=True)
        self._editor_thread.start()
        ready.wait(timeout=10.0)
        return result[0]

    def is_editor_open(self) -> bool:
        return self._editor_open

    def close_editor(self):
        if not self._editor_open or self._hwnd is None:
            if self._editor_stop is not None:
                self._editor_stop.set()
            return
        try:
            step4.user32.PostMessageW(self._hwnd, step4.WM_CLOSE, 0, 0)
        except Exception:
            pass
        if self._editor_stop is not None:
            self._editor_stop.set()
        if self._editor_thread is not None:
            self._editor_thread.join(timeout=2.0)

    def trigger_live_note(self, pitch: int, velocity: int = 100, duration: float = 1.0) -> bool:
        if not self._editor_open or self._live_engine is None or self._live_event_list is None:
            return False
        vel_norm = velocity / 127.0 if velocity > 1.0 else velocity
        self._live_event_list.push_note_on(0, int(pitch), vel_norm)

        def _note_off_later():
            time.sleep(max(0.01, duration))
            if self._live_event_list is not None:
                self._live_event_list.push_note_off(0, int(pitch), vel_norm)

        threading.Thread(target=_note_off_later, daemon=True).start()
        return True

    def __repr__(self) -> str:
        status = "carregado" if self.loaded else "não carregado"
        return f"<VST3PluginInstance '{self.plugin_name}' [{status}] @ {self.sample_rate}Hz>"