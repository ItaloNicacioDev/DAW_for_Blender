"""
vst3_host_step4_open_gui.py

PASSO 4 do host VST3 nativo (continuação do step1 + step2 + step3).

O que esse script faz, e SÓ isso:
  1. Reusa passo 1 + passo 2 + passo 3 pra chegar num IEditController
     pronto (já cobrindo os dois casos: controller separado OU
     SingleComponentEffect -- é por isso que a gente importa e
     reaproveita step3.get_or_create_controller() em vez de duplicar
     essa lógica aqui).
  2. Chama createView("editor") no controller -- isso devolve um
     IPlugView* (ponteiro CRU, não é como os outros métodos que
     devolvem tresult; se o plugin não tiver editor gráfico, vem
     NULL e a gente para por aí, sem crashar).
  3. Confirma isPlatformTypeSupported("HWND") -- é o "tipo de
     janela" que o Windows usa; se o plugin só suportar outra
     plataforma (não deveria acontecer numa build Windows, mas a
     spec permite checar antes de assumir).
  4. Cria uma janela Win32 de verdade via ctypes (RegisterClassW +
     CreateWindowExW) -- SEM nenhuma biblioteca de GUI por fora,
     só a API do Windows crua, no mesmo espírito do resto do host.
  5. Implementa um IPlugFrame mínimo (do mesmo jeito que o passo 2/3
     implementou um FUnknown mínimo pro host context) -- é o objeto
     que o PLUGIN chama de volta quando quer redimensionar a própria
     janela (comum em plugins com GUI resizável, tipo o Serum). A
     gente redimensiona a janela host de verdade quando isso
     acontece.
  6. attached(hwnd, "HWND") -- embuti a GUI do plugin dentro da
     nossa janela.
  7. Roda um message loop Win32 normal (GetMessage/DispatchMessage)
     até a pessoa fechar a janela.
  8. Ao fechar: removed() -> release() da view -> terminate()/
     release() do controller (só terminate se for separado, mesma
     regra do passo 3) -> terminate()/release() do componente ->
     FreeLibrary().

IMPORTANTE sobre HWND em 64-bit: por padrão o ctypes assume que toda
função do user32/kernel32 devolve um int de 32 bits. Um HWND é do
tamanho de um ponteiro (64 bits) -- exatamente o mesmo tipo de bug
que já vimos no FreeLibrary do passo 2. Por isso este script declara
`argtypes`/`restype` explicitamente em CADA função do user32/kernel32
usada aqui, mesmo as óbvias.

O que esse script NÃO faz ainda:
  - Não processa áudio de verdade (setupProcessing/process) --
    então o plugin abre mas fica "mudo" (sem callback de áudio real
    alimentando ele). Isso fica pro próximo passo, junto com a
    conexão de fato num motor de áudio.

USO:
    python vst3_host_step4_open_gui.py "C:\\Caminho\\Para\\O\\Plugin.vst3"
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vst3_host_step1_list_classes as step1  # noqa: E402
import vst3_host_step2_instantiate as step2  # noqa: E402
import vst3_host_step3_processor_controller as step3  # noqa: E402


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Declarar argtypes/restype de TUDO que devolve ou recebe um HWND
# (ponteiro) -- sem isso, em 64-bit, ctypes trunca pra 32-bit e a
# janela vira lixo de memória (mesma classe de bug do FreeLibrary).
user32.RegisterClassW.argtypes = [ctypes.c_void_p]
user32.RegisterClassW.restype = ctypes.c_ushort  # ATOM

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_long

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UpdateWindow.argtypes = [wintypes.HWND]

user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = ctypes.c_long

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.PostQuitMessage.argtypes = [ctypes.c_int]

user32.AdjustWindowRectEx.argtypes = [ctypes.POINTER(wintypes.RECT), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT
]

user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadCursorW.restype = wintypes.HICON

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.FreeLibrary.argtypes = [wintypes.HMODULE]
kernel32.FreeLibrary.restype = wintypes.BOOL

# Muitos plugins com GUI customizada (skins desenhadas na mão, tipo o
# Serum) usam COM por baixo dos panos (Direct2D/DirectWrite/WIC) pra
# renderizar. Sem inicializar o COM na thread que chama createView(),
# a PRÓPRIA implementação do plugin recebe ponteiros NULL de volta de
# chamadas COM internas e crasha -- é exatamente o
# "access violation reading 0x0" que aparece se isso faltar.
ole32 = ctypes.windll.ole32
ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
ole32.CoInitializeEx.restype = ctypes.c_long
COINIT_APARTMENTTHREADED = 0x2
COINIT_DISABLE_OLE1DDE = 0x4


# ═══════════════════════════════════════════════════════════════
#  Constantes / structs do Win32 puro (não é coisa do VST3)
# ═══════════════════════════════════════════════════════════════

WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WS_CLIPCHILDREN = 0x02000000
WS_CLIPSIBLINGS = 0x04000000
WS_OVERLAPPEDWINDOW = 0x00CF0000 | WS_CLIPCHILDREN | WS_CLIPSIBLINGS
SW_SHOWNORMAL = 1
IDC_ARROW = 32512
COLOR_WINDOW_BRUSH = ctypes.cast(6, wintypes.HBRUSH)  # COLOR_WINDOW + 1

# [FIX GUI Serum 2 / plugins com renderização HiDPI] Sem declarar
# DPI-awareness do PROCESSO antes de qualquer janela existir, alguns
# plugins com GUI vetorial (Serum 2 é um exemplo conhecido) consultam
# a API de escala do Windows já dentro do próprio attached() pra
# montar o objeto interno de renderização -- se essa consulta falha
# (processo "DPI-unaware" == comportamento padrão do Python), esse
# objeto interno do PLUGIN fica com vtable nula, e a primeira chamada
# virtual nele derruba o processo com "access violation reading 0x..."
# (o offset bate com o slot da vtable, não com endereço 0 puro).
# Plugins com GUI simples/bitmap fixo nunca fazem essa consulta, por
# isso abrem normalmente sem esse fix.
try:
    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4 & (2**64 - 1))
    user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
    if not user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
        raise OSError("SetProcessDpiAwarenessContext falhou")
except (AttributeError, OSError):
    # Windows mais antigo sem Per-Monitor V2 -- cai pro fallback
    # "DPI aware" simples (melhor que nada).
    try:
        user32.SetProcessDPIAware()
    except AttributeError:
        pass

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HICON),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


def _wndproc_impl(hwnd, msg, wparam, lparam):
    if msg == WM_CLOSE:
        user32.DestroyWindow(hwnd)
        return 0
    if msg == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def create_host_window(client_w: int, client_h: int, title: str):
    """Cria uma janela Win32 comum. Devolve (hwnd, wndproc) -- o
    wndproc TEM que ser mantido vivo pelo chamador (mesmo motivo dos
    callbacks do host context: se o Python coletar essa referência,
    o Windows chama um ponteiro de função que não existe mais)."""
    h_instance = kernel32.GetModuleHandleW(None)
    class_name = "VST3HostStep4Window"

    wndproc = WNDPROC(_wndproc_impl)

    wc = WNDCLASSW()
    wc.style = 0
    wc.lpfnWndProc = wndproc
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = h_instance
    wc.hIcon = None
    wc.hCursor = user32.LoadCursorW(None, ctypes.cast(IDC_ARROW, wintypes.LPCWSTR))
    wc.hbrBackground = COLOR_WINDOW_BRUSH
    wc.lpszMenuName = None
    wc.lpszClassName = class_name

    atom = user32.RegisterClassW(ctypes.byref(wc))
    if not atom:
        raise ctypes.WinError(ctypes.get_last_error())

    outer = wintypes.RECT(0, 0, client_w, client_h)
    user32.AdjustWindowRectEx(ctypes.byref(outer), WS_OVERLAPPEDWINDOW, False, 0)
    outer_w = outer.right - outer.left
    outer_h = outer.bottom - outer.top

    hwnd = user32.CreateWindowExW(
        0, class_name, title, WS_OVERLAPPEDWINDOW,
        100, 100, outer_w, outer_h,
        None, None, h_instance, None,
    )
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())

    return hwnd, wndproc


def resize_host_window(hwnd, client_w: int, client_h: int):
    """Redimensiona a janela host pra ter exatamente client_w x
    client_h de ÁREA ÚTIL (descontando borda/titlebar)."""
    rect = wintypes.RECT(0, 0, client_w, client_h)
    user32.AdjustWindowRectEx(ctypes.byref(rect), WS_OVERLAPPEDWINDOW, False, 0)
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    user32.SetWindowPos(hwnd, None, 0, 0, w, h, SWP_NOMOVE | SWP_NOZORDER)


def run_message_loop():
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


# ═══════════════════════════════════════════════════════════════
#  Structs/vtables do VST3 (pluginterfaces/gui/iplugview.h)
# ═══════════════════════════════════════════════════════════════

class ViewRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_int32),
        ("top", ctypes.c_int32),
        ("right", ctypes.c_int32),
        ("bottom", ctypes.c_int32),
    ]


_GenericFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p)

IsPlatformTypeSupportedFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_char_p)
AttachedFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
RemovedFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p)
GetSizeFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(ViewRect))
OnSizeFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.POINTER(ViewRect))
SetFrameFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)
CanResizeFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p)


class IPlugViewVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("isPlatformTypeSupported", IsPlatformTypeSupportedFunc),
        ("attached", AttachedFunc),
        ("removed", RemovedFunc),
        ("onWheel", _GenericFunc),
        ("onKeyDown", _GenericFunc),
        ("onKeyUp", _GenericFunc),
        ("getSize", GetSizeFunc),
        ("onSize", OnSizeFunc),
        ("onFocus", _GenericFunc),
        ("setFrame", SetFrameFunc),
        ("canResize", CanResizeFunc),
        ("checkSizeConstraint", _GenericFunc),
    ]


class IPlugViewObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IPlugViewVtbl))]


ResizeViewFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ViewRect))


class IPlugFrameVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("resizeView", ResizeViewFunc),
    ]


class IPlugFrameObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IPlugFrameVtbl))]


# createView() devolve o ponteiro IPlugView* DIRETO (não é tresult
# via out-param como quase tudo no resto do SDK) -- por isso o passo
# 3 declarou esse slot como genérico (não sabíamos o restype certo
# ainda). setComponentState() também precisava de assinatura real
# (recebe um IBStream* -- o passo 3 só tinha o slot genérico porque
# ainda não processávamos estado). Aqui a gente reaproveita a mesma
# vtable do passo 3 (mesmos 18 slots, mesma ordem) só trocando a
# assinatura desses dois slots.
CreateViewFunc = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
SetComponentStateFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)
SetComponentHandlerFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)

_editcontroller_fields = list(step3.IEditControllerVtbl._fields_)
_editcontroller_fields[5] = ("setComponentState", SetComponentStateFunc)  # confirmado pelo índice: qi,ar,rel,init,term,setComponentState,...
_editcontroller_fields[16] = ("setComponentHandler", SetComponentHandlerFunc)
_editcontroller_fields[-1] = ("createView", CreateViewFunc)


class IEditControllerVtblFull(ctypes.Structure):
    _fields_ = _editcontroller_fields


class IEditControllerObjFull(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IEditControllerVtblFull))]


kEditor = b"editor"  # ViewType::kEditor
kPlatformTypeHWND = b"HWND"


# O passo 2 declarou getState()/setState() do IComponent como slot
# genérico (não processávamos estado ainda). Igual fizemos com o
# IEditController acima, reaproveitamos a vtable original só
# corrigindo a assinatura do slot que vamos chamar de verdade.
GetStateFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)

_component_fields = list(step2.IComponentVtbl._fields_)
_component_fields[13] = ("getState", GetStateFunc)  # qi,ar,rel,init,term,getControllerClassId,setIoMode,getBusCount,getBusInfo,getRoutingInfo,activateBus,setActive,setState,getState


class IComponentVtblFull(ctypes.Structure):
    _fields_ = _component_fields


class IComponentObjFull(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IComponentVtblFull))]


# ═══════════════════════════════════════════════════════════════
#  IConnectionPoint (pluginterfaces/vst/ivstmessage.h) -- conecta o
#  IComponent e o IEditController quando são objetos SEPARADOS. Sem
#  isso os dois ficam "cegos" um pro outro; vários plugins (Serum
#  incluso) esperam essa conexão antes de montar a GUI.
# ═══════════════════════════════════════════════════════════════

# DECLARE_CLASS_IID (IConnectionPoint, 0x70A4156F, 0x6E6E4026, 0x989148BF, 0xAA60D8D1)
IID_IConnectionPoint = step1._uid_from_four_u32(0x70A4156F, 0x6E6E4026, 0x989148BF, 0xAA60D8D1)

ConnectFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)
DisconnectFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)
NotifyFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)


class IConnectionPointVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("connect", ConnectFunc),
        ("disconnect", DisconnectFunc),
        ("notify", NotifyFunc),
    ]


class IConnectionPointObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IConnectionPointVtbl))]


# ═══════════════════════════════════════════════════════════════
#  IBStream (pluginterfaces/base/ibstream.h) -- implementado do lado
#  do HOST (em memória, com um bytearray) pra servir de "correio"
#  entre component.getState() e controller.setComponentState(). É
#  assim que hosts de verdade sincronizam o estado antes de abrir a
#  GUI -- sem isso, o controller não sabe o preset/valores atuais.
# ═══════════════════════════════════════════════════════════════

# DECLARE_CLASS_IID (IBStream, 0xC3BF6EA2, 0x30994752, 0x9B6BF990, 0x1EE33E9B)
IID_IBStream = step1._uid_from_four_u32(0xC3BF6EA2, 0x30994752, 0x9B6BF990, 0x1EE33E9B)

kIBSeekSet, kIBSeekCur, kIBSeekEnd = 0, 1, 2

ReadFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p)
WriteFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p)
SeekFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int32, ctypes.c_void_p)
TellFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)


class IBStreamVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("read", ReadFunc),
        ("write", WriteFunc),
        ("seek", SeekFunc),
        ("tell", TellFunc),
    ]


class IBStreamObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IBStreamVtbl))]


class MemoryBStream:
    """IBStream em memória, do lado do host. Mesmo padrão dos outros
    objetos mínimos (host context, plug frame): guarda os callbacks
    vivos como atributos da instância."""

    def __init__(self):
        self._buf = bytearray()
        self._pos = 0

        self._qi = step1.QueryInterfaceFunc(self._query_interface)
        self._ar = step1.AddRefFunc(self._add_ref)
        self._rel = step1.ReleaseFunc(self._release)
        self._read = ReadFunc(self._read_impl)
        self._write = WriteFunc(self._write_impl)
        self._seek = SeekFunc(self._seek_impl)
        self._tell = TellFunc(self._tell_impl)
        self._vtbl = IBStreamVtbl(self._qi, self._ar, self._rel, self._read, self._write, self._seek, self._tell)
        self._obj = IBStreamObj(ctypes.pointer(self._vtbl))
        self.ptr = ctypes.cast(ctypes.pointer(self._obj), ctypes.c_void_p)

    def _query_interface(self, this, iid_ptr, obj_ptr_ptr):
        out = ctypes.cast(obj_ptr_ptr, ctypes.POINTER(ctypes.c_void_p))
        out[0] = None
        return step1.kNoInterface

    def _add_ref(self, this):
        return 1

    def _release(self, this):
        return 1

    def _read_impl(self, this, buffer, num_bytes, num_bytes_read_ptr):
        available = len(self._buf) - self._pos
        to_read = max(0, min(num_bytes, available))
        if to_read > 0 and buffer:
            chunk = bytes(self._buf[self._pos:self._pos + to_read])
            ctypes.memmove(buffer, chunk, to_read)
            self._pos += to_read
        if num_bytes_read_ptr:
            ctypes.cast(num_bytes_read_ptr, ctypes.POINTER(ctypes.c_int32))[0] = to_read
        return step1.kResultOk

    def _write_impl(self, this, buffer, num_bytes, num_bytes_written_ptr):
        chunk = ctypes.string_at(buffer, num_bytes) if buffer and num_bytes > 0 else b""
        end = self._pos + len(chunk)
        if end > len(self._buf):
            self._buf.extend(b"\x00" * (end - len(self._buf)))
        self._buf[self._pos:end] = chunk
        self._pos = end
        if num_bytes_written_ptr:
            ctypes.cast(num_bytes_written_ptr, ctypes.POINTER(ctypes.c_int32))[0] = len(chunk)
        return step1.kResultOk

    def _seek_impl(self, this, pos, mode, result_ptr):
        if mode == kIBSeekSet:
            new_pos = pos
        elif mode == kIBSeekCur:
            new_pos = self._pos + pos
        elif mode == kIBSeekEnd:
            new_pos = len(self._buf) + pos
        else:
            return 0x80004005  # E_FAIL -- modo desconhecido
        self._pos = max(0, new_pos)
        if result_ptr:
            ctypes.cast(result_ptr, ctypes.POINTER(ctypes.c_int64))[0] = self._pos
        return step1.kResultOk

    def _tell_impl(self, this, pos_ptr):
        if pos_ptr:
            ctypes.cast(pos_ptr, ctypes.POINTER(ctypes.c_int64))[0] = self._pos
        return step1.kResultOk

    def rewind(self):
        self._pos = 0


# ═══════════════════════════════════════════════════════════════
#  IHostApplication (pluginterfaces/vst/ivsthostapplication.h) -- é
#  isso que é passado como 'context' pro initialize() do componente
#  e do controller. O host context mínimo do passo 2 (MinimalHostContext)
#  recusava TUDO via queryInterface, inclusive isso -- alguns plugins
#  guardam o resultado dessa consulta e usam (ex: pra mostrar o nome
#  do host, ou pra criar objetos auxiliares) já durante a montagem da
#  GUI, sem checar null antes. Aqui implementamos o mínimo (getName +
#  createInstance) igual um host de verdade faria.
# ═══════════════════════════════════════════════════════════════

# DECLARE_CLASS_IID (IHostApplication, 0x58E595CC, 0xDB2D4969, 0x8B6AAF8C, 0x36A664E5)
IID_IHostApplication = step1._uid_from_four_u32(0x58E595CC, 0xDB2D4969, 0x8B6AAF8C, 0x36A664E5)

GetNameFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p)
HostCreateInstanceFunc = ctypes.WINFUNCTYPE(
    ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
)


class IHostApplicationVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("getName", GetNameFunc),
        ("createInstance", HostCreateInstanceFunc),
    ]


class IHostApplicationObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IHostApplicationVtbl))]


class HostApplicationContext:
    """Substitui o MinimalHostContext do passo 2. A MESMA vtable
    serve tanto pra ser passada como 'context' (que é só um FUnknown)
    quanto pra ser devolvida quando o plugin pergunta especificamente
    por IHostApplication -- IHostApplication só ACRESCENTA métodos
    depois de FUnknown, não redefine nada, então um objeto só resolve
    os dois papéis."""

    def __init__(self, name="Native VST3 Host (Python)"):
        self._name = name
        self._qi = step1.QueryInterfaceFunc(self._query_interface)
        self._ar = step1.AddRefFunc(self._add_ref)
        self._rel = step1.ReleaseFunc(self._release)
        self._get_name = GetNameFunc(self._get_name_impl)
        self._create_instance = HostCreateInstanceFunc(self._create_instance_impl)
        self._vtbl = IHostApplicationVtbl(self._qi, self._ar, self._rel, self._get_name, self._create_instance)
        self._obj = IHostApplicationObj(ctypes.pointer(self._vtbl))
        self.ptr = ctypes.cast(ctypes.pointer(self._obj), ctypes.c_void_p)

    def _query_interface(self, this, iid_ptr, obj_ptr_ptr):
        requested = bytes(iid_ptr.contents)
        out = ctypes.cast(obj_ptr_ptr, ctypes.POINTER(ctypes.c_void_p))
        if requested in (bytes(IID_IHostApplication), bytes(step1.IID_FUnknown)):
            out[0] = this
            return step1.kResultOk
        out[0] = None
        return step1.kNoInterface

    def _add_ref(self, this):
        return 1

    def _release(self, this):
        return 1

    def _get_name_impl(self, this, name_buf_ptr):
        if name_buf_ptr:
            text = self._name[:127]
            buf = (ctypes.c_wchar * 128).from_address(name_buf_ptr)
            for i, ch in enumerate(text):
                buf[i] = ch
            buf[len(text)] = "\x00"
        return step1.kResultOk

    def _create_instance_impl(self, this, cid, iid, obj_ptr_ptr):
        # Não implementamos criação de objetos do lado do host ainda
        # (IMessage, IAttributeList) -- devolve "não implementado".
        out = ctypes.cast(obj_ptr_ptr, ctypes.POINTER(ctypes.c_void_p))
        out[0] = None
        return 0x80004001  # kNotImplemented


# ═══════════════════════════════════════════════════════════════
#  IComponentHandler (pluginterfaces/vst/ivsteditcontroller.h) -- o
#  controller espera um handler setado ANTES do createView(); vários
#  frameworks de GUI consultam esse ponteiro já na construção da
#  view. beginEdit/performEdit/endEdit só confirmamos (não aplicamos
#  a mudança de verdade ainda -- isso é o próximo passo, conectar num
#  motor de áudio real).
# ═══════════════════════════════════════════════════════════════

# DECLARE_CLASS_IID (IComponentHandler, 0x93A0BEA3, 0x0BD045DB, 0x8E890B0C, 0xC1E46AC6)
IID_IComponentHandler = step1._uid_from_four_u32(0x93A0BEA3, 0x0BD045DB, 0x8E890B0C, 0xC1E46AC6)

BeginEditFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32)
PerformEditFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_double)
EndEditFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32)
RestartComponentFunc = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32)


class IComponentHandlerVtbl(ctypes.Structure):
    _fields_ = [
        ("queryInterface", step1.QueryInterfaceFunc),
        ("addRef", step1.AddRefFunc),
        ("release", step1.ReleaseFunc),
        ("beginEdit", BeginEditFunc),
        ("performEdit", PerformEditFunc),
        ("endEdit", EndEditFunc),
        ("restartComponent", RestartComponentFunc),
    ]


class IComponentHandlerObj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IComponentHandlerVtbl))]


class HostComponentHandler:
    def __init__(self):
        self._qi = step1.QueryInterfaceFunc(self._query_interface)
        self._ar = step1.AddRefFunc(self._add_ref)
        self._rel = step1.ReleaseFunc(self._release)
        self._begin = BeginEditFunc(self._begin_edit)
        self._perform = PerformEditFunc(self._perform_edit)
        self._end = EndEditFunc(self._end_edit)
        self._restart = RestartComponentFunc(self._restart_component)
        self._vtbl = IComponentHandlerVtbl(self._qi, self._ar, self._rel, self._begin, self._perform, self._end, self._restart)
        self._obj = IComponentHandlerObj(ctypes.pointer(self._vtbl))
        self.ptr = ctypes.cast(ctypes.pointer(self._obj), ctypes.c_void_p)

    def _query_interface(self, this, iid_ptr, obj_ptr_ptr):
        out = ctypes.cast(obj_ptr_ptr, ctypes.POINTER(ctypes.c_void_p))
        out[0] = None
        return step1.kNoInterface

    def _add_ref(self, this):
        return 1

    def _release(self, this):
        return 1

    def _begin_edit(self, this, param_id):
        return step1.kResultOk

    def _perform_edit(self, this, param_id, value_normalized):
        return step1.kResultOk

    def _end_edit(self, this, param_id):
        return step1.kResultOk

    def _restart_component(self, this, flags):
        print(f"  [IComponentHandler] plugin pediu restartComponent(flags={flags:#x}) -- reconhecido, ainda não tratado.")
        return step1.kResultOk




class HostPlugFrame:
    def __init__(self, hwnd):
        self.hwnd = hwnd
        # Setados depois de createView() -- precisa pra chamar
        # view->onSize() confirmando o novo tamanho pro plugin.
        self.view_vtbl = None
        self.view_self = None

        self._qi = step1.QueryInterfaceFunc(self._query_interface)
        self._ar = step1.AddRefFunc(self._add_ref)
        self._rel = step1.ReleaseFunc(self._release)
        self._resize = ResizeViewFunc(self._resize_view)
        self._vtbl = IPlugFrameVtbl(self._qi, self._ar, self._rel, self._resize)
        self._obj = IPlugFrameObj(ctypes.pointer(self._vtbl))
        self.ptr = ctypes.cast(ctypes.pointer(self._obj), ctypes.c_void_p)

    def _query_interface(self, this, iid_ptr, obj_ptr_ptr):
        out = ctypes.cast(obj_ptr_ptr, ctypes.POINTER(ctypes.c_void_p))
        out[0] = None
        return step1.kNoInterface

    def _add_ref(self, this):
        return 1

    def _release(self, this):
        return 1

    def _resize_view(self, this, view_ptr, new_size_ptr):
        new_size = new_size_ptr.contents
        w = new_size.right - new_size.left
        h = new_size.bottom - new_size.top
        print(f"  [IPlugFrame] plugin pediu resize pra {w}x{h}")
        resize_host_window(self.hwnd, w, h)
        if self.view_vtbl is not None:
            self.view_vtbl.onSize(self.view_self, new_size_ptr)
        return step1.kResultOk


# ═══════════════════════════════════════════════════════════════
#  Lógica principal
# ═══════════════════════════════════════════════════════════════

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        print("Uso: python vst3_host_step4_open_gui.py \"C:\\caminho\\pro\\Plugin.vst3\" [--no-state-sync] [--no-connection-point]")
        sys.exit(1)

    vst3_path = args[0]
    skip_state_sync = "--no-state-sync" in flags
    skip_connection_point = "--no-connection-point" in flags
    print(f"Carregando: {vst3_path}")
    if skip_state_sync:
        print("[debug] pulando getState()/setComponentState() -- teste de isolamento")
    if skip_connection_point:
        print("[debug] pulando connect() do IConnectionPoint -- teste de isolamento")

    hr_co = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE)
    co_initialized = hr_co in (0, 1)  # S_OK ou S_FALSE (já inicializado igual)
    if hr_co not in (0, 1):
        print(f"Aviso: CoInitializeEx devolveu hr={hr_co:#x} -- seguindo mesmo assim.")

    try:
        _main_body(vst3_path, skip_state_sync=skip_state_sync, skip_connection_point=skip_connection_point)
    finally:
        if co_initialized:
            ole32.CoUninitialize()


def _main_body(vst3_path: str, skip_state_sync: bool = False, skip_connection_point: bool = False):
    dll, factory = step1.load_vst3_factory(vst3_path)
    classes = step1.list_classes(factory)
    audio_class = step2.find_audio_module_class(classes)
    print(f"Usando classe: nome={audio_class['name']!r} cid={audio_class['cid']}")

    component_ptr = step2.create_component(factory, audio_class["cid"])
    component_vtbl = component_ptr.contents.lpVtbl.contents
    component_self = ctypes.cast(component_ptr, ctypes.c_void_p)

    host_context = HostApplicationContext()
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
        print("Esse plugin não expõe IEditController -- não dá pra abrir GUI.")
        teardown_component_only()
        return

    # Recasta pros tipos com assinatura real (getState, setComponentState, createView).
    ctrl_full_ptr = ctypes.cast(ctrl_self, ctypes.POINTER(IEditControllerObjFull))
    ctrl_full_vtbl = ctrl_full_ptr.contents.lpVtbl.contents
    component_full_ptr = ctypes.cast(component_self, ctypes.POINTER(IComponentObjFull))
    component_full_vtbl = component_full_ptr.contents.lpVtbl.contents

    connected = False
    comp_cp_vtbl = comp_cp_self = ctrl_cp_vtbl = ctrl_cp_self = None
    if ctrl_is_separate:
        # Handshake padrão que hosts de verdade fazem antes de abrir
        # a GUI: conectar os dois objetos via IConnectionPoint, e
        # sincronizar o estado atual do componente no controller.
        # Sem isso, alguns plugins (Serum incluso) crasham dentro do
        # próprio createView() porque a GUI deles lê dados que só
        # existem depois desse handshake.
        comp_cp_vtbl = comp_cp_self = ctrl_cp_vtbl = ctrl_cp_self = None
        if skip_connection_point:
            print("\n[debug] pulando conexão IComponent <-> IEditController (--no-connection-point).")
        else:
            print("\nConectando IComponent <-> IEditController...")
            comp_cp_obj = ctypes.c_void_p()
            hr_comp_cp = component_vtbl.queryInterface(component_self, ctypes.byref(IID_IConnectionPoint), ctypes.byref(comp_cp_obj))
            ctrl_cp_obj = ctypes.c_void_p()
            hr_ctrl_cp = ctrl_vtbl.queryInterface(ctrl_self, ctypes.byref(IID_IConnectionPoint), ctypes.byref(ctrl_cp_obj))

            if hr_comp_cp == step1.kResultOk and hr_ctrl_cp == step1.kResultOk:
                comp_cp_ptr = ctypes.cast(comp_cp_obj, ctypes.POINTER(IConnectionPointObj))
                comp_cp_vtbl = comp_cp_ptr.contents.lpVtbl.contents
                comp_cp_self = ctypes.cast(comp_cp_ptr, ctypes.c_void_p)

                ctrl_cp_ptr = ctypes.cast(ctrl_cp_obj, ctypes.POINTER(IConnectionPointObj))
                ctrl_cp_vtbl = ctrl_cp_ptr.contents.lpVtbl.contents
                ctrl_cp_self = ctypes.cast(ctrl_cp_ptr, ctypes.c_void_p)

                hr1 = comp_cp_vtbl.connect(comp_cp_self, ctrl_cp_self)
                hr2 = ctrl_cp_vtbl.connect(ctrl_cp_self, comp_cp_self)
                print(f"  connect() -> componente={hr1:#x} controller={hr2:#x}")
                connected = hr1 == step1.kResultOk and hr2 == step1.kResultOk
            else:
                print("  Esse plugin não suporta IConnectionPoint -- pulando (comum em plugins mais simples).")

        if skip_state_sync:
            print("[debug] pulando getState()/setComponentState() (--no-state-sync).")
        else:
            print("Sincronizando estado (component.getState -> controller.setComponentState)...")
            state_stream = MemoryBStream()
            hr_get = component_full_vtbl.getState(component_self, state_stream.ptr)
            if hr_get == step1.kResultOk:
                state_stream.rewind()
                hr_set = ctrl_full_vtbl.setComponentState(ctrl_self, state_stream.ptr)
                print(f"  getState() -> hr={hr_get:#x} ({len(state_stream._buf)} bytes), setComponentState() -> hr={hr_set:#x}")
            else:
                print(f"  getState() falhou (hr={hr_get:#x}) -- seguindo sem sincronizar estado.")

    print("\nsetComponentHandler()...")
    handler = HostComponentHandler()
    hr_handler = ctrl_full_vtbl.setComponentHandler(ctrl_self, handler.ptr)
    print(f"  setComponentHandler() -> hr={hr_handler:#x}")

    view_ptr_raw = ctrl_full_vtbl.createView(ctrl_self, kEditor)
    if not view_ptr_raw:
        print("createView('editor') devolveu NULL -- esse plugin não tem editor gráfico.")
        if ctrl_is_separate:
            ctrl_vtbl.terminate(ctrl_self)
        ctrl_vtbl.release(ctrl_self)
        teardown_component_only()
        return

    view_ptr = ctypes.cast(view_ptr_raw, ctypes.POINTER(IPlugViewObj))
    view_vtbl = view_ptr.contents.lpVtbl.contents
    view_self = ctypes.cast(view_ptr, ctypes.c_void_p)
    print("createView('editor') OK.")

    supported = view_vtbl.isPlatformTypeSupported(view_self, kPlatformTypeHWND)
    print(f"isPlatformTypeSupported('HWND') -> hr={supported:#x}")
    if supported != step1.kResultOk:
        raise RuntimeError("Esse plugin não suporta HWND nessa build.")

    size = ViewRect()
    view_vtbl.getSize(view_self, ctypes.byref(size))
    w, h = size.right - size.left, size.bottom - size.top
    print(f"Tamanho inicial do editor: {w}x{h}")

    hwnd, wndproc_keepalive = create_host_window(w, h, audio_class["name"])
    resize_host_window(hwnd, w, h)

    frame = HostPlugFrame(hwnd)
    hr = view_vtbl.setFrame(view_self, frame.ptr)
    print(f"setFrame() -> hr={hr:#x}")

    hr = view_vtbl.attached(view_self, ctypes.c_void_p(hwnd), kPlatformTypeHWND)
    print(f"attached() -> hr={hr:#x}")
    if hr != step1.kResultOk:
        raise RuntimeError(f"attached() falhou (hr={hr:#x})")

    # Só depois do attached() dar certo que faz sentido o frame
    # conseguir chamar view->onSize() em resizes futuros.
    frame.view_vtbl = view_vtbl
    frame.view_self = view_self

    user32.ShowWindow(hwnd, SW_SHOWNORMAL)
    user32.UpdateWindow(hwnd)

    print("\nJanela aberta -- feche a janela do plugin pra continuar (e desfazer tudo direito).")
    run_message_loop()

    print("\nJanela fechada, desfazendo tudo...")
    view_vtbl.removed(view_self)
    view_vtbl.release(view_self)

    if connected:
        comp_cp_vtbl.disconnect(comp_cp_self, ctrl_cp_self)
        ctrl_cp_vtbl.disconnect(ctrl_cp_self, comp_cp_self)
        comp_cp_vtbl.release(comp_cp_self)
        ctrl_cp_vtbl.release(ctrl_cp_self)
        print("  IConnectionPoint desconectado.")

    if ctrl_is_separate:
        ctrl_vtbl.terminate(ctrl_self)
    ctrl_vtbl.release(ctrl_self)

    teardown_component_only()
    print("Passo 4 concluído sem crash.")


if __name__ == "__main__":
    main()