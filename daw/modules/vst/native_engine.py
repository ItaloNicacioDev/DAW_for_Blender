# modules/vst/native_engine.py
"""
Substituto de `ipc_engine.py`. Mesma interface pública que
`DawdreamerIPCBridge` tinha (load, unload, list_parameters,
set_parameter, get_parameter, process_effect, render_instrument,
stream_reset, stream_render_chunk, save_state, load_state,
open_editor, is_editor_open, trigger_live_note) -- só que em vez de
falar por socket com um processo worker externo rodando dawdreamer,
carrega o plugin DIRETO dentro do processo do Blender via
`modules/vst_host_native` (ctypes puro contra a API VST3 e o Win32).

Por isso `vst.py` não precisa mudar nada além do import: `VST` continua
chamando os mesmos métodos, sem saber que o motor trocou por baixo.

Sem processo externo = sem isolamento de crash (se um plugin travar
de verdade dentro do process(), derruba o Blender junto, não só um
worker). Compensação: nenhuma instalação/dependência externa pro
usuário, nenhuma cópia de Python embutido, sem latência de IPC.
"""
from __future__ import annotations

import sys
import weakref
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .vst import VSTProgramParameter, VSTProgramType

_VST_HOST_NATIVE_DIR = Path(__file__).resolve().parent.parent / "vst_host_native"
if str(_VST_HOST_NATIVE_DIR) not in sys.path:
    sys.path.insert(0, str(_VST_HOST_NATIVE_DIR))

from native_host import VST3PluginInstance  # noqa: E402


# Registro fraco de todas as pontes vivas -- só pra shutdown_worker()
# conseguir fechar editores/threads abertos no unregister() do addon
# (não existe mais um processo único externo pra simplesmente matar).
_all_bridges: "weakref.WeakSet[NativeVST3Bridge]" = weakref.WeakSet()


class NativeVST3Bridge:
    """Drop-in no lugar de `DawdreamerIPCBridge`. Cada instância
    representa um VST carregado -- por baixo, um `VST3PluginInstance`
    (modules/vst_host_native/native_host.py)."""

    def __init__(self, sample_rate: int = 44100, block_size: int = 512):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.plugin_name: str = ""
        self.vst_type: Optional["VSTProgramType"] = None
        self._loaded = False
        self._instance: Optional[VST3PluginInstance] = None
        _all_bridges.add(self)

    # ------------------------------------------------------------------

    def load(self, path: str | Path, vst_type: "VSTProgramType") -> None:
        self.plugin_name = Path(path).stem
        self.vst_type = vst_type
        self._instance = VST3PluginInstance(str(path), sample_rate=self.sample_rate, block_size=self.block_size)
        ok = self._instance.load()
        if not ok:
            err = self._instance.last_error or "motivo desconhecido"
            self._instance = None
            self._loaded = False
            raise RuntimeError(f"Falha ao carregar '{path}' no motor nativo: {err}")
        self._loaded = True

    def unload(self) -> None:
        if self._instance is not None:
            try:
                self._instance.unload()
            except Exception:
                pass
        self._instance = None
        self._loaded = False

    def list_parameters(self) -> List["VSTProgramParameter"]:
        from .vst import VSTProgramParameter

        if not self._loaded or self._instance is None:
            return []
        return [
            VSTProgramParameter(id=p["id"], name=p["name"], value=p["value"], label=p.get("label", ""))
            for p in self._instance.list_parameters()
        ]

    def set_parameter(self, param_id: int, value: float) -> None:
        if self._loaded and self._instance is not None:
            self._instance.set_parameter(int(param_id), float(value))

    def get_parameter(self, param_id: int) -> float:
        if not self._loaded or self._instance is None:
            return 0.0
        return self._instance.get_parameter(int(param_id))

    # ------------------------------------------------------------------
    # Processamento offline
    # ------------------------------------------------------------------

    def process_effect(self, audio, automation: Optional[list] = None):
        import numpy as np

        if not self._loaded or self._instance is None:
            raise RuntimeError("Nenhum plugin carregado")

        arr = np.asarray(audio, dtype=np.float32)
        if arr.ndim == 1:
            arr = np.stack([arr, arr])
        arr = np.ascontiguousarray(arr)

        audio_lists = [arr[ch].tolist() for ch in range(arr.shape[0])]
        out_lists = self._instance.process_effect(audio_lists, automation=automation)
        return np.asarray(out_lists, dtype=np.float32)

    def render_instrument(
        self,
        midi_notes: Sequence[Tuple[int, float, float, int]],
        duration: float,
        automation: Optional[list] = None,
    ):
        import numpy as np

        if not self._loaded or self._instance is None:
            raise RuntimeError("Nenhum plugin carregado")

        out_lists = self._instance.render_instrument(list(midi_notes), float(duration), automation=automation)
        return np.asarray(out_lists, dtype=np.float32)

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def stream_reset(self, midi_notes: Sequence[Tuple[int, float, float, int]], origin_time: float) -> bool:
        if not self._loaded or self._instance is None:
            raise RuntimeError("Nenhum plugin carregado")
        return self._instance.stream_reset(list(midi_notes), float(origin_time))

    def stream_render_chunk(self, chunk_seconds: float, automation_point: Optional[dict] = None):
        import numpy as np

        if not self._loaded or self._instance is None:
            raise RuntimeError("Nenhum plugin carregado")
        out_lists, elapsed = self._instance.stream_render_chunk(float(chunk_seconds), automation_point=automation_point)
        return np.asarray(out_lists, dtype=np.float32), elapsed

    # ------------------------------------------------------------------
    # Estado / GUI
    # ------------------------------------------------------------------

    def save_state(self) -> bytes:
        if self._instance is None:
            return b""
        return self._instance.save_state()

    def load_state(self, data: bytes) -> bool:
        if self._instance is None:
            return False
        return self._instance.load_state(data)

    def open_editor(self) -> bool:
        if self._instance is None:
            return False
        return self._instance.open_editor()

    def is_editor_open(self) -> bool:
        if self._instance is None:
            return False
        return self._instance.is_editor_open()

    def close_editor(self) -> None:
        if self._instance is not None:
            self._instance.close_editor()

    def trigger_live_note(self, pitch: int, velocity: int = 100, duration: float = 1.0) -> bool:
        if self._instance is None:
            return False
        return self._instance.trigger_live_note(int(pitch), int(velocity), float(duration))


# ═══════════════════════════════════════════════════════════════
#  Funções de módulo (mesma assinatura que ipc_engine.py expunha)
# ═══════════════════════════════════════════════════════════════

def is_available() -> bool:
    """O motor nativo roda dentro do próprio processo do Blender via
    ctypes -- não depende de worker externo, Python embutido, nem
    nenhuma instalação extra do usuário. Só existe pro Windows (usa
    ctypes.windll e a API Win32 direto)."""
    return sys.platform == "win32"


def install_instructions() -> str:
    return (
        "O motor de VST nativo (daw/modules/vst_host_native) só funciona "
        "no Windows -- ele fala diretamente com a API VST3 dos plugins e "
        "com o Win32 via ctypes, sem processo externo nem dependências "
        "pra instalar."
    )


def shutdown_worker() -> None:
    """Mantido com esse nome só por compatibilidade com o resto do
    addon (register.py chama isso no unregister()). Não existe mais
    processo externo pra matar -- mas fecha qualquer editor de plugin
    (janela + thread + saída de áudio) que tenha ficado aberto, senão
    o Blender pode fechar com handles nativos pendurados."""
    for bridge in list(_all_bridges):
        try:
            bridge.unload()
        except Exception:
            pass