# modules/vst/ipc_engine.py
"""
Substituto do `DawdreamerBridge` (engine.py) que, em vez de importar o
dawdreamer dentro do processo do Blender, fala com um processo worker
separado (`daw/vst_worker/worker.py`), rodando num Python embutido a
parte (ex.: 3.12) onde o dawdreamer de verdade esta instalado.

Por que:
    - Desacopla o addon da versao de Python do Blender: quando o
      Blender mudar de versao de novo, so o Python embutido do worker
      precisa acompanhar -- nao depende de o mantenedor do dawdreamer
      publicar wheel pra cada versao nova.
    - Isolamento de crash: se um VST travar o processo (comum com
      plugins mal comportados), so o worker morre. O Blender continua
      de pe, e este bridge detecta a queda e pode reiniciar o worker.

Mesma interface publica de `DawdreamerBridge` (engine.py):
    load(), unload(), list_parameters(), set_parameter(), get_parameter(),
    process_effect(), render_instrument()
-- portanto `vst.py` (VST.load/process_effect/render_instrument) nao
precisa saber qual bridge esta por baixo.
"""
from __future__ import annotations

import atexit
import itertools
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "vst_worker"))
from protocol import (  # noqa: E402
    ConnectionClosed,
    parse_port_handshake,
    recv_frame,
    send_frame,
)

if TYPE_CHECKING:
    from .vst import VSTProgramParameter, VSTProgramType


# ═══════════════════════════════════════════════════════════════
#  LOCALIZACAO DO PYTHON EMBUTIDO + WORKER
# ═══════════════════════════════════════════════════════════════

def _worker_python_candidates() -> List[Path]:
    """Pastas de Python embutido compativeis, do mais especifico ao mais
    generico. Cada uma deve conter um python.exe/python3 com dawdreamer
    real instalado (via `pip install dawdreamer` dentro dela)."""
    root = Path(__file__).resolve().parent.parent.parent / "vendor"

    if sys.platform.startswith("win"):
        names = ["py312_embed_win_amd64"]
        exe = "python.exe"
    elif sys.platform == "darwin":
        machine_names = ["py312_embed_macos_arm64", "py312_embed_macos_x86_64"]
        names = machine_names
        exe = "bin/python3"
    else:
        names = ["py312_embed_linux_x86_64"]
        exe = "bin/python3"

    return [root / name / exe for name in names]


def find_worker_python() -> Optional[Path]:
    for candidate in _worker_python_candidates():
        if candidate.is_file():
            return candidate
    return None


def _worker_script_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "vst_worker" / "worker.py"


def install_instructions() -> str:
    candidates = ", ".join(str(c.parent.name) for c in _worker_python_candidates())
    return (
        "Motor de VST (worker) indisponivel.\n\n"
        f"Pasta(s) esperada(s) em daw/vendor/: {candidates}\n"
        "Cada uma deve conter um Python embutido (3.12) com o dawdreamer\n"
        "real instalado dentro dela (pip install dawdreamer), independente\n"
        "da versao de Python do proprio Blender.\n\n"
        "Ver daw/vst_worker/README.md para instrucoes de setup."
    )


# ═══════════════════════════════════════════════════════════════
#  GERENCIADOR DE PROCESSO WORKER (singleton compartilhado)
# ═══════════════════════════════════════════════════════════════

class WorkerProcessError(RuntimeError):
    pass


class _WorkerManager:
    """Gerencia um unico processo worker compartilhado por todos os VSTs
    carregados nesta sessao do Blender. Thread-safe (lock por chamada)."""

    _STARTUP_TIMEOUT = 15.0

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._sock: Optional[socket.socket] = None
        self._lock = threading.RLock()
        self._id_counter = itertools.count(1)
        # Incrementada toda vez que um processo worker novo sobe. Cada
        # DawdreamerIPCBridge guarda em que geracao ele foi carregado;
        # se a geracao mudou (worker morreu e reiniciou por causa de
        # OUTRO plugin travado), o bridge sabe que precisa recarregar
        # a si mesmo antes do proximo comando -- em vez de simplesmente
        # falhar com "nao carregado".
        self._generation = 0

    @property
    def generation(self) -> int:
        return self._generation

    def _spawn(self) -> None:
        python_exe = find_worker_python()
        if python_exe is None:
            raise WorkerProcessError(install_instructions())

        script = _worker_script_path()
        self._proc = subprocess.Popen(
            [str(python_exe), str(script), "--host", "127.0.0.1", "--port", "0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        deadline = time.time() + self._STARTUP_TIMEOUT
        port: Optional[int] = None
        while time.time() < deadline:
            if self._proc.poll() is not None:
                stderr = self._proc.stderr.read() if self._proc.stderr else ""
                raise WorkerProcessError(f"Worker encerrou ao iniciar. stderr:\n{stderr}")
            line = self._proc.stdout.readline() if self._proc.stdout else ""
            if not line:
                continue
            port = parse_port_handshake(line)
            if port is not None:
                break

        if port is None:
            self._kill()
            raise WorkerProcessError("Timeout esperando o worker abrir a porta de escuta.")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", port))
        self._sock = sock
        self._generation += 1

    def _ensure_alive(self) -> None:
        if self._proc is not None and self._proc.poll() is None and self._sock is not None:
            return
        self._kill()
        self._spawn()

    def _kill(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._proc is not None:
            try:
                self._proc.kill()
            except OSError:
                pass
            self._proc = None

    # Timeout por comando -- carregar plugin pode legitimamente demorar
    # (bibliotecas de sample grandes tipo BBC Symphony, wavetables
    # pesadas tipo Serum), então tem mais margem. Os demais são rápidos
    # por natureza; se não voltarem nesse tempo, é sinal de plugin
    # travado (ex.: checagem de licença/ativação esperando uma janela
    # que nunca aparece) -- melhor matar e reiniciar o worker do que
    # deixar o Blender inteiro travado esperando pra sempre.
    _TIMEOUTS = {
        "load": 60.0,
        "unload": 10.0,
        "list_parameters": 15.0,
        "set_parameter": 5.0,
        "get_parameter": 5.0,
        # Bounces com automação (ver VST._build_automation_schedule) fazem
        # várias chamadas engine.render() em sequência do lado do worker
        # em vez de uma só -- folga extra pra não estourar em cadeias
        # longas com muitos pontos de automação.
        "process_effect": 40.0,
        "render_instrument": 90.0,
        "save_state": 15.0,
        "load_state": 15.0,
        "open_editor": 10.0,       # fire-and-forget, deveria responder quase na hora
        "is_editor_open": 5.0,
        "trigger_live_note": 5.0,
        "ping": 5.0,
        "shutdown": 5.0,
    }
    _DEFAULT_TIMEOUT = 20.0

    def call(self, cmd: str, payload: bytes = b"", timeout: Optional[float] = None, **fields) -> Tuple[Dict[str, Any], bytes]:
        """Envia um comando e espera a resposta. Reinicia o worker
        automaticamente se ele tiver caido desde a ultima chamada.

        NUNCA bloqueia indefinidamente -- todo comando tem um timeout
        (ver `_TIMEOUTS`). Se o worker não responder a tempo (plugin
        travado, checagem de licença esperando input, etc.), o processo
        é morto e reiniciado na próxima chamada, e uma exceção clara é
        levantada aqui em vez de travar o Blender inteiro pra sempre.
        """
        with self._lock:
            self._ensure_alive()
            req_id = next(self._id_counter)
            header = {"cmd": cmd, "id": req_id, **fields}
            effective_timeout = timeout if timeout is not None else self._TIMEOUTS.get(cmd, self._DEFAULT_TIMEOUT)
            try:
                self._sock.settimeout(effective_timeout)
                send_frame(self._sock, header, payload)
                resp_header, resp_payload = recv_frame(self._sock)
            except socket.timeout:
                self._kill()
                raise WorkerProcessError(
                    f"O worker não respondeu em {effective_timeout:.0f}s para '{cmd}' -- "
                    f"provavelmente um plugin travado (ex.: checagem de licença/ativação "
                    f"esperando uma janela que não aparece). Processo do worker reiniciado; "
                    f"tente novamente ou verifique esse plugin especificamente."
                )
            except (ConnectionClosed, OSError) as e:
                self._kill()
                raise WorkerProcessError(f"Conexao com o worker perdida: {e}") from e

            if not resp_header.get("ok", False):
                raise WorkerProcessError(resp_header.get("error", "erro desconhecido no worker"))
            return resp_header, resp_payload

    def shutdown(self) -> None:
        with self._lock:
            if self._sock is not None:
                try:
                    self.call("shutdown")
                except WorkerProcessError:
                    pass
            self._kill()


_manager = _WorkerManager()


def shutdown_worker() -> None:
    """Chamar no unregister() do addon, pra nao deixar worker orfao."""
    _manager.shutdown()


# Rede de seguranca: se o Blender fechar sem passar pelo unregister() do
# addon (crash, fechamento abrupto), garante que o processo worker nao
# fique orfao rodando em segundo plano.
atexit.register(_manager.shutdown)


# ═══════════════════════════════════════════════════════════════
#  BRIDGE (mesma interface publica do DawdreamerBridge)
# ═══════════════════════════════════════════════════════════════

class DawdreamerIPCBridge:
    """Drop-in no lugar de `DawdreamerBridge` (engine.py). Cada instancia
    representa um VST carregado, identificado por `vst_id` do lado do
    worker -- mas o processo pesado (RenderEngine) fica todo do outro
    lado do socket."""

    def __init__(self, sample_rate: int = 44100, block_size: int = 512):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.plugin_name: str = ""
        self.vst_type: Optional["VSTProgramType"] = None
        self._loaded = False
        # Path original de load(), guardado pra poder recarregar
        # sozinho se o worker reiniciar por causa de outro plugin.
        self._load_path: Optional[Path] = None
        self._load_generation: int = -1

    def load(self, path: str | Path, vst_type: "VSTProgramType") -> None:
        self.plugin_name = Path(path).stem
        self.vst_type = vst_type
        self._load_path = Path(path)
        _manager.call(
            "load",
            vst_id=self.plugin_name,
            path=str(path),
            vst_type=vst_type.value if hasattr(vst_type, "value") else str(vst_type),
            sample_rate=self.sample_rate,
            block_size=self.block_size,
        )
        self._loaded = True
        self._load_generation = _manager.generation

    def unload(self) -> None:
        if self._loaded:
            try:
                _manager.call("unload", vst_id=self.plugin_name)
            except WorkerProcessError:
                pass
        self._loaded = False
        self._load_generation = -1

    def _ensure_current_generation(self) -> None:
        """Se o worker foi morto e reiniciado desde o ultimo load() deste
        plugin (ex.: outro VST travou e derrubou o processo compartilhado),
        este plugin nao existe mais do lado do worker novo -- mesmo que
        `self._loaded` ainda diga True. Em vez de deixar o proximo comando
        falhar com "nao carregado", recarrega esse plugin especifico de
        forma transparente antes de prosseguir.

        Levanta WorkerProcessError com uma mensagem clara se o proprio
        recarregamento falhar (ex.: o plugin que causou o crash era este
        mesmo)."""
        if not self._loaded or self._load_path is None:
            return
        if self._load_generation == _manager.generation:
            return
        try:
            self.load(self._load_path, self.vst_type)
        except WorkerProcessError as e:
            self._loaded = False
            raise WorkerProcessError(
                f"O worker de VST foi reiniciado (provavelmente outro plugin "
                f"travou) e '{self.plugin_name}' nao pode ser recarregado "
                f"automaticamente: {e}"
            ) from e

    def list_parameters(self) -> List["VSTProgramParameter"]:
        from .vst import VSTProgramParameter

        if not self._loaded:
            return []
        self._ensure_current_generation()
        header, _ = _manager.call("list_parameters", vst_id=self.plugin_name)
        return [
            VSTProgramParameter(id=p["id"], name=p["name"], value=p["value"], label=p.get("label", ""))
            for p in header.get("parameters", [])
        ]

    def set_parameter(self, param_id: int, value: float) -> None:
        if not self._loaded:
            return
        self._ensure_current_generation()
        _manager.call("set_parameter", vst_id=self.plugin_name, param_id=int(param_id), value=float(value))

    def get_parameter(self, param_id: int) -> float:
        if not self._loaded:
            return 0.0
        self._ensure_current_generation()
        header, _ = _manager.call("get_parameter", vst_id=self.plugin_name, param_id=int(param_id))
        return float(header.get("value", 0.0))

    def process_effect(self, audio, automation: Optional[list] = None):
        """
        `automation`, se fornecido, é uma lista de pontos
        `[tempo_em_segundos, {param_id_str: valor_normalizado}]` já
        resolvidos (ver VST._build_automation_schedule() em vst.py). O
        worker processa o áudio em pedaços entre um ponto e o próximo,
        reaplicando os parâmetros automatizados a cada pedaço.
        """
        import numpy as np

        if not self._loaded:
            raise RuntimeError("Nenhum plugin carregado")
        self._ensure_current_generation()

        arr = np.asarray(audio, dtype=np.float32)
        if arr.ndim == 1:
            arr = np.stack([arr, arr])
        arr = np.ascontiguousarray(arr)
        channels, n_samples = arr.shape

        header, payload = _manager.call(
            "process_effect",
            payload=arr.tobytes(),
            vst_id=self.plugin_name,
            channels=channels,
            n_samples=n_samples,
            automation=automation or [],
        )
        out_channels = header["channels"]
        out_samples = header["n_samples"]
        return np.frombuffer(payload, dtype=np.float32).reshape(out_channels, out_samples).copy()

    def render_instrument(
        self,
        midi_notes: Sequence[Tuple[int, float, float, int]],
        duration: float,
        automation: Optional[list] = None,
    ):
        """
        `automation`: mesmo formato de `process_effect()`. Quando
        presente, o worker renderiza em pedaços curtos usando chamadas
        sucessivas de `engine.render()` (que avança o relógio interno
        continuamente), reaplicando os parâmetros automatizados entre
        um pedaço e outro -- em vez de um único valor fixo pra toda a
        duração do bounce.
        """
        import numpy as np

        if not self._loaded:
            raise RuntimeError("Nenhum plugin carregado")
        self._ensure_current_generation()

        header, payload = _manager.call(
            "render_instrument",
            vst_id=self.plugin_name,
            midi_notes=[list(n) for n in midi_notes],
            duration=float(duration),
            automation=automation or [],
        )
        out_channels = header["channels"]
        out_samples = header["n_samples"]
        return np.frombuffer(payload, dtype=np.float32).reshape(out_channels, out_samples).copy()

    def save_state(self) -> bytes:
        """
        Retorna o estado NATIVO do plugin (bytes no formato do
        dawdreamer, não JSON) -- captura tudo que faz parte do estado
        real do plugin, além dos parâmetros normalizados. Retorna
        b"" se não carregado ou se o plugin/dawdreamer não suportar
        save_state() (ex.: build antigo do dawdreamer).
        """
        if not self._loaded:
            return b""
        self._ensure_current_generation()
        header, payload = _manager.call("save_state", vst_id=self.plugin_name)
        if not header.get("ok", False):
            return b""
        return payload

    def load_state(self, data: bytes) -> bool:
        """Restaura um estado nativo salvo por save_state(). Retorna
        False silenciosamente se `data` estiver vazio ou o plugin não
        suportar (ex.: plugin diferente do que gerou o estado)."""
        if not self._loaded or not data:
            return False
        self._ensure_current_generation()
        header, _ = _manager.call("load_state", payload=data, vst_id=self.plugin_name)
        return bool(header.get("ok", False))

    def open_editor(self) -> bool:
        """
        Pede pro worker abrir a janela nativa (GUI) do plugin.

        Retorna rapido (nao espera a janela fechar) -- o worker roda o
        open_editor() do dawdreamer numa thread separada por baixo.
        Retorna False se o plugin nao tiver editor nativo suportado.
        """
        if not self._loaded:
            return False
        header, _ = _manager.call("open_editor", vst_id=self.plugin_name)
        return bool(header.get("ok", False))

    def is_editor_open(self) -> bool:
        if not self._loaded:
            return False
        header, _ = _manager.call("is_editor_open", vst_id=self.plugin_name)
        return bool(header.get("is_open", False))

    def trigger_live_note(self, pitch: int, velocity: int = 100, duration: float = 1.0) -> bool:
        """
        Toca uma nota AGORA através da sessão ao vivo do plugin (só
        funciona com a interface do plugin aberta -- é o motor de áudio
        contínuo que começa junto com open_editor()). Retorna False se
        não houver sessão ao vivo rodando (nesse caso, quem chamou deve
        cair de volta pro preview de um tiro só via render_instrument).
        """
        if not self._loaded:
            return False
        try:
            header, _ = _manager.call(
                "trigger_live_note", vst_id=self.plugin_name,
                pitch=int(pitch), velocity=int(velocity), duration=float(duration),
            )
        except WorkerProcessError:
            return False  # sem sessão ao vivo -- quem chamou cai pro preview de um tiro só
        return bool(header.get("ok", False))

    def __repr__(self) -> str:
        status = "worker" if self._loaded else "nao carregado"
        return f"<DawdreamerIPCBridge '{self.plugin_name}' [{status}] @ {self.sample_rate}Hz>"


def is_available() -> bool:
    return find_worker_python() is not None