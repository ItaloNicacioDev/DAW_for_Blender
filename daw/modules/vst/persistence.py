# modules/vst/persistence.py
"""
Persistência do estado VST no projeto (.json) da DAW.

Por que este arquivo existe:
    O save/load do projeto (`modules/project/save.py` e `load.py`) não
    incluía VSTs — ao fechar e reabrir o projeto, todos os plugins eram
    esquecidos. Este módulo expõe duas funções que o project.save e
    project.load devem chamar:

        serialize_vst_state(scene)   → Dict  (inserir no JSON do projeto)
        restore_vst_state(scene, data, context)  (chamar ao carregar)

    O que é persistido:
        - Lista de cadeias de efeitos por canal: path, nome, tipo, bypass,
          parâmetros atuais e preset corrente.
        - Rack de instrumentos: mesmos campos.
        - Configurações globais (diretórios, auto-bounce, limite de display).

    O que NÃO é persistido:
        - O estado interno do plugin VST (chunk/bank do plugin — exigiria
          a API de estado nativo do VST, disponível só em hosts VST
          completos). Os parâmetros normalizados (0–1) são suficientes
          para reconstruir o som na maioria dos plugins.

Integração com project/save.py:
    No dict retornado por _serialize_scene() (ou equivalente), adicione:
        data["vst"] = persistence.serialize_vst_state(scene)

Integração com project/load.py:
    Após reconstruir os outros módulos:
        persistence.restore_vst_state(scene, data.get("vst", {}), context)
"""
from __future__ import annotations

from typing import Any, Dict, List

import bpy

from .utils import (
    get_or_create_chain,
    get_or_create_live_vst,
    sync_rna_from_pure,
)


# ═══════════════════════════════════════════════════════════════
#  SERIALIZAÇÃO (save)
# ═══════════════════════════════════════════════════════════════

def _serialize_vst_item(item) -> Dict[str, Any]:
    """Serializa um DawVstProperty para dict JSON-safe."""
    return {
        "vst_path": item.vst_path,
        "vst_name": item.vst_name,
        "vst_id": item.vst_id,
        "vst_type": item.vst_type,
        "bypass": item.bypass,
        "current_preset": item.current_preset,
        "parameters": {
            str(p.param_id): p.param_value
            for p in item.parameters
        },
    }


def serialize_vst_state(scene) -> Dict[str, Any]:
    """
    Serializa o estado completo de VST da cena.
    Retorne este dict em project/save.py dentro da chave "vst".
    """
    settings = getattr(scene, "daw_vst", None)

    # Cadeias de efeitos por canal
    chains: List[Dict[str, Any]] = []
    for chain in scene.daw_vst_chains:
        chains.append({
            "chain_id": chain.chain_id,
            "vsts": [_serialize_vst_item(item) for item in chain.vsts],
        })

    # Rack de instrumentos
    rack_items: List[Dict[str, Any]] = []
    rack = getattr(scene, "daw_vst_instruments", None)
    if rack is not None:
        for item in rack.instruments:
            rack_items.append(_serialize_vst_item(item))

    return {
        "version": 1,
        "settings": {
            "vst_directories": settings.vst_directories if settings else "",
            "auto_bounce_on_change": settings.auto_bounce_on_change if settings else False,
            "param_display_limit": settings.param_display_limit if settings else 12,
            "max_effect_slots_per_track": settings.max_effect_slots_per_track if settings else 10,
            "max_instruments": settings.max_instruments if settings else 16,
        },
        "effect_chains": chains,
        "instruments": rack_items,
    }


# ═══════════════════════════════════════════════════════════════
#  RESTAURAÇÃO (load)
# ═══════════════════════════════════════════════════════════════

def _restore_vst_item(item_rna, item_data: Dict[str, Any], context) -> bool:
    """
    Preenche um DawVstProperty a partir de dados serializados e tenta
    carregar o plugin real. Retorna True se o plugin carregou.
    """
    item_rna.vst_path = item_data.get("vst_path", "")
    item_rna.vst_name = item_data.get("vst_name", "")
    item_rna.vst_id = item_data.get("vst_id", "")
    item_rna.vst_type = item_data.get("vst_type", "EFFECT")
    item_rna.bypass = item_data.get("bypass", False)
    item_rna.current_preset = item_data.get("current_preset", "default")

    # Cria o objeto VST puro e tenta carregar
    from .vst import VSTProgramType
    from .utils import get_live_vst, register_live_vst
    from .vst import VST

    daw_props = getattr(context.scene, "daw", None)
    sample_rate = int(daw_props.sample_rate) if daw_props else 44100

    vst = get_live_vst(item_rna.vst_id)
    if vst is None:
        vst = VST(
            path=item_rna.vst_path,
            name=item_rna.vst_name,
            vst_type=VSTProgramType(item_rna.vst_type),
            vst_id=item_rna.vst_id,
            bypass=item_rna.bypass,
        )
        register_live_vst(vst)

    ok = vst.load(sample_rate=sample_rate)

    # Restaurar parâmetros salvos (mesmo que o load tenha falhado, guarda
    # os valores para quando o usuário recarregar manualmente)
    saved_params = item_data.get("parameters", {})
    for param_id_str, value in saved_params.items():
        try:
            vst.set_parameter(int(param_id_str), float(value))
        except Exception:
            pass

    # Se carregou, os parâmetros reais do plugin podem sobrescrever os
    # salvos — re-aplicamos os valores restaurados sobre os defaults:
    if ok and vst.bridge is not None:
        for param_id_str, value in saved_params.items():
            try:
                vst.bridge.set_parameter(int(param_id_str), float(value))
            except Exception:
                pass

    sync_rna_from_pure(item_rna, vst)
    return ok


def restore_vst_state(scene, data: Dict[str, Any], context) -> None:
    """
    Restaura o estado de VST a partir de dados serializados.
    Chame em project/load.py após carregar os outros módulos.

    Erros de carregamento de plugins individuais são silenciosos
    (registrados no campo error_message do item RNA) para não impedir
    o carregamento do restante do projeto.
    """
    if not data:
        return

    # Configurações globais
    settings = getattr(scene, "daw_vst", None)
    saved_settings = data.get("settings", {})
    if settings is not None:
        if "vst_directories" in saved_settings:
            settings.vst_directories = saved_settings["vst_directories"]
        if "auto_bounce_on_change" in saved_settings:
            settings.auto_bounce_on_change = saved_settings["auto_bounce_on_change"]
        if "param_display_limit" in saved_settings:
            settings.param_display_limit = saved_settings["param_display_limit"]
        if "max_effect_slots_per_track" in saved_settings:
            settings.max_effect_slots_per_track = saved_settings["max_effect_slots_per_track"]
        if "max_instruments" in saved_settings:
            settings.max_instruments = saved_settings["max_instruments"]

    # Cadeias de efeitos
    existing_ids: list = []
    for chain_data in data.get("effect_chains", []):
        chain_id = str(chain_data.get("chain_id", "0"))
        try:
            chain = get_or_create_chain(scene, int(chain_id))
        except (ValueError, TypeError):
            continue

        chain.vsts.clear()
        for item_data in chain_data.get("vsts", []):
            item_rna = chain.vsts.add()
            try:
                ok = _restore_vst_item(item_rna, item_data, context)
                if not ok:
                    print(
                        f"[DAW VST] Plugin '{item_data.get('vst_name')}' "
                        f"não pôde ser carregado: {item_rna.error_message}"
                    )
            except Exception as e:
                item_rna.error_message = str(e)
                print(f"[DAW VST] Erro ao restaurar plugin: {e}")

    # Rack de instrumentos
    rack = getattr(scene, "daw_vst_instruments", None)
    if rack is not None:
        rack.instruments.clear()
        for item_data in data.get("instruments", []):
            item_rna = rack.instruments.add()
            try:
                ok = _restore_vst_item(item_rna, item_data, context)
                if not ok:
                    print(
                        f"[DAW VST] Instrumento '{item_data.get('vst_name')}' "
                        f"não pôde ser carregado: {item_rna.error_message}"
                    )
            except Exception as e:
                item_rna.error_message = str(e)
                print(f"[DAW VST] Erro ao restaurar instrumento: {e}")