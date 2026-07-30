# modules/vst/__init__.py
"""
Módulo VST da DAW.

Responsabilidade:
    Suporte a plugins VST2 e VST3 — tanto efeitos (inseridos na cadeia de
    um canal) quanto instrumentos (síntese via MIDI), processados de
    verdade através de `dawdreamer`.

Arquitetura:
    vst.py         — modelo puro de um plugin VST (sem bpy): parâmetros,
                      programas/presets em memória, delega processamento
                      real ao bridge.
    engine.py      — ponte real de processamento (DawdreamerBridge):
                      detecção de formato VST2/VST3, checagem de
                      disponibilidade da lib, processamento de efeito
                      (bloco a bloco) e render de instrumento (MIDI -> áudio).
    pressets.py    — presets embutidos + presets do usuário (JSON em disco).
    utils.py       — registro global vst_id -> VST puro, ponte RNA <-> puro,
                      varredura de diretórios por plugins.
    properties.py  — PropertyGroups do Blender (estado real da UI).
    operators.py   — Operators do Blender (escanear, adicionar/remover,
                      bypass, reload, parâmetros, presets, instalar dawdreamer).
    ui.py          — Painéis do Blender (Browser, Efeitos, Instrumentos).
    register.py    — register() / unregister().

Uso fora do Blender, a partir do modelo puro:
    from daw.modules.vst import VST, VSTProgramType

    fx = VST(path="/plugins/MyComp.vst3", name="MyComp", vst_type=VSTProgramType.EFFECT)
    if fx.load():
        processed = fx.process_effect(audio_buffer)

    synth = VST(path="/plugins/MySynth.vst3", name="MySynth", vst_type=VSTProgramType.INSTRUMENT)
    if synth.load():
        audio = synth.render_instrument(midi_notes, duration=4.0)

Uso a partir da cena do Blender (RNA), dentro de um Operator/Panel:
    chain = get_or_create_chain(context.scene, channel_index=0)
    for item in chain.vsts:
        live = get_live_vst(item.vst_id)
        ...
"""
from __future__ import annotations

from .vst import VST, VSTProgramType, VSTProgramParameter, VSTProgramState
from . import engine
from . import timeline_bridge
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

__all__ = [
    # Modelo puro
    "VST", "VSTProgramType", "VSTProgramParameter", "VSTProgramState",
    # Motor (dawdreamer)
    "engine",
    # Ponte com a timeline nativa do Blender (bounce -> sound strips)
    "timeline_bridge",
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