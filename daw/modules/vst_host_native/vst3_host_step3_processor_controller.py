"""
vst3_host_step3_processor_controller.py

PASSO 3 do host VST3 nativo (continuação do step1 + step2).

O que esse script faz, e SÓ isso, NESSA ORDEM:
  1. Reusa passo 1 + passo 2 pra chegar num IComponent inicializado
     (igual o passo 2 já validou em 4 plugins de fabricantes
     diferentes).
  2. queryInterface(IAudioProcessor) NO MESMO OBJETO do IComponent.
     Isso é assim de propósito: na spec VST3, o componente de áudio
     ("Audio Module Class") normalmente implementa IComponent E
     IAudioProcessor no MESMO objeto C++ (herança múltipla) -- não
     são duas classes diferentes. Por isso a gente NÃO faz
     createInstance() de novo aqui, só pergunta pro mesmo objeto
     "você também fala IAudioProcessor?" via queryInterface. Se der
     kNoInterface, esse plugin não processa áudio nesse componente
     (bem incomum, mas tecnicamente permitido pela spec).
  3. Só pra validar que a interface funciona de verdade (sem ainda
     processar áudio real): chama canProcessSampleSize() e
     getLatencySamples().
  4. Instancia o Edit Controller -- e aqui tem uma bifurcação que
     TEM que existir pra funcionar com qualquer plugin:
       a) Se getControllerClassId() (já visto no passo 2) devolve um
          CID diferente de zero, o controller é um objeto SEPARADO
          -> createInstance() nesse CID pedindo IEditController, e
          chama initialize() nele também (ele é uma instância nova,
          ninguém inicializou ainda).
       b) Se o CID vem zerado (ou getControllerClassId falha), é o
          padrão "SingleComponentEffect": o PRÓPRIO objeto do
          IComponent também implementa IEditController. Nesse caso
          é só queryInterface(IEditController) no mesmo objeto --
          NÃO chama initialize() de novo (o objeto já foi
          inicializado no passo 2/3, chamar de novo seria errado).
     Sem essa bifurcação o script só funcionaria com plugins que
     usam controller separado (a maioria dos grandes, tipo Serum,
     Vital) e quebraria silenciosamente (ou pior, teria comportamento
     indefinido) em plugins mais simples que usam
     SingleComponentEffect.
  5. Lê getParameterCount() + getParameterInfo() dos primeiros
     parâmetros, só pra confirmar que a comunicação com o controller
     funciona.
  6. Desfaz tudo direito: terminate()/release() de cada objeto que
     foi inicializado ou teve refcount incrementado (toda chamada de
     queryInterface ou createInstance devolve uma referência com
     addRef já feito -- isso PRECISA de um release() correspondente,
     senão vaza referência do lado do plugin).

O que esse script NÃO faz ainda (vem no próximo passo):
  - Não chama setupProcessing()/process() de verdade (processar um
    bloco de áudio).
  - Não conecta IComponent <-> IEditController via IConnectionPoint
    (necessário nos plugins que separam os dois em processos/threads
     diferentes -- a maioria não precisa, mas alguns exigem).

USO:
    python vst3_host_step3_processor_controller.py "C:\\Caminho\\Para\\O\\Plugin.vst3"
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vst3_host_step1_list_classes as step1  # noqa: E402
import vst3_host_step2_instantiate as step2  # noqa: E402


# ═══════════════════════════════════════════════════════════════
#  IIDs adicionais (pluginterfaces/vst/ivstaudioprocessor.h e
#  pluginterfaces/vst/ivsteditcontroller.h)
# ═══════════════════════════════════════════════════════════════

# DECLARE_CLASS_IID (IAudioProcessor, 0x42043F99, 0xB7DA453C, 0xA569E79D, 0x9AAEC33D)
IID_IAudioProcessor = step1._uid_from_four_u32(0x42043F99, 0xB7DA453C, 0xA569E79D, 0x9AAEC33D)

# DECLARE_CLASS_IID (IEditController, 0xDCD7BBE3, 0x7742448D, 0xA874AACC, 0x979C759E)
IID_IEditController = step1._uid_from_four_u32(0xDCD7BBE3, 0x7742448D, 0xA874AACC, 0x979C759E)

kSample32 = 0  # Vst::SymbolicSampleSizes::kSample32


# ═══════════════════════════════════════════════════════════════
#  Vtable do IAudioProcessor (FUnknown (3) + 8 métodos próprios)
#  Só damos assinatura real pra canProcessSampleSize/getLatencySamples
#  -- os outros só ocupam o slot certo (mesmo raciocínio do passo 2).
# ═══════════════════════════════════════════════════════════════

CanProcessSampleSizeFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32)
GetLatencySamplesFunc = ctypes.WINFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p)
_GenericFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p)


class IAudioProcessorVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("setBusArrangements", _GenericFunc),
        ("getBusArrangement", _GenericFunc),
        ("canProcessSampleSize", CanProcessSampleSizeFunc),
        ("getLatencySamples", GetLatencySamplesFunc),
        ("setupProcessing", _GenericFunc),
        ("setProcessing", _GenericFunc),
        ("process", _GenericFunc),
        ("getTailSamples", _GenericFunc),
    ]


class IAudioProcessorObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IAudioProcessorVtbl))]


# ═══════════════════════════════════════════════════════════════
#  Vtable do IEditController
#  FUnknown (3) + IPluginBase (2: initialize, terminate) +
#  IEditController (13 métodos, na ordem real do header --
#  setComponentState, setState, getState, getParameterCount,
#  getParameterInfo, getParamStringByValue, getParamValueByString,
#  normalizedParamToPlain, plainParamToNormalized, getParamNormalized,
#  setParamNormalized, setComponentHandler, createView).
#  Só damos assinatura real pro que vamos chamar neste passo.
# ═══════════════════════════════════════════════════════════════

class ParameterInfo(ctypes.Structure):
    """ivsteditcontroller.h -- struct ParameterInfo (layout exato)."""
    _fields_ = [
        ("id", ctypes.c_uint32),
        ("title", ctypes.c_wchar * 128),
        ("shortTitle", ctypes.c_wchar * 128),
        ("units", ctypes.c_wchar * 128),
        ("stepCount", ctypes.c_int32),
        ("defaultNormalizedValue", ctypes.c_double),
        ("unitId", ctypes.c_int32),
        ("flags", ctypes.c_int32),
    ]


GetParameterCountFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p)
GetParameterInfoFunc = ctypes.WINFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ParameterInfo)
)


class IEditControllerVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("initialize", step2.InitializeFunc),
        ("terminate", step2.TerminateFunc),
        ("setComponentState", _GenericFunc),
        ("setState", _GenericFunc),
        ("getState", _GenericFunc),
        ("getParameterCount", GetParameterCountFunc),
        ("getParameterInfo", GetParameterInfoFunc),
        ("getParamStringByValue", _GenericFunc),
        ("getParamValueByString", _GenericFunc),
        ("normalizedParamToPlain", _GenericFunc),
        ("plainParamToNormalized", _GenericFunc),
        ("getParamNormalized", _GenericFunc),
        ("setParamNormalized", _GenericFunc),
        ("setComponentHandler", _GenericFunc),
        ("createView", _GenericFunc),
    ]


class IEditControllerObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IEditControllerVtbl))]


# ═══════════════════════════════════════════════════════════════
#  Lógica principal
# ═══════════════════════════════════════════════════════════════

def query_audio_processor(component_vtbl, component_self_ptr):
    """Passo 2 do enunciado: queryInterface(IAudioProcessor) no MESMO
    objeto do componente. Devolve (vtbl, self_ptr) ou (None, None) se
    o plugin não implementar essa interface nesse objeto."""
    obj_ptr = ctypes.c_void_p()
    hr = component_vtbl.queryInterface(component_self_ptr, ctypes.byref(IID_IAudioProcessor), ctypes.byref(obj_ptr))
    if hr != step1.kResultOk or not obj_ptr:
        print(f"  queryInterface(IAudioProcessor) falhou (hr={hr:#x}) -- plugin não processa áudio nesse objeto.")
        return None, None

    ap_ptr = ctypes.cast(obj_ptr, ctypes.POINTER(IAudioProcessorObj))
    ap_vtbl = ap_ptr.contents.lpVtbl.contents
    ap_self = ctypes.cast(ap_ptr, ctypes.c_void_p)
    print("  queryInterface(IAudioProcessor) OK.")

    can32 = ap_vtbl.canProcessSampleSize(ap_self, kSample32)
    print(f"  canProcessSampleSize(32-bit float) -> hr={can32:#x} ({'suportado' if can32 == step1.kResultOk else 'não suportado'})")

    latency = ap_vtbl.getLatencySamples(ap_self)
    print(f"  getLatencySamples() -> {latency} amostras")

    return ap_vtbl, ap_self


def get_or_create_controller(factory, component_vtbl, component_self_ptr, host_context):
    """Passo 4 do enunciado: instancia o Edit Controller separado, OU
    (se o plugin for SingleComponentEffect) pega ele via
    queryInterface no próprio objeto do componente.

    Devolve (vtbl, self_ptr, is_separate_object) -- is_separate_object
    indica se precisamos chamar terminate() nele depois (só objetos
    separados que a gente mesmo inicializou aqui)."""

    controller_cid = step1.TUID()
    hr = component_vtbl.getControllerClassId(component_self_ptr, ctypes.byref(controller_cid))
    has_separate_controller = hr == step1.kResultOk and any(controller_cid)

    if has_separate_controller:
        cid_hex = bytes(controller_cid).hex().upper()
        print(f"  Controller separado, CID={cid_hex} -- criando instância própria.")

        factory_vtbl = factory.contents.lpVtbl.contents
        factory_self = ctypes.cast(factory, ctypes.c_void_p)
        obj_ptr = ctypes.c_void_p()
        hr = factory_vtbl.createInstance(
            factory_self, bytes(controller_cid), bytes(IID_IEditController), ctypes.byref(obj_ptr)
        )
        if hr != step1.kResultOk or not obj_ptr:
            raise RuntimeError(f"createInstance(IEditController) falhou (hr={hr:#x})")

        ctrl_ptr = ctypes.cast(obj_ptr, ctypes.POINTER(IEditControllerObj))
        ctrl_vtbl = ctrl_ptr.contents.lpVtbl.contents
        ctrl_self = ctypes.cast(ctrl_ptr, ctypes.c_void_p)

        # É uma instância NOVA -- ninguém chamou initialize() nela
        # ainda, diferente do IComponent que o passo 2 já inicializou.
        hr = ctrl_vtbl.initialize(ctrl_self, host_context.ptr)
        if hr != step1.kResultOk:
            raise RuntimeError(f"initialize() do controller separado falhou (hr={hr:#x})")
        print("  initialize() do controller separado OK.")

        return ctrl_vtbl, ctrl_self, True

    else:
        print("  Sem controller separado (SingleComponentEffect) -- pegando IEditController do próprio componente.")
        obj_ptr = ctypes.c_void_p()
        hr = component_vtbl.queryInterface(
            component_self_ptr, ctypes.byref(IID_IEditController), ctypes.byref(obj_ptr)
        )
        if hr != step1.kResultOk or not obj_ptr:
            print(f"  queryInterface(IEditController) também falhou (hr={hr:#x}) -- esse plugin não expõe parâmetros por aqui.")
            return None, None, False

        ctrl_ptr = ctypes.cast(obj_ptr, ctypes.POINTER(IEditControllerObj))
        ctrl_vtbl = ctrl_ptr.contents.lpVtbl.contents
        ctrl_self = ctypes.cast(ctrl_ptr, ctypes.c_void_p)
        print("  queryInterface(IEditController) no próprio componente OK (não chama initialize() de novo).")

        return ctrl_vtbl, ctrl_self, False


def print_parameters(ctrl_vtbl, ctrl_self, max_params=10):
    count = ctrl_vtbl.getParameterCount(ctrl_self)
    print(f"  getParameterCount() -> {count} parâmetro(s)")
    for i in range(min(count, max_params)):
        info = ParameterInfo()
        hr = ctrl_vtbl.getParameterInfo(ctrl_self, i, ctypes.byref(info))
        if hr == step1.kResultOk:
            print(f"    [{i}] id={info.id} título={info.title!r} padrão={info.defaultNormalizedValue:.3f} steps={info.stepCount}")
        else:
            print(f"    [{i}] getParameterInfo falhou (hr={hr:#x})")
    if count > max_params:
        print(f"    ... e mais {count - max_params} parâmetro(s) não listado(s) aqui.")


def main():
    if len(sys.argv) < 2:
        print("Uso: python vst3_host_step3_processor_controller.py \"C:\\caminho\\pro\\Plugin.vst3\"")
        sys.exit(1)

    vst3_path = sys.argv[1]
    print(f"Carregando: {vst3_path}")

    dll, factory = step1.load_vst3_factory(vst3_path)
    classes = step1.list_classes(factory)
    audio_class = step2.find_audio_module_class(classes)
    print(f"Usando classe: nome={audio_class['name']!r} cid={audio_class['cid']}")

    component_ptr = step2.create_component(factory, audio_class["cid"])
    component_vtbl = component_ptr.contents.lpVtbl.contents
    component_self = ctypes.cast(component_ptr, ctypes.c_void_p)

    host_context = step2.MinimalHostContext()
    hr = component_vtbl.initialize(component_self, host_context.ptr)
    if hr != step1.kResultOk:
        raise RuntimeError(f"initialize() do componente falhou (hr={hr:#x})")
    print("Componente inicializado (IComponent.initialize OK).\n")

    print("Etapa 1: queryInterface(IAudioProcessor)")
    ap_vtbl, ap_self = query_audio_processor(component_vtbl, component_self)

    print("\nEtapa 2: Edit Controller")
    ctrl_vtbl, ctrl_self, ctrl_is_separate = get_or_create_controller(
        factory, component_vtbl, component_self, host_context
    )

    if ctrl_vtbl is not None:
        print("\nEtapa 3: parâmetros")
        print_parameters(ctrl_vtbl, ctrl_self)

    print("\nDesfazendo tudo...")

    # Cada queryInterface/createInstance devolveu uma referência com
    # addRef já feito -- cada uma precisa do release() correspondente.
    if ap_vtbl is not None:
        ap_vtbl.release(ap_self)
        print("  IAudioProcessor liberado.")

    if ctrl_vtbl is not None:
        if ctrl_is_separate:
            ctrl_vtbl.terminate(ctrl_self)
        ctrl_vtbl.release(ctrl_self)
        print(f"  IEditController liberado (terminate={'sim' if ctrl_is_separate else 'não, objeto compartilhado'}).")

    component_vtbl.terminate(component_self)
    component_vtbl.release(component_self)
    print("  IComponent terminado e liberado.")

    kernel32 = ctypes.windll.kernel32
    kernel32.FreeLibrary.argtypes = [step1.wintypes.HMODULE]
    kernel32.FreeLibrary.restype = step1.wintypes.BOOL
    kernel32.FreeLibrary(dll._handle)
    print("\nDLL liberada. Passo 3 concluído sem crash.")


if __name__ == "__main__":
    main()