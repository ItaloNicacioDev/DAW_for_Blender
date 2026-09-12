"""
vst3_host_step1_list_classes.py

PASSO 1 do host VST3 nativo (sem JUCE, sem dawdreamer, sem host externo).

O que esse script faz, e SÓ isso:
  1. Carrega o binário .vst3 via ctypes (é uma DLL comum no Windows,
     mesmo com essa extensão).
  2. Chama a função exportada `GetPluginFactory()` pra pegar o
     ponteiro da `IPluginFactory`.
  3. Lê a vtable dessa interface na mão (é assim que COM/VST3
     funciona: um ponteiro pra uma struct de ponteiros de função) e
     chama `countClasses()` + `getClassInfo()` pra listar os plugins
     que esse arquivo contém.

O que esse script NÃO faz ainda (vem nos próximos passos):
  - Não instancia o plugin (createInstance)
  - Não inicializa IComponent/IAudioProcessor (sem áudio ainda)
  - Não abre nenhuma janela (sem GUI ainda)

Por que começar tão pequeno: o binário do VST3 é baseado em vtables
com layout de struct EXATO definido pelo SDK da Steinberg. Se o
tamanho/ordem de qualquer campo aqui estiver errado, a chamada pode
simplesmente crashar o processo (com o interpretador do Python
junto) sem mensagem de erro nenhuma -- em vez de um traceback normal
do Python. Validar esse alicerce com o passo mais simples possível
(só ler metadados, sem criar nada) é a forma mais segura de garantir
que os fundamentos (carregar a DLL, ler a vtable, chamar uma função
COM) estão corretos antes de arriscar algo que mexe com áudio/janela
em tempo real.

USO:
    python vst3_host_step1_list_classes.py "C:\\Caminho\\Para\\O\\Plugin.vst3"

Se funcionar, vai imprimir uma lista com nome/categoria/CID de cada
classe de plugin dentro do arquivo. Se crashar (o processo fecha sem
nada, ou dá "Windows fatal exception: access violation"), me manda
exatamente essa mensagem -- ela sozinha já aponta qual struct está
com o layout errado.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


# ═══════════════════════════════════════════════════════════════
#  Tipos e constantes do SDK do VST3 (pluginterfaces/base/*.h)
# ═══════════════════════════════════════════════════════════════

# TUID = 16 bytes (é um GUID, só que representado como char[16] em vez
# de struct GUID nomeada -- mesmo layout binário).
TUID = ctypes.c_uint8 * 16

# tresult: int32. kResultOk = 0.
kResultOk = 0
kResultTrue = 0
kNoInterface = 0x80004002  # E_NOINTERFACE, mesmo valor do COM do Windows


def tuid_from_hex(hex_str: str) -> TUID:
    """Converte uma string hex de 32 caracteres (sem hífen) num TUID."""
    raw = bytes.fromhex(hex_str)
    assert len(raw) == 16
    return TUID(*raw)


# FUID da IPluginFactory -- vem direto do SDK (pluginterfaces/base/ipluginfactory.h):
#   DECLARE_CLASS_IID (IPluginFactory, 0x7A4D811C, 0x52114A1F, 0xAED9D2EE, 0x0B43BF9F)
#
# ATENÇÃO -- isso NÃO é simplesmente "4 uint32 little-endian colados".
# A macro INLINE_UID do SDK (funknown.h), quando COM_COMPATIBLE está
# definido (é o caso no Windows), empacota do jeito que um GUID do
# Windows é empacotado:
#   l1 -> 4 bytes little-endian                  (Data1)
#   l2 -> DUAS metades de 16 bits, cada little-endian (Data2 + Data3)
#   l3 -> 4 bytes BIG-endian, cru                 (Data4[0..3])
#   l4 -> 4 bytes BIG-endian, cru                 (Data4[4..7])
# Empacotar l2/l3/l4 como little-endian "normal" gera um TUID
# diferente do de verdade -- o plugin recusa a interface
# (E_NOINTERFACE) porque o IID simplesmente não bate.
def _uid_from_four_u32(a: int, b: int, c: int, d: int) -> TUID:
    raw = bytearray(16)
    raw[0:4] = a.to_bytes(4, "little")
    raw[4] = (b >> 16) & 0xFF
    raw[5] = (b >> 24) & 0xFF
    raw[6] = b & 0xFF
    raw[7] = (b >> 8) & 0xFF
    raw[8:12] = c.to_bytes(4, "big")
    raw[12:16] = d.to_bytes(4, "big")
    return TUID(*raw)


IID_IPluginFactory = _uid_from_four_u32(0x7A4D811C, 0x52114A1F, 0xAED9D2EE, 0x0B43BF9F)
IID_FUnknown = _uid_from_four_u32(0x00000000, 0x00000000, 0xC0000000, 0x00000046)


# ═══════════════════════════════════════════════════════════════
#  Structs do SDK (layout EXATO -- cuidado ao mexer aqui)
# ═══════════════════════════════════════════════════════════════

class PClassInfo(ctypes.Structure):
    """pluginterfaces/base/ipluginfactory.h -- struct PClassInfo.

    Layout original em C++:
        char8 cid[16];
        int32 cardinality;
        char8 category[32];
        char8 name[64];
    """
    _fields_ = [
        ("cid", ctypes.c_uint8 * 16),
        ("cardinality", ctypes.c_int32),
        ("category", ctypes.c_char * 32),
        ("name", ctypes.c_char * 64),
    ]


class PFactoryInfo(ctypes.Structure):
    """struct PFactoryInfo -- só usada aqui pra completude, não é
    estritamente necessária pra listar classes."""
    _fields_ = [
        ("vendor", ctypes.c_char * 64),
        ("url", ctypes.c_char * 256),
        ("email", ctypes.c_char * 128),
        ("flags", ctypes.c_int32),
    ]


# ═══════════════════════════════════════════════════════════════
#  Vtable da FUnknown (base de TODA interface VST3/COM)
# ═══════════════════════════════════════════════════════════════
#
# Toda interface COM (e VST3 é COM-like até no Windows) começa com
# essa mesma vtable de 3 ponteiros, nessa ordem exata:
#   queryInterface(iid: TUID*, obj: void**) -> tresult
#   addRef() -> uint32
#   release() -> uint32
#
# Interfaces derivadas (como IPluginFactory) só ADICIONAM métodos
# DEPOIS desses 3 -- nunca antes, nunca no meio.

QueryInterfaceFunc = ctypes.WINFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(TUID), ctypes.POINTER(ctypes.c_void_p)
)
AddRefFunc = ctypes.WINFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p)
ReleaseFunc = ctypes.WINFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p)

# Vtable da IPluginFactory: FUnknown (3) + 4 métodos próprios.
GetFactoryInfoFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(PFactoryInfo))
CountClassesFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p)
GetClassInfoFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(PClassInfo))
CreateInstanceFunc = ctypes.WINFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)
)


class IPluginFactoryVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", QueryInterfaceFunc),
        ("addRef", AddRefFunc),
        ("release", ReleaseFunc),
        ("getFactoryInfo", GetFactoryInfoFunc),
        ("countClasses", CountClassesFunc),
        ("getClassInfo", GetClassInfoFunc),
        ("createInstance", CreateInstanceFunc),
    ]


class IPluginFactoryObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IPluginFactoryVtbl))]


def resolve_vst3_binary(vst3_path: str) -> str:
    """Desde o SDK 3.6.10, um .vst3 normalmente NÃO é uma DLL solta --
    é um bundle (uma PASTA chamada Algo.vst3) com a DLL de verdade
    dentro de Contents/x86_64-win/Algo.vst3 (mesmo nome, mesma
    extensão, mas agora é arquivo).

    Passar o caminho da pasta pro LoadLibrary/WinDLL não dá "not
    found" -- dá exatamente WinError 5 (Acesso negado), porque o
    carregador tenta mapear a "pasta" como PE e falha. É isso que
    estava acontecendo aqui.
    """
    from pathlib import Path

    p = Path(vst3_path)

    if p.is_file():
        return str(p)  # formato antigo: já é a DLL direto

    if p.is_dir():
        for arch in ("x86_64-win", "x86-win"):
            candidate = p / "Contents" / arch / p.name
            if candidate.is_file():
                return str(candidate)
        raise FileNotFoundError(
            f"'{vst3_path}' é um bundle, mas não achei o binário em "
            f"Contents/x86_64-win/{p.name} nem Contents/x86-win/{p.name}. "
            f"Confira o conteúdo da pasta manualmente."
        )

    raise FileNotFoundError(f"'{vst3_path}' não existe.")


def load_vst3_factory(vst3_path: str):
    """Carrega o .vst3 e devolve (dll, factory_ptr) -- factory_ptr já
    é um IPluginFactoryObj* pronto pra chamar os métodos."""
    real_path = resolve_vst3_binary(vst3_path)
    print(f"Binário real resolvido: {real_path}")
    dll = ctypes.WinDLL(real_path)

    if not hasattr(dll, "GetPluginFactory"):
        raise RuntimeError(
            f"'{vst3_path}' não exporta GetPluginFactory() -- não é um "
            f"binário VST3 válido nesse formato, ou é um bundle "
            f"(pasta) e o binário de verdade está em outro caminho "
            f"dentro dele (ex.: Contents/x86_64-win/*.vst3)."
        )

    dll.GetPluginFactory.restype = ctypes.c_void_p
    dll.GetPluginFactory.argtypes = []

    raw_ptr = dll.GetPluginFactory()
    if not raw_ptr:
        raise RuntimeError("GetPluginFactory() devolveu NULL -- o plugin recusou fornecer a factory.")

    factory = ctypes.cast(raw_ptr, ctypes.POINTER(IPluginFactoryObj))
    return dll, factory


def list_classes(factory) -> list[dict]:
    vtbl = factory.contents.lpVtbl.contents
    self_ptr = ctypes.cast(factory, ctypes.c_void_p)

    count = vtbl.countClasses(self_ptr)
    results = []
    for i in range(count):
        info = PClassInfo()
        hr = vtbl.getClassInfo(self_ptr, i, ctypes.byref(info))
        if hr != kResultOk:
            results.append({"index": i, "error": f"getClassInfo falhou (hr={hr:#x})"})
            continue
        cid_hex = bytes(info.cid).hex().upper()
        results.append({
            "index": i,
            "cid": cid_hex,
            "cardinality": info.cardinality,
            "category": info.category.decode("utf-8", errors="replace"),
            "name": info.name.decode("utf-8", errors="replace"),
        })
    return results


def main():
    if len(sys.argv) < 2:
        print("Uso: python vst3_host_step1_list_classes.py \"C:\\caminho\\pro\\Plugin.vst3\"")
        sys.exit(1)

    vst3_path = sys.argv[1]
    print(f"Carregando: {vst3_path}")

    dll, factory = load_vst3_factory(vst3_path)
    print("GetPluginFactory() OK, factory obtida.")

    classes = list_classes(factory)
    print(f"\n{len(classes)} classe(s) encontrada(s):\n")
    for c in classes:
        if "error" in c:
            print(f"  [{c['index']}] ERRO: {c['error']}")
        else:
            print(f"  [{c['index']}] nome={c['name']!r} categoria={c['category']!r} cid={c['cid']}")


if __name__ == "__main__":
    main()