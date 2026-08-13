# modules/vst/utils.py
"""
Utilitários do módulo VST.

Responsabilidade:
    - Registro global (em memória) que liga cada item RNA (identificado
      por vst_id) a um objeto `VST` puro real, dono do estado processado
      por dawdreamer. PropertyGroups do Blender não podem guardar objetos
      Python arbitrários, então o registro vive fora do RNA.
    - Sincronização RNA <-> modelo puro.
    - Varredura de diretórios em busca de plugins .vst3 / .dll / .so / .vst.
    - Obter/criar cadeias de efeito VST por canal.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from .vst import VST, VSTProgramType
from .engine import detect_plugin_format

if TYPE_CHECKING:
    from .properties import DawVstProperty, DawVstChainProperty, DawVstRackProperty


# ═══════════════════════════════════════════════════════════════
#  REGISTRO GLOBAL: vst_id -> VST (modelo puro, com estado real)
# ═══════════════════════════════════════════════════════════════

_LIVE_VSTS: Dict[str, VST] = {}


def get_live_vst(vst_id: str) -> Optional[VST]:
    """Retorna o objeto VST puro (com estado carregado) para um vst_id, se existir."""
    return _LIVE_VSTS.get(vst_id)


def register_live_vst(vst: VST) -> None:
    """Registra/atualiza o objeto VST puro no registro global."""
    _LIVE_VSTS[vst.vst_id] = vst


def unregister_live_vst(vst_id: str) -> None:
    """Remove um objeto VST puro do registro global."""
    _LIVE_VSTS.pop(vst_id, None)


def get_or_create_live_vst(prop: "DawVstProperty") -> VST:
    """
    Retorna o objeto VST puro associado a este item RNA, criando-o a
    partir dos campos RNA se ainda não existir no registro.
    """
    vst = get_live_vst(prop.vst_id)
    if vst is not None:
        return vst

    vst = VST(
        path=prop.vst_path,
        name=prop.vst_name,
        vst_type=VSTProgramType(prop.vst_type),
        vst_id=prop.vst_id,
        bypass=prop.bypass,
    )
    register_live_vst(vst)
    return vst


def sync_rna_from_pure(prop: "DawVstProperty", vst: VST) -> None:
    """Copia o estado do modelo puro (pós-carregamento real) de volta para o RNA."""
    prop.vst_name = vst.name
    prop.is_loaded = vst.loaded
    prop.error_message = vst.error or ""
    prop.bypass = vst.bypass

    prop.parameters.clear()
    for param_id, info in sorted(vst.parameter_info.items()):
        item = prop.parameters.add()
        item.param_id = param_id
        item.param_name = info.name
        item.param_value = vst.parameters.get(param_id, info.value)
        item.param_label = info.label
        item.is_automatable = info.is_automatable


def sync_pure_bypass(prop: "DawVstProperty") -> None:
    """Propaga o bypass do RNA para o objeto puro correspondente, se já existir."""
    vst = get_live_vst(prop.vst_id)
    if vst is not None:
        vst.bypass = prop.bypass


# ═══════════════════════════════════════════════════════════════
#  CADEIAS / RACKS
# ═══════════════════════════════════════════════════════════════

def clamp_index(index: int, length: int) -> int:
    """Restringe um índice ao range válido [0, length-1]. Retorna 0 se length <= 0."""
    if length <= 0:
        return 0
    return max(0, min(index, length - 1))


def get_chain(scene, channel_index: int) -> Optional["DawVstChainProperty"]:
    """Retorna a cadeia de efeitos VST de um canal, ou None se não existir."""
    for chain in scene.daw_vst_chains:
        if chain.chain_id == str(channel_index):
            return chain
    return None


def get_or_create_chain(scene, channel_index: int) -> "DawVstChainProperty":
    """Retorna a cadeia de efeitos VST de um canal, criando-a se necessário."""
    chain = get_chain(scene, channel_index)
    if chain is not None:
        return chain
    chain = scene.daw_vst_chains.add()
    chain.chain_id = str(channel_index)
    return chain


def make_unique_vst_id(base_name: str, existing_ids: List[str]) -> str:
    """Gera um vst_id único a partir do nome do plugin, evitando colisões."""
    slug = base_name.lower().strip().replace(" ", "_")
    slug = "".join(c for c in slug if c.isalnum() or c == "_") or "vst"
    candidate = slug
    n = 1
    while candidate in existing_ids:
        n += 1
        candidate = f"{slug}_{n}"
    return candidate


# ═══════════════════════════════════════════════════════════════
#  VARREDURA DE DIRETÓRIOS
# ═══════════════════════════════════════════════════════════════

_VST_EXTENSIONS = {".vst3", ".dll", ".so", ".dylib", ".vst"}


def scan_directory_for_vsts(directory: str, recursive: bool = True) -> List[Dict[str, str]]:
    """
    Varre um diretório em busca de arquivos de plugin VST2/VST3.

    Retorna lista de dicts: {"path", "name", "format"}.
    Nunca levanta exceção — diretórios inválidos retornam lista vazia.

    Resiliente a erros por entrada: usa os.walk com onerror silencioso,
    então uma pasta sem permissão (comum em sync de nuvem, symlinks
    quebrados etc.) no meio da árvore não aborta o resto da varredura
    -- só pula aquele ponto e continua. Antes, um erro no meio de um
    Path.rglob() interrompia o loop inteiro e descartava tudo que
    viria depois dele silenciosamente.
    """
    results: List[Dict[str, str]] = []
    root = Path(directory).expanduser()
    if not root.exists() or not root.is_dir():
        return results

    def _on_walk_error(_err: OSError) -> None:
        pass  # ignora e continua a varredura no resto da árvore

    if recursive:
        walk_iter = os.walk(root, onerror=_on_walk_error, followlinks=False)
    else:
        try:
            entries = list(root.iterdir())
        except (PermissionError, OSError):
            entries = []
        walk_iter = [(str(root), [], [e.name for e in entries if e.is_file()])]

    for dirpath, dirnames, filenames in walk_iter:
        # Bundles .vst3/.vst podem ser PASTAS (comum no Windows/macOS),
        # não só arquivos únicos -- checa os dois.
        for dirname in list(dirnames):
            if Path(dirname).suffix.lower() in (".vst3", ".vst"):
                entry = Path(dirpath) / dirname
                fmt = "VST3" if entry.suffix.lower() == ".vst3" else "VST2"
                results.append({
                    "path": str(entry),
                    "name": entry.stem,
                    "format": fmt,
                })

        for filename in filenames:
            entry = Path(dirpath) / filename
            if entry.suffix.lower() not in _VST_EXTENSIONS:
                continue
            try:
                fmt = detect_plugin_format(entry)
            except OSError:
                continue
            if fmt == "UNKNOWN":
                continue
            results.append({
                "path": str(entry),
                "name": entry.stem,
                "format": fmt,
            })

        # Não desce dentro de bundles .vst3/.vst já identificados como
        # plugin (evita listar o binário interno como um plugin
        # separado -- era a causa das duplicatas tipo "BBC Symphony
        # Orchestra" aparecendo duas vezes: uma como bundle, outra como
        # o binário de dentro dele).
        dirnames[:] = [
            d for d in dirnames
            if Path(d).suffix.lower() not in (".vst3", ".vst")
        ]

    return results


def scan_multiple_directories(directories: str, recursive: bool = True) -> List[Dict[str, str]]:
    """Varre múltiplos diretórios separados por ';' (formato usado em vst_directories)."""
    results: List[Dict[str, str]] = []
    seen_paths = set()
    for raw in directories.split(";"):
        directory = raw.strip()
        if not directory:
            continue
        for item in scan_directory_for_vsts(directory, recursive=recursive):
            if item["path"] not in seen_paths:
                seen_paths.add(item["path"])
                results.append(item)
    return results


# ═══════════════════════════════════════════════════════════════
#  DESCOBERTA AUTOMÁTICA: pastas padrão do SO + registro do Windows
#  + todos os discos -- pra não depender só do que o usuário adiciona
#  manualmente.
# ═══════════════════════════════════════════════════════════════

# Nomes de pasta que nunca valem a pena descer -- ou são gigantes e
# irrelevantes (Windows, node_modules) ou são pastas de sistema que só
# geram erro de permissão sem nunca conter um VST de verdade.
_SKIP_DIR_NAMES = {
    "Windows", "$Recycle.Bin", "System Volume Information", "node_modules",
    ".git", ".svn", "AppData", "$WinREAgent", "Recovery", "PerfLogs",
    "Config.Msi", "MSOCache", "$SysReset",
}


def get_default_vst_search_paths() -> List[str]:
    """Pastas onde plugins VST2/VST3 costumam ser instalados por padrão,
    por sistema operacional. Sempre incluídas na varredura, além do que
    o usuário adiciona manualmente."""
    paths: List[str] = []

    if os.name == "nt":
        for env_var in ("ProgramFiles", "ProgramFiles(x86)", "CommonProgramFiles", "CommonProgramFiles(x86)"):
            base = os.environ.get(env_var)
            if not base:
                continue
            paths.extend([
                os.path.join(base, "VST3"),
                os.path.join(base, "VSTPlugins"),
                os.path.join(base, "Steinberg", "VSTPlugins"),
                os.path.join(base, "Common Files", "VST3"),
                os.path.join(base, "Common Files", "VSTPlugins"),
            ])
    elif sys_platform_is_mac():
        home = str(Path.home())
        paths.extend([
            "/Library/Audio/Plug-Ins/VST",
            "/Library/Audio/Plug-Ins/VST3",
            "/Library/Audio/Plug-Ins/Components",
            os.path.join(home, "Library/Audio/Plug-Ins/VST"),
            os.path.join(home, "Library/Audio/Plug-Ins/VST3"),
        ])
    else:  # Linux
        home = str(Path.home())
        paths.extend([
            "/usr/lib/vst3", "/usr/lib/vst", "/usr/local/lib/vst3", "/usr/local/lib/vst",
            os.path.join(home, ".vst3"), os.path.join(home, ".vst"),
        ])

    # Remove duplicatas mantendo ordem, e só devolve pastas que existem
    seen = set()
    existing = []
    for p in paths:
        if p not in seen and os.path.isdir(p):
            seen.add(p)
            existing.append(p)
    return existing


def sys_platform_is_mac() -> bool:
    import sys as _sys
    return _sys.platform == "darwin"


def get_registry_vst_paths() -> List[str]:
    """
    No Windows, alguns instaladores registram a pasta de VST num lugar
    customizado via Registro, em vez de usar as pastas padrão. Consulta
    as chaves conhecidas. Sem efeito (lista vazia) fora do Windows.
    """
    if os.name != "nt":
        return []

    paths: List[str] = []
    try:
        import winreg
    except ImportError:
        return []

    keys_to_check = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\VST3", "VST3PluginPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\VST3", "VST3PluginPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\VST", "VSTPluginsPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\VST", "VSTPluginsPath"),
    ]
    for hive, subkey, value_name in keys_to_check:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _type = winreg.QueryValueEx(key, value_name)
                if value and os.path.isdir(value):
                    paths.append(value)
        except (FileNotFoundError, OSError):
            continue

    return paths


def get_all_drive_roots() -> List[str]:
    """Todos os discos/drives disponíveis no sistema (pra varredura
    'PC inteiro'). No Windows, letras de A: a Z:; em Unix, só '/'."""
    if os.name == "nt":
        import string
        drives = []
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.isdir(root):
                drives.append(root)
        return drives
    return ["/"]


# ═══════════════════════════════════════════════════════════════
#  VARREDURA INCREMENTAL: mesma ideia do FL Studio -- guarda a data de
#  modificação (mtime) de cada pasta já visitada. Numa nova varredura,
#  se a pasta não mudou desde a última vez, reaproveita o que já foi
#  achado nela sem tocar o disco de novo (nem sequer listar o
#  conteúdo). Isso é o que torna scans repetidos rápidos -- só pastas
#  novas ou modificadas (plugin instalado/removido) são revisitadas de
#  verdade.
# ═══════════════════════════════════════════════════════════════

def _scan_dir_incremental(
    root: str,
    old_cache: Dict[str, dict],
    new_cache: Dict[str, dict],
    results: List[Dict[str, str]],
    seen_paths: set,
) -> None:
    """Varre `root` recursivamente, usando/atualizando `old_cache`/`new_cache`
    (dict: caminho_normalizado -> {"mtime": float, "subdirs": [...], "plugins": [...]})."""
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            current_mtime = os.stat(current).st_mtime
        except OSError:
            continue

        cached_entry = old_cache.get(current)
        if cached_entry is not None and cached_entry.get("mtime") == current_mtime:
            # Pasta não mudou desde o último scan -- reaproveita sem
            # tocar o disco. Ainda assim empilha as subpastas conhecidas
            # pra checar CADA UMA independentemente (uma subpasta pode
            # ter mudado mesmo que esta aqui não tenha).
            new_cache[current] = cached_entry
            for entry in cached_entry.get("plugins", []):
                if entry["path"] not in seen_paths:
                    seen_paths.add(entry["path"])
                    results.append(entry)
            for sub in cached_entry.get("subdirs", []):
                stack.append(sub)
            continue

        # Pasta nova ou modificada -- lista de verdade.
        try:
            with os.scandir(current) as it:
                dir_entries = list(it)
        except OSError:
            continue

        subdirs: List[str] = []
        plugins_here: List[Dict[str, str]] = []

        for entry in dir_entries:
            name = entry.name
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue

            if is_dir:
                if name in _SKIP_DIR_NAMES:
                    continue
                suffix = Path(name).suffix.lower()
                if suffix in (".vst3", ".vst"):
                    # Bundle .vst3/.vst como pasta -- conta como plugin,
                    # NÃO desce pra dentro (evita duplicar o binário
                    # interno como plugin separado).
                    full = str(Path(current) / name)
                    fmt = "VST3" if suffix == ".vst3" else "VST2"
                    plugin_entry = {"path": full, "name": Path(name).stem, "format": fmt}
                    plugins_here.append(plugin_entry)
                else:
                    full = str(Path(current) / name)
                    subdirs.append(full)
            else:
                suffix = Path(name).suffix.lower()
                if suffix not in _VST_EXTENSIONS:
                    continue
                full = Path(current) / name
                try:
                    fmt = detect_plugin_format(full)
                except OSError:
                    continue
                if fmt == "UNKNOWN":
                    continue
                plugins_here.append({"path": str(full), "name": full.stem, "format": fmt})

        new_cache[current] = {"mtime": current_mtime, "subdirs": subdirs, "plugins": plugins_here}
        for entry in plugins_here:
            if entry["path"] not in seen_paths:
                seen_paths.add(entry["path"])
                results.append(entry)
        stack.extend(subdirs)


def scan_whole_system(
    recursive: bool = True,
    extra_directories: str = "",
    use_cache: bool = True,
    progress_callback=None,
) -> List[Dict[str, str]]:
    """
    Varredura completa: pastas adicionadas manualmente pelo usuário +
    pastas padrão do SO + pastas do Registro (Windows) + TODOS os discos
    do sistema (pulando pastas de sistema conhecidas por serem grandes e
    irrelevantes, ver `_SKIP_DIR_NAMES`).

    Incremental (estilo FL Studio): reaproveita o cache por pasta
    (mtime) da varredura anterior -- só pastas novas ou modificadas
    desde então são realmente visitadas no disco. A primeira varredura
    ainda precisa tocar tudo (não tem cache pra reaproveitar), mas as
    seguintes ficam bem mais rápidas.

    Paraleliza a varredura entre os discos/pastas de topo (a maior
    parte do tempo é esperando o disco responder, não CPU -- múltiplas
    threads ajudam de verdade aqui mesmo com o GIL).
    """
    import concurrent.futures

    results: List[Dict[str, str]] = []
    seen_paths: set = set()
    old_dir_cache = load_dir_cache() if use_cache else {}
    new_dir_cache: Dict[str, dict] = {}

    roots: List[str] = []

    for raw in extra_directories.split(";"):
        directory = raw.strip()
        if directory:
            roots.append(directory)

    roots.extend(get_default_vst_search_paths())
    roots.extend(get_registry_vst_paths())
    roots.extend(get_all_drive_roots())

    # Remove duplicatas/subpastas redundantes mantendo ordem (ex.: se
    # "C:\" já está na lista, não precisa escanear "C:\Program Files"
    # separadamente também -- seria trabalho repetido).
    roots = sorted(set(roots), key=len)
    deduped_roots: List[str] = []
    for r in roots:
        r_norm = os.path.normcase(os.path.normpath(r))
        if not any(
            r_norm != os.path.normcase(os.path.normpath(existing))
            and r_norm.startswith(os.path.normcase(os.path.normpath(existing)) + os.sep)
            for existing in deduped_roots
        ):
            deduped_roots.append(r)

    lock = threading.Lock()
    done_count = [0]

    def _worker(root: str):
        local_results: List[Dict[str, str]] = []
        local_seen: set = set()
        local_cache: Dict[str, dict] = {}
        _scan_dir_incremental(root, old_dir_cache, local_cache, local_results, local_seen)
        with lock:
            for entry in local_results:
                if entry["path"] not in seen_paths:
                    seen_paths.add(entry["path"])
                    results.append(entry)
            new_dir_cache.update(local_cache)
            done_count[0] += 1
            if progress_callback:
                progress_callback(done_count[0], len(deduped_roots))

    max_workers = min(8, max(1, len(deduped_roots)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(_worker, deduped_roots))

    if use_cache:
        save_dir_cache(new_dir_cache)

    return results


# ═══════════════════════════════════════════════════════════════
#  CACHE PERSISTENTE
#
#  Dois arquivos, propósitos diferentes:
#    - vst_scan_cache.json  : lista final de plugins (o que a UI mostra
#                              instantaneamente ao abrir o Blender)
#    - vst_dir_cache.json   : mtime por pasta visitada (o que torna o
#                              PRÓXIMO scan completo rápido -- pastas
#                              inalteradas nem são tocadas de novo)
#
#  Ficam na pasta de config do usuário (fora do .blend), então
#  persistem entre projetos diferentes.
# ═══════════════════════════════════════════════════════════════

def _cache_file_path() -> Path:
    import bpy
    config_dir = Path(bpy.utils.user_resource('CONFIG', path="daw", create=True))
    return config_dir / "vst_scan_cache.json"


def _dir_cache_file_path() -> Path:
    import bpy
    config_dir = Path(bpy.utils.user_resource('CONFIG', path="daw", create=True))
    return config_dir / "vst_dir_cache.json"


def save_scan_cache(found: List[Dict[str, str]]) -> None:
    import json
    import time as _time

    payload = {
        "version": 1,
        "scanned_at": _time.time(),
        "plugins": found,
    }
    try:
        with open(_cache_file_path(), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[DAW VST] Falha ao salvar cache de scan: {e}")


def load_scan_cache() -> Optional[List[Dict[str, str]]]:
    """Retorna a lista de plugins do último scan salvo, ou None se não
    existir cache ainda (primeira vez usando o addon)."""
    import json

    path = _cache_file_path()
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("plugins", [])
    except (OSError, json.JSONDecodeError) as e:
        print(f"[DAW VST] Falha ao ler cache de scan: {e}")
        return None


def get_scan_cache_timestamp() -> Optional[float]:
    import json

    path = _cache_file_path()
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("scanned_at")
    except (OSError, json.JSONDecodeError):
        return None


def save_dir_cache(dir_cache: Dict[str, dict]) -> None:
    """Salva o cache por pasta (mtime + subpastas + plugins achados),
    usado pra acelerar a PRÓXIMA varredura completa."""
    import json

    try:
        with open(_dir_cache_file_path(), "w", encoding="utf-8") as f:
            json.dump(dir_cache, f, ensure_ascii=False)
    except OSError as e:
        print(f"[DAW VST] Falha ao salvar cache de pastas: {e}")


def load_dir_cache() -> Dict[str, dict]:
    import json

    path = _dir_cache_file_path()
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[DAW VST] Falha ao ler cache de pastas: {e}")
        return {}


def clear_dir_cache() -> None:
    """Apaga o cache por pasta -- força a próxima varredura completa a
    tocar tudo do zero (útil se o cache ficar de alguma forma
    inconsistente, ou pra forçar uma re-checagem total)."""
    try:
        path = _dir_cache_file_path()
        if path.is_file():
            path.unlink()
    except OSError as e:
        print(f"[DAW VST] Falha ao limpar cache de pastas: {e}")