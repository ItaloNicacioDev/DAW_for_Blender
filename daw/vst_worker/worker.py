# daw/vst_worker/protocol.py
"""
Protocolo de framing usado na comunicacao entre o addon (rodando no Python
do Blender, ex.: 3.13) e o worker de VST (rodando num Python separado,
ex.: 3.12 embutido, onde o dawdreamer de verdade esta instalado).

Sem dependencias do Blender (`bpy`) nem do dawdreamer -- e importado dos
dois lados (addon e worker).

Formato de cada frame, em qualquer direcao:

    [4 bytes big-endian] total_len          (tamanho do resto do frame)
    [4 bytes big-endian] json_len           (tamanho do cabecalho JSON)
    [json_len bytes]     cabecalho JSON (utf-8)
    [restante]           payload binario opcional (ex.: audio float32)

O cabecalho JSON carrega os campos de controle (comando, ids, parametros,
shape do audio etc.); o payload binario carrega dados grandes (buffers de
audio) sem o overhead de serializar numeros em JSON.
"""
from __future__ import annotations

import json
import socket
import struct
from typing import Any, Dict, Optional, Tuple

_HEADER_LEN_FMT = ">II"  # total_len, json_len -- ambos uint32 big-endian
_HEADER_LEN_SIZE = struct.calcsize(_HEADER_LEN_FMT)


class ProtocolError(Exception):
    pass


class ConnectionClosed(Exception):
    """Levantado quando o socket fecha no meio de uma leitura."""


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Le exatamente `n` bytes do socket, ou levanta ConnectionClosed."""
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionClosed("Conexao fechada pelo outro lado durante a leitura")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def send_frame(sock: socket.socket, header: Dict[str, Any], payload: bytes = b"") -> None:
    """Envia um frame (cabecalho JSON + payload binario opcional)."""
    header_bytes = json.dumps(header, ensure_ascii=False).encode("utf-8")
    total_len = len(header_bytes) + len(payload)
    prefix = struct.pack(_HEADER_LEN_FMT, total_len, len(header_bytes))
    sock.sendall(prefix + header_bytes + payload)


def recv_frame(sock: socket.socket) -> Tuple[Dict[str, Any], bytes]:
    """Recebe um frame. Retorna (cabecalho_dict, payload_bytes)."""
    prefix = _recv_exact(sock, _HEADER_LEN_SIZE)
    total_len, json_len = struct.unpack(_HEADER_LEN_FMT, prefix)
    if json_len > total_len:
        raise ProtocolError("json_len maior que total_len -- frame corrompido")

    body = _recv_exact(sock, total_len)
    header_bytes = body[:json_len]
    payload = body[json_len:]

    try:
        header = json.loads(header_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProtocolError(f"Cabecalho JSON invalido: {e}") from e

    return header, payload


# ---------------------------------------------------------------------
# Handshake de porta: o worker escreve "DAW-VST-WORKER PORT=<n>" na
# primeira linha do stdout assim que o socket de escuta esta pronto.
# ---------------------------------------------------------------------
PORT_HANDSHAKE_PREFIX = "DAW-VST-WORKER PORT="


def format_port_handshake(port: int) -> str:
    return f"{PORT_HANDSHAKE_PREFIX}{port}"


def parse_port_handshake(line: str) -> Optional[int]:
    line = line.strip()
    if not line.startswith(PORT_HANDSHAKE_PREFIX):
        return None
    try:
        return int(line[len(PORT_HANDSHAKE_PREFIX):])
    except ValueError:
        return None