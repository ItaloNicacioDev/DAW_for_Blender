# modules/effects/presets.py
"""
Gerenciamento de presets dos efeitos.

Responsabilidade:
    Combinar os presets embutidos (definidos em cada módulo de efeito,
    ex: chorus.PRESETS) com presets salvos pelo usuário em disco, e
    fornecer funções de aplicar/salvar/remover presets usadas pelos
    operadores (operators.py).

Presets do usuário são salvos como JSON em:
    <diretório de scripts do usuário>/presets/daw_effects/<TIPO>.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import bpy

from .rack import default_params_for, presets_for, EFFECT_TYPES


def _user_presets_dir() -> Path:
    base = Path(bpy.utils.user_resource('SCRIPTS', path="presets/daw_effects", create=True))
    return base


def _user_presets_file(effect_type: str) -> Path:
    return _user_presets_dir() / f"{effect_type}.json"


def load_user_presets(effect_type: str) -> Dict[str, Dict[str, Any]]:
    """Carrega os presets salvos pelo usuário para um tipo de efeito (dict cru, não objetos)."""
    path = _user_presets_file(effect_type)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_user_preset(effect_type: str, name: str, params_dict: Dict[str, Any]) -> bool:
    """Salva/atualiza um preset do usuário em disco. Retorna True em sucesso."""
    if effect_type not in EFFECT_TYPES or not name.strip():
        return False

    presets = load_user_presets(effect_type)
    presets[name] = params_dict

    try:
        path = _user_presets_file(effect_type)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def delete_user_preset(effect_type: str, name: str) -> bool:
    """Remove um preset do usuário salvo em disco."""
    presets = load_user_presets(effect_type)
    if name not in presets:
        return False
    del presets[name]
    try:
        path = _user_presets_file(effect_type)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def list_all_preset_names(effect_type: str) -> list[str]:
    """
    Lista todos os presets disponíveis para um tipo de efeito: embutidos
    (definidos no módulo do efeito) seguidos dos presets do usuário.
    """
    builtin = list(presets_for(effect_type).keys())
    user = list(load_user_presets(effect_type).keys())
    # Evita duplicar nomes caso o usuário sobrescreva um preset embutido
    combined = builtin + [n for n in user if n not in builtin]
    return combined


def get_preset_params(effect_type: str, name: str) -> Optional[Dict[str, Any]]:
    """Retorna o dict de parâmetros de um preset (embutido ou do usuário), ou None."""
    builtin = presets_for(effect_type)
    if name in builtin:
        return builtin[name].to_dict()

    user = load_user_presets(effect_type)
    if name in user:
        return user[name]

    return None


def resolve_params(effect_type: str, name: Optional[str]) -> Dict[str, Any]:
    """Retorna os parâmetros de `name`, ou os parâmetros padrão se `name` for None/inválido."""
    if name:
        params = get_preset_params(effect_type, name)
        if params is not None:
            return params
    return default_params_for(effect_type)