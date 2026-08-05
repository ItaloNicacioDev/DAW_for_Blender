# modules/update/github_api.py
"""
Cliente mínimo da API pública do GitHub, usando apenas a biblioteca
padrão (urllib) — sem `requests` nem nenhuma dependência externa,
seguindo a mesma regra usada no resto do addon (compatibilidade com
Blender "puro", incluindo builds rodando via Termux/Android).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import config


class UpdateError(Exception):
    """Erro genérico do sistema de atualização (rede, parsing, etc)."""


def _request_json(url: str, allow_404: bool = False):
    """Faz o request e retorna o JSON decodificado.

    Se `allow_404=True` e o servidor responder 404, retorna `None` em vez
    de lançar `UpdateError` — usado por `fetch_latest_release()` para
    tentar o endpoint "/latest" antes de cair no fallback da listagem.
    """
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": config.USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            if allow_404:
                return None
            raise UpdateError(
                "Repositório ou release não encontrado (verifique GITHUB_OWNER/"
                "GITHUB_REPO em modules/update/config.py)."
            ) from e
        if e.code == 403:
            raise UpdateError(
                "Limite de requisições da API do GitHub atingido. Tente novamente "
                "mais tarde."
            ) from e
        raise UpdateError(f"Erro HTTP {e.code} ao consultar o GitHub.") from e
    except urllib.error.URLError as e:
        raise UpdateError(f"Sem conexão com o GitHub: {e.reason}") from e
    except Exception as e:
        raise UpdateError(f"Erro inesperado ao consultar o GitHub: {e}") from e

    try:
        return json.loads(raw)
    except Exception as e:
        raise UpdateError(f"Resposta inválida da API do GitHub: {e}") from e


def fetch_latest_release() -> dict:
    """Retorna o JSON do release mais recente.

    Tenta primeiro o endpoint oficial "/releases/latest" (só retorna
    release estável, não pre-release). Se não houver nenhuma release
    estável publicada ainda (404 — comum durante a fase beta, onde tudo
    é pre-release), cai para a listagem "/releases" — que inclui
    pre-releases — e pega o primeiro item (mais recente).
    """
    data = _request_json(config.api_latest_release_url(), allow_404=True)
    if data is not None:
        return data

    releases = _request_json(config.api_releases_list_url())
    if not isinstance(releases, list) or not releases:
        raise UpdateError(
            "Nenhum release encontrado no repositório (verifique GITHUB_OWNER/"
            "GITHUB_REPO em modules/update/config.py, e se há pelo menos um "
            "release publicado, mesmo que pre-release)."
        )
    return releases[0]


def parse_release(data: dict) -> dict:
    """Extrai as informações relevantes do JSON de um release.

    Retorna:
        {
            "tag": "v0.19.0",
            "name": "0.19.0 — Auto-update",
            "changelog": "texto do corpo do release...",
            "download_url": "https://.../daw-0.19.0.zip",
            "is_source_zip": False,
            "html_url": "https://github.com/.../releases/tag/v0.19.0",
        }
    """
    tag = data.get("tag_name") or data.get("name") or ""
    name = data.get("name") or tag
    changelog = (data.get("body") or "").strip()
    html_url = data.get("html_url") or config.releases_page_url()

    download_url = None
    for asset in data.get("assets", []) or []:
        asset_name = (asset.get("name") or "").lower()
        if asset_name.endswith(".zip"):
            download_url = asset.get("browser_download_url")
            break

    is_source_zip = False
    if not download_url:
        download_url = data.get("zipball_url")
        is_source_zip = True

    if not download_url:
        raise UpdateError("O release mais recente não possui nenhum arquivo .zip.")

    return {
        "tag": tag,
        "name": name,
        "changelog": changelog,
        "download_url": download_url,
        "is_source_zip": is_source_zip,
        "html_url": html_url,
    }


def get_latest_release_info() -> dict:
    """Busca e já retorna o release mais recente já processado."""
    data = fetch_latest_release()
    return parse_release(data)