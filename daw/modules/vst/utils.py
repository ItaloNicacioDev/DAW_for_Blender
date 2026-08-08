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