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
    python vst3_host_step4_open_gui.py "C:\\Program Files\\Common Files\\VST3\\Serum2.vst3"
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


# ═══════════════════════════════════════════════════════════════
#  Constantes / structs do Win32 puro (não é coisa do VST3)
# ═══════════════════════════════════════════════════════════════

WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WS_OVERLAPPEDWINDOW = 0x00CF0000
SW_SHOWNORMAL = 1
IDC_ARROW = 32512
COLOR_WINDOW_BRUSH = ctypes.cast(6, wintypes.HBRUSH)  # COLOR_WINDOW + 1

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
# ainda). Aqui a gente reaproveita a mesma vtable do passo 3 (mesmos
# 18 slots, mesma ordem) só trocando a assinatura do ÚLTIMO slot pra
# ter o restype certo (c_void_p, não int32).
CreateViewFunc = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)


class IEditControllerVtblFull(ctypes.Structure):
    _fields_ = list(step3.IEditControllerVtbl._fields_[:-1]) + [("createView", CreateViewFunc)]


class IEditControllerObjFull(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(IEditControllerVtblFull))]


kEditor = b"editor"  # ViewType::kEditor
kPlatformTypeHWND = b"HWND"


# ═══════════════════════════════════════════════════════════════
#  IPlugFrame mínimo (o "host context" da GUI): o plugin chama isso
#  quando quer redimensionar a própria janela.
# ═══════════════════════════════════════════════════════════════

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
    if len(sys.argv) < 2:
        print("Uso: python vst3_host_step4_open_gui.py \"C:\\caminho\\pro\\Plugin.vst3\"")
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
    print("Componente inicializado.")

    ctrl_vtbl, ctrl_self, ctrl_is_separate = step3.get_or_create_controller(
        factory, component_vtbl, component_self, host_context
    )

    def teardown_component_only():
        component_vtbl.terminate(component_self)
        component_vtbl.release(component_self)
        kernel32.FreeLibrary(dll._handle)

    if ctrl_vtbl is None:
        print("Esse plugin não expõe IEditController -- não dá pra abrir GUI.")
        teardown_component_only()
        return

    # Recasta pro tipo com createView() de verdade (restype certo).
    ctrl_full_ptr = ctypes.cast(ctrl_self, ctypes.POINTER(IEditControllerObjFull))
    ctrl_full_vtbl = ctrl_full_ptr.contents.lpVtbl.contents

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

    if ctrl_is_separate:
        ctrl_vtbl.terminate(ctrl_self)
    ctrl_vtbl.release(ctrl_self)

    teardown_component_only()
    print("Passo 4 concluído sem crash.")


if __name__ == "__main__":
    main()