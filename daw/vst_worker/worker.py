# daw/vst_worker/worker.py
"""
Processo standalone que hospeda o dawdreamer de verdade e os VSTs
carregados. Roda num Python separado do Blender (ex.: 3.12 embutido em
`daw/vendor/py312_embed_win_amd64/`), onde existe uma wheel oficial do
dawdreamer instalada -- sem depender da versao de Python do Blender.

Uso:
    python worker.py [--host 127.0.0.1] [--port 0]

Ao subir, escreve na primeira linha do stdout:
    DAW-VST-WORKER PORT=<porta>
e entao aceita UMA conexao do addon (o cliente em `ipc_engine.py`).

Fica vivo ate receber o comando "shutdown" ou a conexao cair -- nesse
caso encerra sozinho (nao fica orfao caso o Blender feche/crashe).

═══════════════════════════════════════════════════════════════════
THREAD ÚNICA PARA TUDO QUE TOCA EM dawdreamer/JUCE
═══════════════════════════════════════════════════════════════════
JUCE exige que toda a interação com o sistema de janelas nativo (GUI de
plugin, via `plugin.open_editor()`) aconteça na MESMA thread que
inicializou esse sistema. Rodar open_editor() numa thread diferente da
que criou o RenderEngine/plugin faz a chamada "funcionar" sem erro, só
que a janela nunca aparece/desenha de verdade -- exatamente o sintoma
relatado quando isso rodava numa thread solta por comando.

Por isso: existe UMA thread dedicada (`_juce_thread_main`) que processa
TODOS os comandos que tocam em dawdreamer -- load, parâmetros, render,
E open_editor -- sempre na mesma thread, do início ao fim do processo.
A thread de rede (`_serve`) só enfileira pedidos e espera a resposta;
não chama dawdreamer diretamente nunca.

open_editor() é bloqueante (só retorna quando a janela é fechada pelo
usuário). Pra não travar o Blender enquanto a janela está aberta, esse
comando específico é "fire-and-forget": a thread de rede responde OK
assim que enfileira o pedido, sem esperar a janela fechar. A thread
JUCE fica ocupada com aquele plugin até a janela fechar -- outros
comandos ficam na fila esperando a vez (mesmo limite que a maioria dos
hosts de plugin tem: uma GUI de plugin aberta por vez por thread).

SEM dependencia de `bpy`. A UNICA dependencia externa e o `dawdreamer`
de verdade, que deve estar instalado no Python que roda este script
(nao no Python do Blender).
"""
from __future__ import annotations

import argparse
import datetime
import queue
import socket
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Força o stdout/stderr a UTF-8, independente da codepage do console do
# Windows (que costuma ser cp1252 em sistemas PT-BR). Sem isso, print()
# de texto com acento (ex.: "não", "codificação") pode sair em bytes
# cp1252, enquanto o lado do Blender (ipc_engine.py) lê esse stdout
# assumindo UTF-8 -- causa exatamente um
# "'utf-8' codec can't decode byte 0xe7 ... invalid continuation byte"
# (0xe7 é 'ç' em cp1252) na hora do handshake de porta.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from protocol import (  # noqa: E402
    ConnectionClosed,
    ProtocolError,
    format_port_handshake,
    recv_frame,
    send_frame,
)

# ═══════════════════════════════════════════════════════════════
#  LOG EM ARQUIVO -- à prova de qualquer captura de console/pipe
#  que esteja comendo o stdout/stderr (redirecionamento do
#  Start-Process do PowerShell, terminal integrado de IDE, etc.).
#  Sempre escreve aqui, além de tentar print() normal.
# ═══════════════════════════════════════════════════════════════
_LOG_PATH = Path(__file__).resolve().parent / "worker_debug.log"


def _log(msg: str) -> None:
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}"
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    try:
        print(line, flush=True)
    except Exception:
        pass


_log("=" * 60)
_log("worker.py iniciando (import de protocol.py OK)")

try:
    import numpy as np
    _log(f"numpy OK, versao {np.__version__}")
except ImportError as e:
    _log(f"ERRO: numpy nao encontrado: {e}")
    raise

try:
    import dawdreamer as dd
    _log(f"dawdreamer OK, tem RenderEngine: {hasattr(dd, 'RenderEngine')}")
except ImportError as e:
    _log(f"ERRO: dawdreamer nao encontrado: {e}")
    raise


# ═══════════════════════════════════════════════════════════════
#  ESTADO: um RenderEngine + plugin processor por vst_id
#  (só é tocado pela thread JUCE dedicada, nunca pela thread de rede)
# ═══════════════════════════════════════════════════════════════

class LoadedPlugin:
    __slots__ = ("engine", "plugin", "vst_type", "sample_rate", "block_size")

    def __init__(self, engine, plugin, vst_type: str, sample_rate: int, block_size: int):
        self.engine = engine
        self.plugin = plugin
        self.vst_type = vst_type
        self.sample_rate = sample_rate
        self.block_size = block_size


_LOADED: Dict[str, LoadedPlugin] = {}

# vst_id -> True enquanto a janela do editor daquele plugin está aberta.
# Lido pela thread de rede (is_editor_open), escrito pela thread JUCE.
# Dict simples de bool é seguro o suficiente entre as duas threads aqui
# (GIL cobre get/set atômico de um valor só; não precisa de lock extra).
_EDITOR_OPEN: Dict[str, bool] = {}


def _cmd_ping(header: dict, payload: bytes):
    return {"ok": True, "pong": True}, b""


def _cmd_load(header: dict, payload: bytes):
    vst_id = header["vst_id"]
    path = header["path"]
    vst_type = header.get("vst_type", "EFFECT")
    sample_rate = int(header.get("sample_rate", 44100))
    block_size = int(header.get("block_size", 512))

    engine = dd.RenderEngine(sample_rate, block_size)
    plugin = engine.make_plugin_processor(vst_id, path)

    _LOADED[vst_id] = LoadedPlugin(engine, plugin, vst_type, sample_rate, block_size)
    return {"ok": True}, b""


def _cmd_unload(header: dict, payload: bytes):
    vst_id = header["vst_id"]
    _LOADED.pop(vst_id, None)
    _EDITOR_OPEN.pop(vst_id, None)
    return {"ok": True}, b""


def _cmd_list_parameters(header: dict, payload: bytes):
    vst_id = header["vst_id"]
    loaded = _LOADED.get(vst_id)
    if loaded is None:
        return {"ok": False, "error": f"VST '{vst_id}' nao carregado"}, b""

    params = []
    descriptions = None
    for attr in ("get_parameters_description", "get_plugin_parameters_description"):
        fn = getattr(loaded.plugin, attr, None)
        if callable(fn):
            try:
                descriptions = fn()
                break
            except Exception:
                descriptions = None

    if descriptions:
        for d in descriptions:
            params.append({
                "id": int(d.get("index", d.get("id", 0))),
                "name": str(d.get("name", "")),
                "value": float(d.get("value", 0.0)),
                "label": str(d.get("text", d.get("label", ""))),
            })
    else:
        get_patch = getattr(loaded.plugin, "get_patch", None)
        if callable(get_patch):
            try:
                for idx, value in get_patch():
                    params.append({"id": int(idx), "name": f"Param {idx}", "value": float(value), "label": ""})
            except Exception:
                pass

    return {"ok": True, "parameters": params}, b""


def _cmd_set_parameter(header: dict, payload: bytes):
    vst_id = header["vst_id"]
    loaded = _LOADED.get(vst_id)
    if loaded is None:
        return {"ok": False, "error": f"VST '{vst_id}' nao carregado"}, b""
    loaded.plugin.set_parameter(int(header["param_id"]), float(header["value"]))
    return {"ok": True}, b""


def _cmd_get_parameter(header: dict, payload: bytes):
    vst_id = header["vst_id"]
    loaded = _LOADED.get(vst_id)
    if loaded is None:
        return {"ok": False, "error": f"VST '{vst_id}' nao carregado"}, b""
    value = float(loaded.plugin.get_parameter(int(header["param_id"])))
    return {"ok": True, "value": value}, b""


def _cmd_process_effect(header: dict, payload: bytes):
    vst_id = header["vst_id"]
    loaded = _LOADED.get(vst_id)
    if loaded is None:
        return {"ok": False, "error": f"VST '{vst_id}' nao carregado"}, b""

    channels = int(header["channels"])
    n_samples = int(header["n_samples"])
    arr = np.frombuffer(payload, dtype=np.float32).reshape(channels, n_samples).copy()

    duration = max(n_samples / float(loaded.sample_rate), 1.0 / loaded.sample_rate)
    playback = loaded.engine.make_playback_processor(f"{vst_id}_in", arr)
    loaded.engine.load_graph([
        (playback, []),
        (loaded.plugin, [f"{vst_id}_in"]),
    ])
    loaded.engine.render(duration)
    out = np.asarray(loaded.plugin.get_audio(), dtype=np.float32)[:, :n_samples]
    out = np.ascontiguousarray(out)

    resp = {"ok": True, "channels": out.shape[0], "n_samples": out.shape[1]}
    return resp, out.tobytes()


def _cmd_render_instrument(header: dict, payload: bytes):
    vst_id = header["vst_id"]
    loaded = _LOADED.get(vst_id)
    if loaded is None:
        return {"ok": False, "error": f"VST '{vst_id}' nao carregado"}, b""

    midi_notes = header.get("midi_notes", [])
    duration = float(header["duration"])

    clear_midi = getattr(loaded.plugin, "clear_midi", None)
    if callable(clear_midi):
        try:
            clear_midi()
        except Exception:
            pass

    for pitch, start, note_duration, velocity in midi_notes:
        loaded.plugin.add_midi_note(int(pitch), int(velocity), float(start), float(note_duration))

    loaded.engine.load_graph([(loaded.plugin, [])])
    loaded.engine.render(duration)
    out = np.asarray(loaded.plugin.get_audio(), dtype=np.float32)
    out = np.ascontiguousarray(out)

    resp = {"ok": True, "channels": out.shape[0], "n_samples": out.shape[1]}
    return resp, out.tobytes()


def _cmd_open_editor_blocking(header: dict, payload: bytes):
    """
    Executa de verdade a abertura da GUI -- SEMPRE na thread JUCE
    dedicada (nunca na thread de rede). Bloqueia até o usuário fechar a
    janela. Quem chama isso (`_juce_thread_main`) já sabe que essa
    chamada é bloqueante e não espera resposta imediata pra rede.
    """
    vst_id = header["vst_id"]
    loaded = _LOADED.get(vst_id)
    if loaded is None:
        return {"ok": False, "error": f"VST '{vst_id}' nao carregado"}, b""

    open_editor_fn = getattr(loaded.plugin, "open_editor", None)
    if not callable(open_editor_fn):
        _EDITOR_OPEN[vst_id] = False
        return {"ok": False, "error": "Este plugin nao expoe open_editor() (dawdreamer)"}, b""

    _log(f"[thread JUCE] abrindo editor de '{vst_id}' (janela nativa do plugin)...")
    try:
        open_editor_fn()
        _log(f"[thread JUCE] editor de '{vst_id}' fechado pelo usuário")
    except Exception as e:
        _log(f"[thread JUCE] ERRO no editor de '{vst_id}': {e}\n{traceback.format_exc()}")
    finally:
        _EDITOR_OPEN[vst_id] = False

    return {"ok": True}, b""


def _cmd_is_editor_open(header: dict, payload: bytes):
    vst_id = header["vst_id"]
    return {"ok": True, "is_open": bool(_EDITOR_OPEN.get(vst_id, False))}, b""


_HANDLERS = {
    "ping": _cmd_ping,
    "load": _cmd_load,
    "unload": _cmd_unload,
    "list_parameters": _cmd_list_parameters,
    "set_parameter": _cmd_set_parameter,
    "get_parameter": _cmd_get_parameter,
    "process_effect": _cmd_process_effect,
    "render_instrument": _cmd_render_instrument,
    "_open_editor_blocking": _cmd_open_editor_blocking,  # só chamado internamente pela thread JUCE
    "is_editor_open": _cmd_is_editor_open,
}


# ═══════════════════════════════════════════════════════════════
#  THREAD JUCE DEDICADA -- única thread que toca em dawdreamer
# ═══════════════════════════════════════════════════════════════

class _Job:
    __slots__ = ("header", "payload", "event", "result")

    def __init__(self, header: dict, payload: bytes):
        self.header = header
        self.payload = payload
        self.event = threading.Event()
        self.result: Optional[Tuple[dict, bytes]] = None


_juce_queue: "queue.Queue[_Job]" = queue.Queue()


def _run_job(job: _Job) -> None:
    cmd = job.header.get("cmd")
    handler = _HANDLERS.get(cmd)
    if handler is None:
        job.result = ({"ok": False, "error": f"comando desconhecido: {cmd}"}, b"")
    else:
        try:
            job.result = handler(job.header, job.payload)
        except Exception as e:
            job.result = (
                {"ok": False, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()},
                b"",
            )


def _juce_thread_main() -> None:
    _log("thread JUCE dedicada iniciada -- toda interação com dawdreamer passa por aqui")
    while True:
        job = _juce_queue.get()
        if job is None:  # sentinela de shutdown
            break
        _run_job(job)
        job.event.set()
    _log("thread JUCE dedicada encerrada")


_juce_thread = threading.Thread(target=_juce_thread_main, name="juce-thread", daemon=True)


def _dispatch_sync(header: dict, payload: bytes) -> Tuple[dict, bytes]:
    """Enfileira um job pra thread JUCE e ESPERA a resposta (usado por
    todo comando exceto open_editor, que é fire-and-forget)."""
    job = _Job(header, payload)
    _juce_queue.put(job)
    job.event.wait()
    return job.result


def _serve(conn: socket.socket) -> None:
    while True:
        try:
            header, payload = recv_frame(conn)
        except ConnectionClosed:
            break

        cmd = header.get("cmd")
        req_id = header.get("id")

        if cmd == "shutdown":
            send_frame(conn, {"id": req_id, "ok": True})
            break

        if cmd == "open_editor":
            # Fire-and-forget: enfileira a abertura de verdade na thread
            # JUCE (que É bloqueante, só retorna quando a janela fecha)
            # mas responde pro Blender IMEDIATAMENTE, sem esperar isso
            # acontecer -- senão o Blender ficaria travado até o
            # usuário fechar a janela do plugin.
            vst_id = header.get("vst_id")
            loaded = _LOADED.get(vst_id)
            if loaded is None:
                send_frame(conn, {"id": req_id, "ok": False, "error": f"VST '{vst_id}' nao carregado"})
                continue
            if not hasattr(loaded.plugin, "open_editor"):
                send_frame(conn, {"id": req_id, "ok": False, "error": "Este plugin nao expoe open_editor() (dawdreamer)"})
                continue
            if _EDITOR_OPEN.get(vst_id):
                send_frame(conn, {"id": req_id, "ok": True, "already_open": True})
                continue

            _EDITOR_OPEN[vst_id] = True
            fire_job = _Job({"cmd": "_open_editor_blocking", "vst_id": vst_id}, b"")
            _juce_queue.put(fire_job)  # não espera fire_job.event -- fire-and-forget
            send_frame(conn, {"id": req_id, "ok": True, "already_open": False})
            continue

        resp, resp_payload = _dispatch_sync({**header, "cmd": cmd}, payload)
        resp["id"] = req_id
        try:
            send_frame(conn, resp, resp_payload)
        except (BrokenPipeError, ConnectionResetError):
            break


def main() -> None:
    _log("main() iniciou")
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    _log(f"args parseados: host={args.host} port={args.port}")

    _juce_thread.start()

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((args.host, args.port))
    listener.listen(1)
    actual_port = listener.getsockname()[1]
    _log(f"socket bind+listen OK na porta {actual_port}")

    # Handshake: primeira linha do stdout informa a porta real ao pai.
    print(format_port_handshake(actual_port), flush=True)
    _log("handshake enviado, esperando conexao (accept)...")

    try:
        conn, _addr = listener.accept()
        _log(f"conexao aceita de {_addr}")
    except Exception as e:
        _log(f"ERRO no accept(): {e}\n{traceback.format_exc()}")
        listener.close()
        return

    try:
        _serve(conn)
        _log("_serve() retornou normalmente (conexao encerrada)")
    except Exception as e:
        _log(f"ERRO em _serve(): {e}\n{traceback.format_exc()}")
    finally:
        conn.close()
        listener.close()
        _juce_queue.put(None)  # sentinela pra thread JUCE encerrar
        for loaded in _LOADED.values():
            try:
                loaded.engine = None
                loaded.plugin = None
            except Exception:
                pass
        _LOADED.clear()
        _log("worker encerrado, recursos liberados")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log(f"ERRO FATAL nao tratado em main(): {e}\n{traceback.format_exc()}")
        raise