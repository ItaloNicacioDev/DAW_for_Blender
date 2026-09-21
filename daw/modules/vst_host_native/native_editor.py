"""
native_editor.py

Conserto da GUI dos plugins dentro do Blender.

O PROBLEMA
----------
`native_host.open_editor()` abre a janela do plugin numa THREAD
dedicada (`_editor_thread`), com message loop próprio. Isso funciona
no demo standalone dos steps (onde a thread é dona do processo), mas
dentro do Blender dá exatamente o que você viu: trava, não desenha,
e às vezes derruba o Blender inteiro. Três causas somadas:

  1. GUI de plugin NÃO é thread-safe. VSTGUI/JUCE (Vital, Serum,
     Cymatics, praticamente todos) assumem que `createView()`,
     `attached()` e o message loop acontecem na MESMA thread de UI do
     host. JUCE em particular tem um MessageManager global preso à
     primeira thread que ele viu -- que é a thread principal do
     Blender, porque o plugin já foi carregado por ela. Chamar
     `attached()` de outra thread = deadlock ou access violation.

  2. `step4.create_host_window()` registra a classe Win32 com nome
     FIXO ("VST3HostStep4Window"). Na segunda vez que você abre um
     editor, `RegisterClassW` falha com ERROR_CLASS_ALREADY_EXISTS
     (1410), o `raise ctypes.WinError(...)` estoura dentro da thread,
     o `open_editor()` devolve False e o Blender fica esperando o
     `ready.wait(timeout=10.0)` -- 10 segundos de tela congelada.

  3. O wndproc do step4 chama `PostQuitMessage(0)` no WM_DESTROY.
     No demo isso é o certo (encerra o loop). Dentro do Blender, um
     WM_QUIT na fila da thread principal é lido pelo GHOST como
     "fechar o programa" -- é literalmente o Blender fechando quando
     você fecha a janela do plugin.

A SOLUÇÃO
---------
Abrir o editor na THREAD PRINCIPAL do Blender e deixar o próprio
loop de mensagens do Blender (GHOST já faz PeekMessage/Dispatch em
todas as janelas do processo) alimentar a janela do plugin. Não
precisa de message loop nosso, não precisa de modal operator:

  - `createView()` / `attached()` rodam na thread que chamou (a mesma
    que carregou o plugin);
  - classe de janela com nome ÚNICO por sessão;
  - wndproc SEM `PostQuitMessage` -- só marca "fechei" e destrói a
    janela;
  - um `bpy.app.timers` levinho (0.25 s) só pra perceber que a janela
    foi fechada e desmontar a sessão (parar motor de áudio, liberar
    a view) na thread principal também.

O motor de áudio ao vivo (`LiveAudioEngine`) CONTINUA em thread
separada -- lá é o lugar certo dele, áudio não pode depender do
loop de UI.

COMO USAR
---------
Coloque este arquivo em `modules/vst_host_native/` e chame `install()`
uma vez. O lugar natural é no fim de `modules/vst/native_engine.py`,
logo depois do `from native_host import VST3PluginInstance`:

    import native_editor  # noqa: E402
    native_editor.install()

`install()` substitui `open_editor` / `close_editor` / `is_editor_open`
da `VST3PluginInstance` -- o resto do addon (`vst.py`, `operators.py`,
`mixer/operators.py`, piano roll) não muda nada, inclusive
`trigger_live_note()`, porque continuamos preenchendo
`_live_engine` / `_live_event_list` na instância.
"""

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vst3_host_step1_list_classes as step1  # noqa: E402
import vst3_host_step4_open_gui as step4  # noqa: E402
import vst3_host_step5_process_audio as step5  # noqa: E402
import vst3_host_step6_midi_input as step6  # noqa: E402
import native_host  # noqa: E402

user32 = step4.user32
kernel32 = step4.kernel32

# Funções que os passos anteriores não precisavam declarar. Sem
# argtypes/restype, HWND de 64 bits volta truncado em 32 e vira
# "janela que não existe".
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
user32.UnregisterClassW.restype = wintypes.BOOL
user32.GetActiveWindow.argtypes = []
user32.GetActiveWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint32, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
kernel32.GetLastError.argtypes = []
kernel32.GetLastError.restype = wintypes.DWORD

ERROR_CLASS_ALREADY_EXISTS = 1410
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004

_sessions: "list[EditorSession]" = []
_class_counter = 0
_timer_installed = False


# ═══════════════════════════════════════════════════════════════
#  Sessão de editor -- uma janela + uma view + (opcional) motor de
#  áudio ao vivo. TUDO criado e destruído na thread principal.
# ═══════════════════════════════════════════════════════════════

class EditorSession:

    def __init__(self, inst: "native_host.VST3PluginInstance"):
        self.inst = inst
        self.hwnd = None
        self.view_vtbl = None
        self.view_self = None
        self.frame = None
        self.engine = None
        self.event_list = None
        self._wndproc = None          # manter vivo enquanto a janela existir
        self._class_name = None
        self._h_instance = None
        self._want_close = False
        self._open = False

    # ---- criação -------------------------------------------------

    def _make_window(self, client_w: int, client_h: int, title: str, owner_hwnd=None):
        """Igual ao create_host_window do passo 4, com duas mudanças
        que fazem toda a diferença dentro do Blender: nome de classe
        único por sessão e wndproc que NÃO manda WM_QUIT."""
        global _class_counter
        _class_counter += 1
        self._class_name = f"DAWVst3Editor{_class_counter}"
        self._h_instance = kernel32.GetModuleHandleW(None)

        def _proc(hwnd, msg, wparam, lparam):
            if msg == step4.WM_CLOSE:
                # NÃO destrói a janela aqui. O VST3 exige que
                # IPlugView::removed() rode ENQUANTO o HWND pai ainda
                # existe -- destruir antes faz o plugin (JUCE/VSTGUI)
                # mexer em janelas-filhas já mortas e derrubar o Blender.
                # Só esconde e marca; o timer chama session.close(), que
                # faz removed() -> setFrame(NULL) -> release -> DestroyWindow.
                self._want_close = True
                user32.ShowWindow(hwnd, 0)  # SW_HIDE
                return 0
            if msg == step4.WM_DESTROY:
                # Nada de PostQuitMessage() -- isso fecharia o Blender.
                self._want_close = True
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = step4.WNDPROC(_proc)

        wc = step4.WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = self._wndproc
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = self._h_instance
        wc.hIcon = None
        wc.hCursor = user32.LoadCursorW(None, ctypes.cast(step4.IDC_ARROW, wintypes.LPCWSTR))
        wc.hbrBackground = step4.COLOR_WINDOW_BRUSH
        wc.lpszMenuName = None
        wc.lpszClassName = self._class_name

        if not user32.RegisterClassW(ctypes.byref(wc)):
            err = kernel32.GetLastError()
            if err != ERROR_CLASS_ALREADY_EXISTS:
                raise RuntimeError(f"RegisterClassW({self._class_name}) falhou (GetLastError={err})")

        outer = wintypes.RECT(0, 0, client_w, client_h)
        user32.AdjustWindowRectEx(ctypes.byref(outer), step4.WS_OVERLAPPEDWINDOW, False, 0)

        hwnd = user32.CreateWindowExW(
            0, self._class_name, title, step4.WS_OVERLAPPEDWINDOW,
            120, 120, outer.right - outer.left, outer.bottom - outer.top,
            owner_hwnd, None, self._h_instance, None,
        )
        if not hwnd:
            raise RuntimeError(f"CreateWindowExW falhou (GetLastError={kernel32.GetLastError()})")
        return hwnd

    def open(self) -> bool:
        inst = self.inst
        if inst._ctrl_full_vtbl is None:
            return False

        # Apartamento COM da thread principal -- plugin com WebView,
        # Direct2D ou drag&drop precisa disso. Se o Blender já
        # inicializou (quase sempre inicializou), volta S_FALSE ou
        # RPC_E_CHANGED_MODE e a gente ignora: não é erro nosso.
        try:
            ctypes.windll.ole32.CoInitializeEx(None, step4.COINIT_APARTMENTTHREADED)
        except Exception:
            pass

        view_ptr_raw = inst._ctrl_full_vtbl.createView(inst._ctrl_self, step4.kEditor)
        if not view_ptr_raw:
            return False

        view_ptr = ctypes.cast(view_ptr_raw, ctypes.POINTER(step4.IPlugViewObj))
        self.view_vtbl = view_ptr.contents.lpVtbl.contents
        self.view_self = ctypes.cast(view_ptr, ctypes.c_void_p)

        if self.view_vtbl.isPlatformTypeSupported(self.view_self, step4.kPlatformTypeHWND) != step1.kResultOk:
            self.view_vtbl.release(self.view_self)
            self.view_vtbl = self.view_self = None
            return False

        size = step4.ViewRect()
        self.view_vtbl.getSize(self.view_self, ctypes.byref(size))
        w = max(64, size.right - size.left)
        h = max(64, size.bottom - size.top)

        # Janela do Blender como "owner" (NÃO parent): o editor flutua
        # por cima do Blender e minimiza junto, mas continua sendo uma
        # janela top-level -- o loop do GHOST despacha as mensagens
        # dela normalmente, que é justamente o que faz isso funcionar
        # sem message loop nosso.
        owner = user32.GetActiveWindow() or user32.GetForegroundWindow()
        self.hwnd = self._make_window(w, h, inst.plugin_name or "VST3", owner)

        self.frame = step4.HostPlugFrame(self.hwnd)
        self.view_vtbl.setFrame(self.view_self, self.frame.ptr)

        hr = self.view_vtbl.attached(self.view_self, ctypes.c_void_p(self.hwnd), step4.kPlatformTypeHWND)
        if hr != step1.kResultOk:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
            self.view_vtbl.release(self.view_self)
            self.view_vtbl = self.view_self = None
            inst.last_error = f"attached() falhou (hr={hr:#x})"
            return False

        # Deixa o HostPlugFrame poder responder resizeView() do plugin.
        self.frame.view_vtbl = self.view_vtbl
        self.frame.view_self = self.view_self

        user32.ShowWindow(self.hwnd, step4.SW_SHOWNORMAL)
        user32.UpdateWindow(self.hwnd)
        try:
            user32.SetForegroundWindow(self.hwnd)
        except Exception:
            pass

        # Motor ao vivo (thread separada -- esse é o lugar certo dele).
        if inst._ap_vtbl is not None:
            self.event_list = step6.HostEventList() if inst._has_event_in_bus else None
            self.engine = step6.LiveAudioEngineWithEvents(
                inst._ap_vtbl, inst._ap_self, inst._out_channels,
                input_event_list=self.event_list,
            )
            self.engine.pending_input_param_changes = None
            try:
                self.engine.start()
            except Exception as e:
                inst.last_error = f"motor de áudio ao vivo não subiu: {e}"
                self.engine = None

        # Mantém a API antiga funcionando (trigger_live_note,
        # _push_live_param, close_editor do native_host).
        inst._hwnd = self.hwnd
        inst._view_vtbl = self.view_vtbl
        inst._view_self = self.view_self
        inst._frame = self.frame
        inst._wndproc_keepalive = self._wndproc
        inst._live_engine = self.engine
        inst._live_event_list = self.event_list
        inst._editor_open = True

        self._open = True
        _sessions.append(self)
        _ensure_timer()
        return True

    # ---- fechamento ---------------------------------------------

    def alive(self) -> bool:
        if not self._open:
            return False
        if self._want_close:
            return False
        if self.hwnd and not user32.IsWindow(self.hwnd):
            return False
        return True

    def close(self):
        """Desmonta na ordem certa. Sempre chamado da thread
        principal (pelo timer ou pelo close_editor())."""
        if not self._open:
            return
        self._open = False
        inst = self.inst

        if self.engine is not None:
            try:
                inst._ap_vtbl.setProcessing(inst._ap_self, 0)
            except Exception:
                pass
            try:
                self.engine.stop()
            except Exception:
                pass
            try:
                inst._ap_vtbl.setProcessing(inst._ap_self, 1)
            except Exception:
                pass
            self.engine = None

        if self.view_vtbl is not None:
            try:
                self.view_vtbl.removed(self.view_self)
            except Exception:
                pass
            try:
                # Desconecta o frame ANTES de liberar a view: senão o
                # plugin pode chamar o HostPlugFrame (já liberado pelo
                # Python) durante o release -> use-after-free.
                self.view_vtbl.setFrame(self.view_self, None)
            except Exception:
                pass
            try:
                self.view_vtbl.release(self.view_self)
            except Exception:
                pass
            self.view_vtbl = self.view_self = None

        if self.hwnd and user32.IsWindow(self.hwnd):
            try:
                user32.DestroyWindow(self.hwnd)
            except Exception:
                pass
        self.hwnd = None

        if self._class_name:
            try:
                user32.UnregisterClassW(self._class_name, self._h_instance)
            except Exception:
                pass
            self._class_name = None

        self.frame = None
        self.event_list = None
        self._wndproc = None

        inst._hwnd = None
        inst._view_vtbl = None
        inst._view_self = None
        inst._frame = None
        inst._live_engine = None
        inst._live_event_list = None
        inst._editor_open = False

        if self in _sessions:
            _sessions.remove(self)

    def request_close(self):
        self._want_close = True
        if self.hwnd and user32.IsWindow(self.hwnd):
            user32.PostMessageW(self.hwnd, step4.WM_CLOSE, 0, 0)


# ═══════════════════════════════════════════════════════════════
#  Timer do Blender -- só faxina, o loop de mensagens é o do GHOST.
# ═══════════════════════════════════════════════════════════════

def tick() -> float:
    for session in list(_sessions):
        if not session.alive():
            try:
                session.close()
            except Exception:
                pass
    return 0.25


def _ensure_timer():
    global _timer_installed
    if _timer_installed:
        return
    try:
        import bpy
    except ImportError:
        return  # rodando fora do Blender: quem chamou pumpa/fecha na mão
    if not bpy.app.timers.is_registered(tick):
        bpy.app.timers.register(tick, persistent=True)
    _timer_installed = True


def close_all():
    """Chamar no unregister() do addon."""
    for session in list(_sessions):
        try:
            session.close()
        except Exception:
            pass
    global _timer_installed
    try:
        import bpy
        if bpy.app.timers.is_registered(tick):
            bpy.app.timers.unregister(tick)
    except Exception:
        pass
    _timer_installed = False


# ═══════════════════════════════════════════════════════════════
#  Instalação por cima da VST3PluginInstance
# ═══════════════════════════════════════════════════════════════

def _find_session(inst) -> "EditorSession | None":
    for s in _sessions:
        if s.inst is inst:
            return s
    return None


def _open_editor(self) -> bool:
    if not self.loaded or self._ctrl_full_vtbl is None:
        return False
    existing = _find_session(self)
    if existing is not None and existing.alive():
        # Já aberto -- só traz pra frente.
        try:
            user32.SetForegroundWindow(existing.hwnd)
        except Exception:
            pass
        return True
    if threading.current_thread() is not threading.main_thread():
        self.last_error = "open_editor() precisa ser chamado da thread principal do Blender"
        return False
    session = EditorSession(self)
    try:
        return session.open()
    except Exception as e:
        self.last_error = str(e)
        try:
            session.close()
        except Exception:
            pass
        return False


def _close_editor(self):
    session = _find_session(self)
    if session is not None:
        session.close()
    self._editor_open = False


def _is_editor_open(self) -> bool:
    session = _find_session(self)
    return bool(session and session.alive())


def install():
    """Troca open_editor/close_editor/is_editor_open da
    VST3PluginInstance pela versão de thread principal."""
    native_host.VST3PluginInstance.open_editor = _open_editor
    native_host.VST3PluginInstance.close_editor = _close_editor
    native_host.VST3PluginInstance.is_editor_open = _is_editor_open
    return True