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


def scan_whole_system(recursive: bool = True, extra_directories: str = "") -> List[Dict[str, str]]:
    """
    Varredura completa: pastas adicionadas manualmente pelo usuário +
    pastas padrão do SO + pastas do Registro (Windows) + TODOS os discos
    do sistema (pulando pastas de sistema conhecidas por serem grandes e
    irrelevantes, ver `_SKIP_DIR_NAMES`).

    Pode demorar bastante num disco cheio -- é pensada pra rodar em
    background (ver DAW_OT_ScanVstDirectoriesAsync) e ter o resultado
    cacheado depois (ver `save_scan_cache`/`load_scan_cache`), pra não
    precisar repetir isso toda vez que o Blender abre.
    """
    results: List[Dict[str, str]] = []
    seen_paths = set()

    def _add_all(directory: str):
        for item in scan_directory_for_vsts(directory, recursive=recursive):
            if item["path"] not in seen_paths:
                seen_paths.add(item["path"])
                results.append(item)

    # 1. Pastas manuais do usuário (mais rápido, prioridade primeiro)
    for raw in extra_directories.split(";"):
        directory = raw.strip()
        if directory:
            _add_all(directory)

    # 2. Pastas padrão do SO
    for directory in get_default_vst_search_paths():
        _add_all(directory)

    # 3. Pastas customizadas do Registro do Windows
    for directory in get_registry_vst_paths():
        _add_all(directory)

    # 4. Todos os discos -- a parte pesada. Usa os.walk manual aqui (em
    # vez de reusar scan_directory_for_vsts por disco inteiro) só pra
    # poder filtrar _SKIP_DIR_NAMES antes de descer, economizando tempo
    # de verdade em pastas gigantes e irrelevantes tipo Windows/.
    for root in get_all_drive_roots():
        try:
            walk_iter = os.walk(root, onerror=lambda e: None, followlinks=False)
        except OSError:
            continue
        for dirpath, dirnames, filenames in walk_iter:
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR_NAMES]

            for dirname in list(dirnames):
                if Path(dirname).suffix.lower() in (".vst3", ".vst"):
                    entry = Path(dirpath) / dirname
                    if str(entry) not in seen_paths:
                        seen_paths.add(str(entry))
                        fmt = "VST3" if entry.suffix.lower() == ".vst3" else "VST2"
                        results.append({"path": str(entry), "name": entry.stem, "format": fmt})

            for filename in filenames:
                entry = Path(dirpath) / filename
                if entry.suffix.lower() not in _VST_EXTENSIONS:
                    continue
                if str(entry) in seen_paths:
                    continue
                try:
                    fmt = detect_plugin_format(entry)
                except OSError:
                    continue
                if fmt == "UNKNOWN":
                    continue
                seen_paths.add(str(entry))
                results.append({"path": str(entry), "name": entry.stem, "format": fmt})

            dirnames[:] = [d for d in dirnames if Path(d).suffix.lower() not in (".vst3", ".vst")]

    return results


# ═══════════════════════════════════════════════════════════════
#  CACHE PERSISTENTE: evita reescanear o PC inteiro toda vez que o
#  Blender abre. Fica num JSON na pasta de config do usuário (não no
#  .blend, então persiste entre projetos diferentes).
# ═══════════════════════════════════════════════════════════════

def _cache_file_path() -> Path:
    import bpy
    config_dir = Path(bpy.utils.user_resource('CONFIG', path="daw", create=True))
    return config_dir / "vst_scan_cache.json"


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