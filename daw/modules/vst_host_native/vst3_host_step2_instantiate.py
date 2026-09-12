"""
vst3_host_step2_instantiate.py

PASSO 2 do host VST3 nativo (continuação do vst3_host_step1_list_classes.py).

O que esse script faz, e SÓ isso:
  1. Reusa o passo 1 pra carregar a DLL e listar as classes do plugin.
  2. Acha a classe da categoria "Audio Module Class" (é o componente
     de processamento de áudio -- isso é PADRÃO da spec VST3, todo
     plugin em conformidade tem exatamente uma classe nessa categoria
     por "produto" dentro do arquivo, então essa lógica funciona pra
     QUALQUER .vst3, não só pro Serum).
  3. Chama createInstance() nessa classe pedindo a interface
     IComponent.
  4. Cria um "host context" mínimo (um objeto FUnknown implementado
     em Python via ctypes callbacks) e passa pro initialize() do
     plugin -- é obrigatório, todo plugin espera receber isso.
  5. Consulta getBusCount()/getBusInfo() pra listar os buses de
     áudio/eventos de entrada e saída (essencial pra uma DAW saber
     como rotear o plugin antes de processar qualquer áudio).
  6. Testa o ciclo setActive(True) -> setActive(False) -- valida que
     o plugin aceita ser ativado/desativado sem crashar.
  7. Chama terminate(), release() e libera a DLL (FreeLibrary).

O que esse script NÃO faz ainda (vem nos próximos passos):
  - Não conecta o IComponent num IAudioProcessor de verdade pra
    processar áudio (setupProcessing/process).
  - Não instancia o Edit Controller separado (quando o plugin usa um
    -- veja o aviso sobre getControllerClassId abaixo).
  - Não abre GUI.

SOBRE O "HOST CONTEXT": todo host VST3 real (Cubase, Reaper, etc.)
passa pro plugin um objeto que implementa FUnknown e, opcionalmente,
interfaces extras como IHostApplication, IPlugInterfaceSupport, etc.
Aqui implementamos o mínimo possível: um FUnknown que recusa
(kNoInterface) qualquer interface extra que o plugin peça. Isso é uma
resposta VÁLIDA segundo a spec -- a maioria dos plugins simplesmente
desliga funcionalidades opcionais que dependem dessas interfaces (ex:
alguns recursos de UI ou de nomeação de unidades) mas continua
funcionando normalmente pro que interessa numa DAW (áudio). Se no
futuro algum plugin específico exigir uma interface extra pra nem
inicializar, a gente implementa ela incrementalmente aqui.

USO:
    python vst3_host_step2_instantiate.py "C:\\Caminho\\Para\\O\\Plugin.vst3"

Se crashar sem traceback (o terminal simplesmente fecha ou mostra
"Windows fatal exception: access violation"), me manda a mensagem
exata -- assim como no passo 1, isso aponta um layout de struct
errado (mais provável: BusInfo, já que ela tem um char16[128] que é
fácil de errar o tamanho).
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

# Reusa tudo que já validamos no passo 1: resolve_vst3_binary,
# load_vst3_factory, list_classes, tuid_from_hex, TUID, kResultOk,
# kNoInterface, QueryInterfaceFunc, AddRefFunc, ReleaseFunc, etc.
# Precisa rodar este script na mesma pasta do passo 1.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vst3_host_step1_list_classes as step1  # noqa: E402


# ═══════════════════════════════════════════════════════════════
#  IIDs adicionais do SDK (pluginterfaces/vst/ivstcomponent.h)
# ═══════════════════════════════════════════════════════════════

# DECLARE_CLASS_IID (IComponent, 0xE831FF31, 0xF2D54301, 0x928EBBEE, 0x25697802)
IID_IComponent = step1._uid_from_four_u32(0xE831FF31, 0xF2D54301, 0x928EBBEE, 0x25697802)

# MediaTypes (pluginterfaces/vst/vsttypes.h)
kAudio = 0
kEvent = 1
MEDIA_TYPE_NAMES = {kAudio: "Audio", kEvent: "Event"}

# BusDirections
kInput = 0
kOutput = 1
BUS_DIRECTION_NAMES = {kInput: "Input", kOutput: "Output"}


# ═══════════════════════════════════════════════════════════════
#  Structs do SDK (layout EXATO)
# ═══════════════════════════════════════════════════════════════

class BusInfo(ctypes.Structure):
    """ivstcomponent.h -- struct BusInfo.

    Layout original em C++:
        MediaType  mediaType;     // int32
        BusDirection direction;   // int32
        int32      channelCount;
        String128  name;          // char16[128]  (UTF-16 no Windows)
        BusType    busType;       // int32
        uint32     flags;
    """
    _fields_ = [
        ("mediaType", ctypes.c_int32),
        ("direction", ctypes.c_int32),
        ("channelCount", ctypes.c_int32),
        ("name", ctypes.c_wchar * 128),  # wchar_t no Windows = 2 bytes = char16
        ("busType", ctypes.c_int32),
        ("flags", ctypes.c_uint32),
    ]


# ═══════════════════════════════════════════════════════════════
#  Vtable do IComponent
#
#  Ordem EXATA (herança linear em C++ = métodos concatenados na
#  vtable, nunca reordenados):
#    FUnknown (3):     queryInterface, addRef, release
#    IPluginBase (2):  initialize, terminate
#    IComponent (9):   getControllerClassId, setIoMode, getBusCount,
#                       getBusInfo, getRoutingInfo, activateBus,
#                       setActive, setState, getState
#
#  Só damos assinatura "de verdade" pros métodos que vamos chamar
#  neste passo. Os outros (getRoutingInfo, activateBus, setState,
#  getState) só precisam ocupar o slot certo na struct -- qualquer
#  ponteiro de função tem o mesmo tamanho, então um protótipo
#  genérico aqui não quebra nada desde que a gente não os chame.
# ═══════════════════════════════════════════════════════════════

InitializeFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)
TerminateFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p)
GetControllerClassIdFunc = ctypes.WINFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(step1.TUID)
)
SetIoModeFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32)
GetBusCountFunc = ctypes.WINFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32
)
GetBusInfoFunc = ctypes.WINFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32,
    ctypes.POINTER(BusInfo),
)
SetActiveFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint8)
# Slots que não vamos chamar neste passo -- protótipo genérico só pra
# manter o offset certo dos que vêm depois deles.
_GenericFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p)


class IComponentVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("initialize", InitializeFunc),
        ("terminate", TerminateFunc),
        ("getControllerClassId", GetControllerClassIdFunc),
        ("setIoMode", SetIoModeFunc),
        ("getBusCount", GetBusCountFunc),
        ("getBusInfo", GetBusInfoFunc),
        ("getRoutingInfo", _GenericFunc),
        ("activateBus", _GenericFunc),
        ("setActive", SetActiveFunc),
        ("setState", _GenericFunc),
        ("getState", _GenericFunc),
    ]


class IComponentObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IComponentVtbl))]


# ═══════════════════════════════════════════════════════════════
#  Host context mínimo (FUnknown implementado em Python)
# ═══════════════════════════════════════════════════════════════

class HostFUnknownVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
    ]


class HostFUnknownObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(HostFUnknownVtbl))]


class MinimalHostContext:
    """FUnknown mínimo que passamos pro initialize() do plugin.

    IMPORTANTE: guardamos os callbacks/structs como atributos da
    instância (self._qi, self._vtbl, self._obj, ...) e mantemos essa
    instância viva enquanto o plugin puder chamar de volta nela
    (até o terminate()). Se o Python coletar (GC) esses objetos
    antes da hora, o ponteiro de função vira lixo e o plugin crasha
    ao tentar chamar queryInterface -- por isso eles não são
    variáveis locais soltas em lugar nenhum.
    """

    def __init__(self):
        self._qi = step1.QueryInterfaceFunc(self._query_interface)
        self._ar = step1.AddRefFunc(self._add_ref)
        self._rel = step1.ReleaseFunc(self._release)
        self._vtbl = HostFUnknownVtbl(self._qi, self._ar, self._rel)
        self._obj = HostFUnknownObj(ctypes.pointer(self._vtbl))
        self.ptr = ctypes.cast(ctypes.pointer(self._obj), ctypes.c_void_p)

    def _query_interface(self, this, iid_ptr, obj_ptr_ptr):
        # Recusamos qualquer interface extra (IHostApplication, etc.)
        # por enquanto -- resposta válida pela spec.
        out = ctypes.cast(obj_ptr_ptr, ctypes.POINTER(ctypes.c_void_p))
        out[0] = None
        return step1.kNoInterface

    def _add_ref(self, this):
        return 1

    def _release(self, this):
        return 1


# ═══════════════════════════════════════════════════════════════
#  Lógica principal
# ═══════════════════════════════════════════════════════════════

def find_audio_module_class(classes: list[dict]) -> dict:
    """Acha a classe 'Audio Module Class' -- o componente de
    processamento de áudio. É genérico pra qualquer plugin em
    conformidade com a spec VST3 (não é algo específico do Serum)."""
    for c in classes:
        if c.get("category") == "Audio Module Class":
            return c
    raise RuntimeError(
        "Nenhuma classe 'Audio Module Class' encontrada -- esse "
        ".vst3 pode não ser um plugin de áudio válido, ou tem um "
        "formato inesperado."
    )


def create_component(factory, cid_hex: str) -> IComponentObj:
    vtbl = factory.contents.lpVtbl.contents
    self_ptr = ctypes.cast(factory, ctypes.c_void_p)

    cid_tuid = step1.tuid_from_hex(cid_hex)
    obj_ptr = ctypes.c_void_p()

    hr = vtbl.createInstance(
        self_ptr,
        bytes(cid_tuid),
        bytes(IID_IComponent),
        ctypes.byref(obj_ptr),
    )
    if hr != step1.kResultOk or not obj_ptr:
        raise RuntimeError(f"createInstance() falhou (hr={hr:#x}) pro CID {cid_hex}")

    return ctypes.cast(obj_ptr, ctypes.POINTER(IComponentObj))


def print_buses(component_vtbl, self_ptr):
    for media_type in (kAudio, kEvent):
        for direction in (kInput, kOutput):
            count = component_vtbl.getBusCount(self_ptr, media_type, direction)
            label = f"{MEDIA_TYPE_NAMES[media_type]} {BUS_DIRECTION_NAMES[direction]}"
            print(f"  {label}: {count} bus(es)")
            for i in range(count):
                info = BusInfo()
                hr = component_vtbl.getBusInfo(self_ptr, media_type, direction, i, ctypes.byref(info))
                if hr == step1.kResultOk:
                    print(f"    [{i}] nome={info.name!r} canais={info.channelCount} busType={info.busType} flags={info.flags:#x}")
                else:
                    print(f"    [{i}] getBusInfo falhou (hr={hr:#x})")


def main():
    if len(sys.argv) < 2:
        print("Uso: python vst3_host_step2_instantiate.py \"C:\\caminho\\pro\\Plugin.vst3\"")
        sys.exit(1)

    vst3_path = sys.argv[1]
    print(f"Carregando: {vst3_path}")

    dll, factory = step1.load_vst3_factory(vst3_path)
    print("GetPluginFactory() OK.")

    classes = step1.list_classes(factory)
    audio_class = find_audio_module_class(classes)
    print(f"\nUsando classe: nome={audio_class['name']!r} cid={audio_class['cid']}")

    component_ptr = create_component(factory, audio_class["cid"])
    component_vtbl = component_ptr.contents.lpVtbl.contents
    self_ptr = ctypes.cast(component_ptr, ctypes.c_void_p)
    print("createInstance(IComponent) OK.")

    # Guardamos a referência no escopo de main() pra ela sobreviver
    # até o fim (veja o aviso de GC na docstring da classe).
    host_context = MinimalHostContext()

    hr = component_vtbl.initialize(self_ptr, host_context.ptr)
    if hr != step1.kResultOk:
        raise RuntimeError(f"initialize() falhou (hr={hr:#x})")
    print("initialize() OK.")

    # Se o plugin usa um Edit Controller separado, esse CID não vem
    # zerado. Isso é só informativo por enquanto -- instanciar o
    # controller separado fica pro próximo passo.
    controller_cid = step1.TUID()
    hr = component_vtbl.getControllerClassId(self_ptr, ctypes.byref(controller_cid))
    if hr == step1.kResultOk and any(controller_cid):
        print(f"Plugin usa Edit Controller separado, CID={bytes(controller_cid).hex().upper()}")
    else:
        print("Plugin não declarou um Edit Controller separado (ou usa o próprio IComponent).")

    print("\nBuses:")
    print_buses(component_vtbl, self_ptr)

    print("\nTestando setActive(True) -> setActive(False)...")
    hr = component_vtbl.setActive(self_ptr, 1)
    print(f"  setActive(True)  -> hr={hr:#x}")
    hr = component_vtbl.setActive(self_ptr, 0)
    print(f"  setActive(False) -> hr={hr:#x}")

    hr = component_vtbl.terminate(self_ptr)
    print(f"\nterminate() -> hr={hr:#x}")

    ref_count = component_vtbl.release(self_ptr)
    print(f"release() -> refcount restante reportado={ref_count}")

    # windll.kernel32.FreeLibrary sem argtypes declarado assume um
    # int comum, que estoura em handles de 64 bits -- por isso o
    # OverflowError. HMODULE é do tamanho certo de ponteiro.
    kernel32 = ctypes.windll.kernel32
    kernel32.FreeLibrary.argtypes = [wintypes.HMODULE]
    kernel32.FreeLibrary.restype = wintypes.BOOL
    kernel32.FreeLibrary(dll._handle)
    print("\nDLL liberada. Passo 2 concluído sem crash.")


if __name__ == "__main__":
    main()