# modules/update/installer.py
"""
Instalação da atualização já baixada: extrai o .zip, localiza a pasta
real do addon dentro dele (não importa como o .zip está organizado),
faz backup da instalação atual e substitui os arquivos.

Nenhuma função aqui toca a API do bpy — só faz operações de arquivo,
para poder rodar com segurança em uma thread separada da UI do Blender
(ver jobs.py).
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
import zipfile

from .github_api import UpdateError


def addon_root_from_this_file() -> str:
    """Retorna o caminho da pasta raiz do addon (a pasta "daw/", que
    contém o __init__.py com bl_info), a partir da localização deste
    arquivo (daw/modules/update/installer.py)."""
    this_dir = os.path.dirname(os.path.abspath(__file__))   # .../daw/modules/update
    modules_dir = os.path.dirname(this_dir)                  # .../daw/modules
    addon_root = os.path.dirname(modules_dir)                # .../daw
    return addon_root


def extract_zip(zip_path: str) -> str:
    """Extrai o .zip para uma pasta temporária e retorna o caminho dela."""
    extract_dir = tempfile.mkdtemp(prefix="daw_update_extract_")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            _validate_zip_members(zf, extract_dir)
            zf.extractall(extract_dir)
    except zipfile.BadZipFile as e:
        raise UpdateError("O arquivo baixado não é um .zip válido.") from e
    except Exception as e:
        raise UpdateError(f"Falha ao extrair o pacote: {e}") from e
    return extract_dir


def _validate_zip_members(zf: zipfile.ZipFile, extract_dir: str):
    """Bloqueia entradas de zip maliciosas (path traversal / "zip slip")."""
    extract_dir_abs = os.path.abspath(extract_dir)
    for member in zf.namelist():
        member_path = os.path.abspath(os.path.join(extract_dir, member))
        if not member_path.startswith(extract_dir_abs + os.sep) and member_path != extract_dir_abs:
            raise UpdateError(f"Entrada suspeita no .zip: {member}")


def find_package_dir(extracted_root: str) -> str:
    """Procura, dentro da pasta extraída, o diretório que contém o
    __init__.py com bl_info — ou seja, a verdadeira pasta do addon,
    não importa o nome do wrapper que o GitHub/release usou."""
    for current_dir, _dirnames, filenames in os.walk(extracted_root):
        if "__init__.py" not in filenames:
            continue
        init_path = os.path.join(current_dir, "__init__.py")
        try:
            with open(init_path, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(4096)
        except Exception:
            continue
        if "bl_info" in head:
            return current_dir

    raise UpdateError(
        "Não foi possível encontrar a pasta do addon (com bl_info) dentro "
        "do pacote baixado."
    )


def backup_current_install(addon_root: str) -> str:
    """Copia a instalação atual para uma pasta de backup ao lado dela e
    retorna o caminho do backup."""
    parent = os.path.dirname(addon_root)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(parent, f"_daw_backup_{stamp}")

    if os.path.exists(backup_path):
        shutil.rmtree(backup_path, ignore_errors=True)

    shutil.copytree(addon_root, backup_path)
    return backup_path


def restore_backup(addon_root: str, backup_path: str):
    if not os.path.isdir(backup_path):
        return
    if os.path.isdir(addon_root):
        shutil.rmtree(addon_root, ignore_errors=True)
    shutil.move(backup_path, addon_root)


def replace_addon_files(addon_root: str, new_package_dir: str):
    """Substitui o conteúdo de `addon_root` pelo conteúdo de
    `new_package_dir`. Preserva a pasta `template/` (conteúdo de
    usuário) se ela não existir no pacote novo, para não apagar dados
    do usuário à toa."""
    preserved = {}
    for keep_name in ("template",):
        keep_src = os.path.join(addon_root, keep_name)
        keep_dst = os.path.join(new_package_dir, keep_name)
        if os.path.isdir(keep_src) and not os.path.isdir(keep_dst):
            preserved[keep_name] = keep_src

    # Remove tudo dentro de addon_root, exceto o que será preservado.
    for entry in os.listdir(addon_root):
        if entry in preserved:
            continue
        full = os.path.join(addon_root, entry)
        if os.path.isdir(full):
            shutil.rmtree(full, ignore_errors=True)
        else:
            try:
                os.remove(full)
            except Exception:
                pass

    # Copia os arquivos novos para dentro de addon_root.
    for entry in os.listdir(new_package_dir):
        src = os.path.join(new_package_dir, entry)
        dst = os.path.join(addon_root, entry)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


def cleanup_paths(*paths: str):
    for path in paths:
        if not path:
            continue
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass


def install_update(zip_path: str) -> dict:
    """Fluxo completo: extrai, localiza o pacote, faz backup, substitui.

    Retorna {"addon_root": ..., "backup_path": ...} em caso de sucesso.
    Em caso de erro, tenta restaurar o backup automaticamente antes de
    relançar a exceção.
    """
    addon_root = addon_root_from_this_file()
    extract_dir = extract_zip(zip_path)
    backup_path = None

    try:
        new_package_dir = find_package_dir(extract_dir)
        backup_path = backup_current_install(addon_root)
        replace_addon_files(addon_root, new_package_dir)
    except Exception:
        if backup_path:
            restore_backup(addon_root, backup_path)
        raise
    finally:
        cleanup_paths(extract_dir)

    return {"addon_root": addon_root, "backup_path": backup_path}