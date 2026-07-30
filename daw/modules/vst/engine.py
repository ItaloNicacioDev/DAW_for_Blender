# modules/vst/engine.py
"""
Ponte real de processamento de VST via `dawdreamer`.

Por que dawdreamer:
    - Suporta VST2 e VST3 (efeitos e instrumentos) na mesma biblioteca.
    - Processa tanto em modo "efeito" (aplica sobre um buffer de áudio já
      existente) quanto em modo "instrumento" (sintetiza áudio a partir de
      notas MIDI) — os dois modos que este addon precisa, escolhidos
      automaticamente conforme `VSTProgramType` de cada plugin.
    - É a opção mais pesada (traz o JUCE embutido), mas é a única que dá
      suporte completo a efeitos + instrumentos MIDI sem depender de um
      host VST externo.

SEM dependência obrigatória: se `dawdreamer` não estiver instalado, todo
o resto do addon continua funcionando normalmente — apenas os VSTs não
carregam, e `VST.load()` preenche `VST.error` com instruções de instalação
(ver `install_instructions()`).

Este módulo NÃO importa `bpy` — é usado tanto pela UI do Blender quanto,
em tese, por um motor de áudio isolado (offline).
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .vst import VSTProgramParameter, VSTProgramType


# ═══════════════════════════════════════════════════════════════
#  DETECÇÃO DE FORMATO (VST2 x VST3)
# ═══════════════════════════════════════════════════════════════

_VST3_EXTENSIONS = {".vst3"}
_VST2_EXTENSIONS = {".dll", ".so", ".dylib", ".vst"}


def detect_plugin_format(path: str | Path) -> str:
    """
    Detecta se um caminho é um plugin VST2 ou VST3 pela extensão.

    Retorna "VST3", "VST2" ou "UNKNOWN".

    Notas:
        - VST3 é normalmente um bundle (.vst3), que no Windows/Linux
          pode aparecer como arquivo único ou como pasta terminando em
          .vst3 (contendo Contents/<arch>/*.so|*.dll por dentro).
        - VST2 é sempre um único binário: .dll (Windows), .so (Linux,
          fora de um bundle .vst3) ou .vst (pacote .vst do macOS, que
          internamente também é um diretório, mas a extensão já entrega
          o formato).
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in _VST3_EXTENSIONS:
        return "VST3"
    if suffix in _VST2_EXTENSIONS:
        return "VST2"

    # Fallback: bundles .vst3 às vezes são passados sem checar suffix
    # diretamente (ex.: caminho apontando para dentro do bundle).
    for parent in p.parents:
        if parent.suffix.lower() == ".vst3":
            return "VST3"
        if parent.suffix.lower() == ".vst":
            return "VST2"

    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════
#  DISPONIBILIDADE DA BIBLIOTECA
# ═══════════════════════════════════════════════════════════════

_dawdreamer_module = None       # cache do módulo importado
_availability_checked = False   # evita reimportar a cada chamada
_import_error: Optional[str] = None


def _try_import_dawdreamer():
    """Importa `dawdreamer` uma única vez e guarda o resultado em cache."""
    global _dawdreamer_module, _availability_checked, _import_error

    if _availability_checked:
        return _dawdreamer_module

    _availability_checked = True
    try:
        import dawdreamer as dd  # type: ignore
        _dawdreamer_module = dd
        _import_error = None
    except Exception as e:  # ImportError ou erro de carregamento de DLL nativa
        _dawdreamer_module = None
        _import_error = str(e)

    return _dawdreamer_module


def is_available() -> bool:
    """True se `dawdreamer` está instalado e importável no Python do Blender."""
    return _try_import_dawdreamer() is not None


def get_import_error() -> Optional[str]:
    """Mensagem de erro da última tentativa de import, se houver."""
    _try_import_dawdreamer()
    return _import_error


def install_instructions() -> str:
    """
    Mensagem amigável explicando como instalar `dawdreamer` no Python
    embutido do Blender (é um Python separado do sistema).
    """
    py = sys.executable
    reason = f" (detalhe: {_import_error})" if _import_error else ""
    return (
        "dawdreamer não está instalado no Python do Blender.\n"
        f"Python em uso: {py}\n\n"
        "Para instalar, feche o Blender e rode no terminal:\n"
        f'    "{py}" -m pip install dawdreamer\n\n'
        "Ou use o botão \"Instalar dawdreamer\" no painel VST > "
        "Configurações, que executa o mesmo comando automaticamente.\n"
        "Após instalar, reinicie o Blender." + reason
    )


def install_dawdreamer(callback=None) -> None:
    """
    Instala `dawdreamer` via pip no Python do Blender, em background.

    `callback(success: bool, message: str)` é chamado ao final, a partir
    da thread de instalação — quem registra o callback deve agendar a
    atualização de UI via `bpy.app.timers` se for tocar em bpy.types.
    """

    def _run():
        import subprocess
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "dawdreamer"],
                capture_output=True, text=True, timeout=600,
            )
            global _availability_checked
            _availability_checked = False  # força reavaliar na próxima checagem
            ok = proc.returncode == 0
            msg = proc.stdout[-2000:] if ok else (proc.stderr[-2000:] or proc.stdout[-2000:])
            if callback:
                callback(ok, msg)
        except Exception as e:
            if callback:
                callback(False, str(e))

    threading.Thread(target=_run, daemon=True).start()


# ═══════════════════════════════════════════════════════════════
#  PONTE DE PROCESSAMENTO (efeito OU instrumento, via dawdreamer)
# ═══════════════════════════════════════════════════════════════

class DawdreamerBridge:
    """
    Encapsula um `dawdreamer.RenderEngine` + um processor de plugin único.

    Cada instância de `VST` (modules/vst/vst.py) possui seu próprio bridge,
    isolado, para poder carregar/descarregar plugins independentemente.

    Modos de processamento (escolhidos por `vst_type`, nunca pelo usuário):
        - EFFECT     -> `process_effect()`: injeta um buffer de áudio como
                        fonte de "playback" no grafo, encadeia o plugin
                        como efeito e renderiza — usado bloco a bloco
                        durante a reprodução (processamento em tempo real
                        por chamada, ideal para inserts em uma track).
        - INSTRUMENT -> `render_instrument()`: injeta eventos MIDI direto
                        no plugin e renderiza a duração pedida — usado
                        para bounce/render offline de uma pattern/clipe.
    """

    def __init__(self, sample_rate: int = 44100, block_size: int = 512):
        dd = _try_import_dawdreamer()
        if dd is None:
            raise RuntimeError(install_instructions())

        self._dd = dd
        self.sample_rate = sample_rate
        self.block_size = block_size

        self.engine = dd.RenderEngine(sample_rate, block_size)
        self.plugin = None            # processor do dawdreamer (make_plugin_processor)
        self.plugin_name: str = ""
        self.vst_type: Optional["VSTProgramType"] = None
        self._param_names: Dict[int, str] = {}

    # ------------------------------------------------------------------
    # Carregamento / descarregamento
    # ------------------------------------------------------------------
    def load(self, path: str | Path, vst_type: "VSTProgramType") -> None:
        """Carrega o plugin (VST2 ou VST3, dawdreamer detecta pela extensão)."""
        from .vst import VSTProgramType  # import tardio evita ciclo

        path = str(path)
        self.plugin_name = Path(path).stem
        self.vst_type = vst_type

        try:
            self.plugin = self.engine.make_plugin_processor(self.plugin_name, path)
        except Exception as e:
            raise RuntimeError(f"Falha ao carregar plugin '{path}': {e}")

        self._param_names.clear()

    def unload(self) -> None:
        """Libera referências do plugin e do engine para o GC coletar."""
        self.plugin = None
        self.engine = None
        self._dd = None

    # ------------------------------------------------------------------
    # Parâmetros
    # ------------------------------------------------------------------
    def list_parameters(self) -> List["VSTProgramParameter"]:
        """
        Lista os parâmetros expostos pelo plugin como `VSTProgramParameter`
        (valores já normalizados 0.0-1.0, como o dawdreamer trabalha).
        """
        from .vst import VSTProgramParameter

        if self.plugin is None:
            return []

        params: List[VSTProgramParameter] = []

        # `get_parameters_description()` existe nas versões mais novas do
        # dawdreamer e traz nome/label por parâmetro. Em versões antigas
        # cai no fallback com apenas índice + valor.
        descriptions = None
        for attr in ("get_parameters_description", "get_plugin_parameters_description"):
            fn = getattr(self.plugin, attr, None)
            if callable(fn):
                try:
                    descriptions = fn()
                    break
                except Exception:
                    descriptions = None

        if descriptions:
            for d in descriptions:
                idx = int(d.get("index", d.get("id", 0)))
                name = str(d.get("name", f"Param {idx}"))
                value = float(d.get("value", 0.0))
                label = str(d.get("text", d.get("label", "")))
                self._param_names[idx] = name
                params.append(VSTProgramParameter(id=idx, name=name, value=value, label=label))
            return params

        # Fallback: `get_patch()` retorna [(index, value), ...] sem nomes.
        get_patch = getattr(self.plugin, "get_patch", None)
        if callable(get_patch):
            try:
                for idx, value in get_patch():
                    name = f"Param {idx}"
                    self._param_names[int(idx)] = name
                    params.append(VSTProgramParameter(id=int(idx), name=name, value=float(value)))
            except Exception:
                pass

        return params

    def set_parameter(self, param_id: int, value: float) -> None:
        if self.plugin is None:
            return
        self.plugin.set_parameter(int(param_id), float(value))

    def get_parameter(self, param_id: int) -> float:
        if self.plugin is None:
            return 0.0
        return float(self.plugin.get_parameter(int(param_id)))

    # ------------------------------------------------------------------
    # Processamento — EFFECT (streaming/bloco a bloco durante playback)
    # ------------------------------------------------------------------
    def process_effect(self, audio):
        """
        Processa um buffer numpy (shape (2, N) ou (N,) mono) através do
        plugin carregado como efeito, devolvendo o áudio processado.

        Cada chamada monta um grafo mínimo (playback -> plugin) e renderiza
        apenas a duração do buffer recebido — é assim que a DAW aplica o
        VST bloco a bloco conforme o transporte avança, sem precisar manter
        um stream de áudio contínuo dentro do dawdreamer (que é um motor
        de render offline por natureza).
        """
        import numpy as np

        if self.plugin is None:
            raise RuntimeError("Nenhum plugin carregado")

        arr = np.asarray(audio, dtype=np.float32)
        if arr.ndim == 1:
            arr = np.stack([arr, arr])  # mono -> estéreo
        n_samples = arr.shape[-1]
        duration = max(n_samples / float(self.sample_rate), 1.0 / self.sample_rate)

        playback = self.engine.make_playback_processor(f"{self.plugin_name}_in", arr)
        self.engine.load_graph([
            (playback, []),
            (self.plugin, [f"{self.plugin_name}_in"]),
        ])
        self.engine.render(duration)
        out = self.plugin.get_audio()
        return np.asarray(out, dtype=np.float32)[:, :n_samples]

    # ------------------------------------------------------------------
    # Processamento — INSTRUMENT (render offline a partir de MIDI)
    # ------------------------------------------------------------------
    def render_instrument(self, midi_notes: Sequence[Tuple[int, float, float, int]], duration: float):
        """
        Renderiza o plugin como instrumento a partir de uma lista de notas
        MIDI `(pitch, start_seconds, duration_seconds, velocity)`.

        Retorna um numpy array estéreo (2, N).
        """
        import numpy as np

        if self.plugin is None:
            raise RuntimeError("Nenhum plugin carregado")

        clear_midi = getattr(self.plugin, "clear_midi", None)
        if callable(clear_midi):
            try:
                clear_midi()
            except Exception:
                pass

        for pitch, start, note_duration, velocity in midi_notes:
            self.plugin.add_midi_note(
                int(pitch), int(velocity), float(start), float(note_duration),
            )

        self.engine.load_graph([(self.plugin, [])])
        self.engine.render(float(duration))
        out = self.plugin.get_audio()
        return np.asarray(out, dtype=np.float32)

    def __repr__(self) -> str:
        return f"<DawdreamerBridge '{self.plugin_name}' @ {self.sample_rate}Hz>"