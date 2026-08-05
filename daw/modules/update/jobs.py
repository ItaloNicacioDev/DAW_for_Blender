# modules/update/jobs.py
"""
Ponte thread-safe entre o trabalho de rede/disco (que roda em uma
`threading.Thread` separada, para não travar a UI do Blender) e as
propriedades do Blender (que só podem ser lidas/escritas na thread
principal).

Padrão usado:
    1. Uma thread de trabalho só mexe em `_state` (um dict comum,
       protegido por um Lock) — nunca chama `bpy` diretamente.
    2. Um `bpy.app.timers` registrado nesta (a thread principal) lê
       `_state` periodicamente e copia os valores para
       `context.window_manager.daw_updater`.

Isso evita crashes do Blender por acesso à API bpy fora da thread
principal.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

import bpy

from . import config, downloader, github_api, installer, version
from .github_api import UpdateError

_lock = threading.Lock()
_state = {
    "active": False,
    "status": None,
    "progress": 0.0,
    "latest_version": "",
    "changelog": "",
    "download_url": "",
    "release_url": "",
    "error": "",
    "needs_restart": False,
}

_POLL_INTERVAL = 0.3


def _set(**kwargs):
    with _lock:
        _state.update(kwargs)


def _get() -> dict:
    with _lock:
        return dict(_state)


# ─────────────────────────────────────────────────────────────────
#  Info do addon local (versão atual etc.)
# ─────────────────────────────────────────────────────────────────

def _get_local_bl_info() -> dict:
    top_pkg_name = __package__.split(".")[0]
    top_pkg = sys.modules.get(top_pkg_name)
    return getattr(top_pkg, "bl_info", {}) if top_pkg else {}


def get_local_version_tuple():
    return _get_local_bl_info().get("version", (0, 0, 0))


def get_local_version_str() -> str:
    return version.format_version(get_local_version_tuple())


# ─────────────────────────────────────────────────────────────────
#  Cache em disco (throttling da verificação automática)
# ─────────────────────────────────────────────────────────────────

def _cache_path() -> str:
    config_dir = bpy.utils.user_resource("CONFIG")
    return os.path.join(config_dir, config.CACHE_FILENAME)


def _read_cache() -> dict:
    try:
        with open(_cache_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_cache(data: dict):
    try:
        with open(_cache_path(), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────
#  Sincronização com a UI (roda na thread principal via timer)
# ─────────────────────────────────────────────────────────────────

def _sync_to_wm():
    data = _get()

    try:
        wm = bpy.context.window_manager
        st = wm.daw_update
    except Exception:
        return _POLL_INTERVAL if data["active"] else None

    if data["status"]:
        try:
            st.status = data["status"]
        except Exception:
            pass
    st.progress = data["progress"]
    st.latest_version = data["latest_version"]
    st.changelog = data["changelog"][:2000]
    st.download_url = data["download_url"]
    st.release_url = data["release_url"]
    st.error = data["error"]
    st.needs_restart = data["needs_restart"]

    try:
        screen = bpy.context.screen
        if screen:
            for area in screen.areas:
                if area.type == 'PREFERENCES':
                    area.tag_redraw()
    except Exception:
        pass

    return _POLL_INTERVAL if data["active"] else None


def _ensure_polling():
    if not bpy.app.timers.is_registered(_sync_to_wm):
        bpy.app.timers.register(_sync_to_wm, first_interval=0.1)


# ─────────────────────────────────────────────────────────────────
#  Job: verificar atualização
# ─────────────────────────────────────────────────────────────────

def run_check_update(silent: bool = False):
    """Dispara a verificação em uma thread separada. `silent=True` é
    usado na checagem automática de inicialização: se não houver
    atualização, o status volta para IDLE em vez de UP_TO_DATE, para
    não exibir nada não solicitado ao usuário."""
    if _get()["active"]:
        return

    _set(active=True, status="CHECKING", error="", progress=0.0)
    _ensure_polling()

    def worker():
        try:
            local = get_local_version_tuple()
            release = github_api.get_latest_release_info()
            _write_cache({"last_check": time.time(), "latest_tag": release["tag"]})

            if version.is_newer(release["tag"], local):
                _set(
                    active=False,
                    status="UPDATE_AVAILABLE",
                    latest_version=release["tag"] or version.format_version(
                        version.parse_version(release["tag"])
                    ),
                    changelog=release["changelog"],
                    download_url=release["download_url"],
                    release_url=release["html_url"],
                    error="",
                )
            else:
                _set(
                    active=False,
                    status="IDLE" if silent else "UP_TO_DATE",
                    latest_version=release["tag"],
                    changelog="",
                    download_url="",
                    error="",
                )
        except UpdateError as e:
            _set(active=False, status="IDLE" if silent else "ERROR", error=str(e))
        except Exception as e:
            _set(active=False, status="IDLE" if silent else "ERROR", error=f"Erro inesperado: {e}")

    threading.Thread(target=worker, daemon=True).start()


# ─────────────────────────────────────────────────────────────────
#  Job: baixar + instalar atualização
# ─────────────────────────────────────────────────────────────────

def run_download_and_install(download_url: str):
    if _get()["active"]:
        return

    _set(active=True, status="DOWNLOADING", progress=0.0, error="")
    _ensure_polling()

    def worker():
        zip_path = None
        try:
            def on_progress(fraction):
                _set(progress=fraction)

            zip_path = downloader.download_file(download_url, progress_callback=on_progress)

            _set(status="INSTALLING", progress=1.0)
            installer.install_update(zip_path)

            _set(
                active=False,
                status="DONE_INSTALL",
                needs_restart=True,
                error="",
            )
        except UpdateError as e:
            _set(active=False, status="ERROR", error=str(e))
        except Exception as e:
            _set(active=False, status="ERROR", error=f"Erro inesperado: {e}")
        finally:
            if zip_path:
                installer.cleanup_paths(zip_path)

    threading.Thread(target=worker, daemon=True).start()


# ─────────────────────────────────────────────────────────────────
#  Checagem automática ao iniciar o Blender (com throttling)
# ─────────────────────────────────────────────────────────────────

def maybe_auto_check_on_startup():
    try:
        addon_key = __package__.split(".")[0]
        prefs = bpy.context.preferences.addons[addon_key].preferences
        if not prefs.check_for_updates:
            return
    except Exception:
        return

    cache = _read_cache()
    last_check = cache.get("last_check", 0)
    elapsed_hours = (time.time() - last_check) / 3600.0

    if elapsed_hours < config.CHECK_INTERVAL_HOURS:
        return

    run_check_update(silent=True)