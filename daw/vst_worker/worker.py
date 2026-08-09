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

SEM dependencia de `bpy`. A UNICA dependencia externa e o `dawdreamer`
de verdade, que deve estar instalado no Python que roda este script
(nao no Python do Blender).
"""
from __future__ import annotations

import argparse
import datetime
import socket
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

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

# Threads que estao rodando plugin.open_editor() (bloqueante ate a
# janela ser fechada pelo usuario). Uma por vst_id, pra nao abrir a
# mesma janela duas vezes nem travar o loop principal do worker.
_EDITOR_THREADS: Dict[str, threading.Thread] = {}


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


def _cmd_open_editor(header: dict, payload: bytes):
    """
    Abre a janela nativa (GUI) do plugin numa thread separada.

    plugin.open_editor() do dawdreamer é BLOQUEANTE -- só retorna quando
    o usuário fecha a janela. Se chamássemos direto aqui, travaríamos o
    loop principal do worker (nenhum outro comando, nem process_effect
    de outro VST, seria atendido até a janela fechar). Por isso roda
    numa thread daemon à parte; o comando em si responde OK assim que a
    thread é disparada, sem esperar a janela fechar.
    """
    vst_id = header["vst_id"]
    loaded = _LOADED.get(vst_id)
    if loaded is None:
        return {"ok": False, "error": f"VST '{vst_id}' nao carregado"}, b""

    open_editor_fn = getattr(loaded.plugin, "open_editor", None)
    if not callable(open_editor_fn):
        return {"ok": False, "error": "Este plugin nao expoe open_editor() (dawdreamer)"}, b""

    existing = _EDITOR_THREADS.get(vst_id)
    if existing is not None and existing.is_alive():
        return {"ok": True, "already_open": True}, b""

    def _run_editor():
        _log(f"abrindo editor de '{vst_id}' (janela nativa do plugin)...")
        try:
            open_editor_fn()
        except Exception as e:
            _log(f"ERRO no editor de '{vst_id}': {e}\n{traceback.format_exc()}")
        finally:
            _log(f"editor de '{vst_id}' fechado")

    thread = threading.Thread(target=_run_editor, name=f"vst-editor-{vst_id}", daemon=True)
    _EDITOR_THREADS[vst_id] = thread
    thread.start()

    return {"ok": True, "already_open": False}, b""


def _cmd_is_editor_open(header: dict, payload: bytes):
    vst_id = header["vst_id"]
    thread = _EDITOR_THREADS.get(vst_id)
    is_open = thread is not None and thread.is_alive()
    return {"ok": True, "is_open": is_open}, b""


_HANDLERS = {
    "ping": _cmd_ping,
    "load": _cmd_load,
    "unload": _cmd_unload,
    "list_parameters": _cmd_list_parameters,
    "set_parameter": _cmd_set_parameter,
    "get_parameter": _cmd_get_parameter,
    "process_effect": _cmd_process_effect,
    "render_instrument": _cmd_render_instrument,
    "open_editor": _cmd_open_editor,
    "is_editor_open": _cmd_is_editor_open,
}


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

        handler = _HANDLERS.get(cmd)
        if handler is None:
            send_frame(conn, {"id": req_id, "ok": False, "error": f"comando desconhecido: {cmd}"})
            continue

        try:
            resp, resp_payload = handler(header, payload)
        except Exception as e:
            resp = {"ok": False, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
            resp_payload = b""

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