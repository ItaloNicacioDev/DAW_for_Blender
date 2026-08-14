# modules/vst/__init__.py
"""
Módulo VST da DAW.

Arquitetura (arquivos novos/alterados marcados com *):
    vst.py            — modelo puro de um plugin VST (sem bpy)
    engine.py         — utilitários de plugin (detecção de formato VST2/VST3)
    ipc_engine.py   * — motor real de processamento: cliente IPC pro worker
                        externo (vendorizado, ver vst_worker/), que hospeda
                        o dawdreamer de verdade num Python separado
    pressets.py       — presets embutidos + presets do usuário (JSON)
    utils.py          — registro global vst_id -> VST puro, varredura
    properties.py   * — PropertyGroups (+ scroll, busca, auto-bounce, sounddevice)
    operators.py    * — Operators (+ MoveVst, ScanAsync, AutoBounce, LiveMonitor,
                        DeletePreset, Export/ImportPresetLibrary)
    ui.py           * — Painéis (+ scroll de parâmetros, reorder, lista de presets,
                        monitor ao vivo, scan assíncrono)
    live_monitor.py * — NOVO: thread de áudio para monitor ao vivo via microfone
    persistence.py  * — NOVO: serialize/restore VST state no projeto (.json)
    register.py     * — register/unregister (+ handlers de load_pre/auto-scan,
                        desliga o worker de VST no unregister)

Integração com project/save.py — adicione ao final de _serialize_scene():
    from ..vst import persistence as vst_persistence
    data["vst"] = vst_persistence.serialize_vst_state(scene)

Integração com project/load.py — adicione após carregar os outros módulos:
    from ..vst import persistence as vst_persistence
    vst_persistence.restore_vst_state(scene, data.get("vst", {}), context)
"""
from __future__ import annotations

try:
    import bpy  # noqa: F401
except ImportError:  # pragma: no cover - allows test/CLI usage outside Blender
    bpy = None

from .vst import VST, VSTProgramType, VSTProgramParameter, VSTProgramState
from . import engine
from . import ipc_engine

if bpy is not None:
    from . import timeline_bridge
    from . import persistence
    from . import live_monitor
    from .pressets import get_preset_manager, VSTProgramPresetManager
    from .utils import (
        get_live_vst,
        register_live_vst,
        unregister_live_vst,
        get_or_create_live_vst,
        sync_rna_from_pure,
        sync_pure_bypass,
        clamp_index,
        get_chain,
        get_or_create_chain,
        make_unique_vst_id,
        scan_directory_for_vsts,
        scan_multiple_directories,
    )
    from .register import register, unregister
else:
    get_preset_manager = None
    VSTProgramPresetManager = None
    timeline_bridge = None
    persistence = None
    live_monitor = None
    get_live_vst = None
    register_live_vst = None
    unregister_live_vst = None
    get_or_create_live_vst = None
    sync_rna_from_pure = None
    sync_pure_bypass = None
    clamp_index = None
    get_chain = None
    get_or_create_chain = None
    make_unique_vst_id = None
    scan_directory_for_vsts = None
    scan_multiple_directories = None
    register = None
    unregister = None

__all__ = [
    # Modelo puro
    "VST", "VSTProgramType", "VSTProgramParameter", "VSTProgramState",
    # Utilitários de plugin (detecção de formato)
    "engine",
    # Motor real (worker IPC vendorizado)
    "ipc_engine",
    # Ponte com a timeline nativa do Blender
    "timeline_bridge",
    # Persistência (save/load de projeto)
    "persistence",
    # Monitor ao vivo (microfone -> VST effects -> saída)
    "live_monitor",
    # Presets
    "get_preset_manager", "VSTProgramPresetManager",
    # Ponte RNA <-> puro
    "get_live_vst", "register_live_vst", "unregister_live_vst", "get_or_create_live_vst",
    "sync_rna_from_pure", "sync_pure_bypass", "clamp_index",
    "get_chain", "get_or_create_chain", "make_unique_vst_id",
    "scan_directory_for_vsts", "scan_multiple_directories",
    # Blender
    "register", "unregister",
]