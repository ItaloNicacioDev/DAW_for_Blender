# modules/updater/downloader.py
"""
Download do pacote .zip da atualização, com callback de progresso.

Usa apenas `urllib` (stdlib) — roda em uma thread separada (ver jobs.py)
para não travar a interface do Blender durante o download.
"""
from __future__ import annotations

import os
import tempfile
import urllib.error
import urllib.request

from . import config
from .github_api import UpdateError


def download_file(url: str, progress_callback=None, chunk_size: int = 65536) -> str:
    """Baixa `url` para um arquivo temporário e retorna o caminho local.

    `progress_callback(fraction: float)` é chamado periodicamente com um
    valor entre 0.0 e 1.0 (ou não é chamado, se o servidor não informar
    o tamanho total do arquivo).
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": config.USER_AGENT,
            "Accept": "application/octet-stream",
        },
    )

    fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="daw_update_")
    os.close(fd)

    try:
        with urllib.request.urlopen(req, timeout=config.DOWNLOAD_TIMEOUT) as resp:
            total = resp.headers.get("Content-Length")
            total = int(total) if total and total.isdigit() else 0
            downloaded = 0

            with open(tmp_path, "wb") as out_file:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        try:
                            progress_callback(min(downloaded / total, 1.0))
                        except Exception:
                            pass
    except urllib.error.URLError as e:
        _safe_remove(tmp_path)
        raise UpdateError(f"Falha no download: {e.reason if hasattr(e, 'reason') else e}") from e
    except Exception as e:
        _safe_remove(tmp_path)
        raise UpdateError(f"Falha no download: {e}") from e

    return tmp_path


def _safe_remove(path: str):
    try:
        os.remove(path)
    except Exception:
        pass