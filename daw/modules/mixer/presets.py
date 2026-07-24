# modules/mixer/presets.py
"""
Gerenciamento de presets do Mixer.

Responsabilidade:
    Duas categorias de preset, ambas salvas como JSON em disco e usadas
    pelos operadores (operators.py) e pela UI (ui.py):

    1. Presets de INSERT — parâmetros de um único efeito (ver effects.py
       para o catálogo de tipos e parâmetros padrão).
    2. Presets de CHANNEL STRIP — o estado inteiro de uma faixa do mixer
       (volume, pan, saída, cadeia de inserts e sends), para reaproveitar
       uma configuração de canal entre projetos/faixas.

Presets do usuário são salvos em:
    <diretório de scripts do usuário>/presets/daw_mixer/inserts/<TIPO>.json
    <diretório de scripts do usuário>/presets/daw_mixer/channel_strips.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import bpy

from .effects import EFFECT_TYPES, default_params_for

DEFAULT_INSERT_PRESET_NAME = "Padrão"


# ------------------------------------------------------------------ #
# Diretórios / arquivos
# ------------------------------------------------------------------ #
def _presets_root() -> Path:
    return Path(bpy.utils.user_resource('SCRIPTS', path="presets/daw_mixer", create=True))


def _insert_presets_dir() -> Path:
    path = _presets_root() / "inserts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _insert_presets_file(effect_type: str) -> Path:
    return _insert_presets_dir() / f"{effect_type}.json"


def _strip_presets_file() -> Path:
    return _presets_root() / "channel_strips.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: Dict[str, Any]) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


# ------------------------------------------------------------------ #
# Presets de INSERT (parâmetros de um único efeito)
# ------------------------------------------------------------------ #
def builtin_insert_presets(effect_type: str) -> Dict[str, Dict[str, float]]:
    """Presets embutidos de um tipo de efeito (por ora, só os valores padrão)."""
    return {DEFAULT_INSERT_PRESET_NAME: default_params_for(effect_type)}


def load_user_insert_presets(effect_type: str) -> Dict[str, Dict[str, float]]:
    return _read_json(_insert_presets_file(effect_type))


def save_user_insert_preset(effect_type: str, name: str, params: Dict[str, float]) -> bool:
    if effect_type not in EFFECT_TYPES or not name.strip():
        return False
    presets = load_user_insert_presets(effect_type)
    presets[name] = dict(params)
    return _write_json(_insert_presets_file(effect_type), presets)


def delete_user_insert_preset(effect_type: str, name: str) -> bool:
    presets = load_user_insert_presets(effect_type)
    if name not in presets:
        return False
    del presets[name]
    return _write_json(_insert_presets_file(effect_type), presets)


def list_insert_preset_names(effect_type: str) -> List[str]:
    """Presets embutidos seguidos dos presets do usuário (sem duplicar nomes)."""
    builtin = list(builtin_insert_presets(effect_type).keys())
    user = list(load_user_insert_presets(effect_type).keys())
    return builtin + [n for n in user if n not in builtin]


def get_insert_preset_params(effect_type: str, name: str) -> Optional[Dict[str, float]]:
    builtin = builtin_insert_presets(effect_type)
    if name in builtin:
        return dict(builtin[name])
    user = load_user_insert_presets(effect_type)
    if name in user:
        return dict(user[name])
    return None


def resolve_insert_params(effect_type: str, name: Optional[str]) -> Dict[str, float]:
    """Parâmetros de `name`, ou os padrão do tipo de efeito se `name` for inválido."""
    if name:
        params = get_insert_preset_params(effect_type, name)
        if params is not None:
            return params
    return default_params_for(effect_type)


def apply_params_to_insert_slot(slot, params: Dict[str, float]) -> None:
    """Substitui os parâmetros de um MixerInsertSlotProperties pelos de `params`."""
    slot.params.clear()
    for key, value in params.items():
        p = slot.params.add()
        p.name = key
        p.value = float(value)


def insert_slot_params_to_dict(slot) -> Dict[str, float]:
    return {p.name: p.value for p in slot.params}


# ------------------------------------------------------------------ #
# Presets de CHANNEL STRIP (faixa inteira do mixer)
# ------------------------------------------------------------------ #
def load_strip_presets() -> Dict[str, Dict[str, Any]]:
    return _read_json(_strip_presets_file())


def list_strip_preset_names() -> List[str]:
    return list(load_strip_presets().keys())


def get_strip_preset(name: str) -> Optional[Dict[str, Any]]:
    return load_strip_presets().get(name)


def track_to_strip_dict(track) -> Dict[str, Any]:
    """Serializa uma MixerTrackProperties para um dict simples (JSON-safe)."""
    return {
        "volume": track.volume,
        "pan": track.pan,
        "output_bus": track.output_bus,
        "inserts": [
            {
                "effect_type": slot.effect_type,
                "enabled": slot.enabled,
                "bypass": slot.bypass,
                "params": insert_slot_params_to_dict(slot),
            }
            for slot in track.inserts
        ],
        "sends": [
            {
                "bus_name": send.bus_name,
                "level": send.level,
                "pre_fader": send.pre_fader,
                "enabled": send.enabled,
            }
            for send in track.sends
        ],
    }


def apply_strip_dict_to_track(track, data: Dict[str, Any]) -> None:
    """Aplica um dict salvo por `track_to_strip_dict` de volta a uma faixa RNA."""
    track.volume = float(data.get("volume", track.volume))
    track.pan = float(data.get("pan", track.pan))
    track.output_bus = data.get("output_bus", track.output_bus)

    track.inserts.clear()
    for insert_data in data.get("inserts", []):
        slot = track.inserts.add()
        slot.effect_type = insert_data.get("effect_type", "EQ")
        slot.enabled = bool(insert_data.get("enabled", True))
        slot.bypass = bool(insert_data.get("bypass", False))
        apply_params_to_insert_slot(slot, insert_data.get("params", {}))

    track.sends.clear()
    for send_data in data.get("sends", []):
        send = track.sends.add()
        send.bus_name = send_data.get("bus_name", "")
        send.level = float(send_data.get("level", 0.0))
        send.pre_fader = bool(send_data.get("pre_fader", False))
        send.enabled = bool(send_data.get("enabled", True))


def save_strip_preset(name: str, track) -> bool:
    """Salva o estado atual de `track` (MixerTrackProperties) como preset."""
    if not name.strip():
        return False
    presets = load_strip_presets()
    presets[name] = track_to_strip_dict(track)
    return _write_json(_strip_presets_file(), presets)


def delete_strip_preset(name: str) -> bool:
    presets = load_strip_presets()
    if name not in presets:
        return False
    del presets[name]
    return _write_json(_strip_presets_file(), presets)


def apply_strip_preset(name: str, track) -> bool:
    """Carrega o preset `name` e aplica em `track`. Retorna False se não existir."""
    data = get_strip_preset(name)
    if data is None:
        return False
    apply_strip_dict_to_track(track, data)
    return True