# modules/automation/store.py
"""
Armazenamento dos clips de automação de uma cena.

Antes, os clips viviam só num dicionário em memória: sumiam ao fechar o
Blender, e ainda vazavam entre arquivos (a chave era `scene.name`, então abrir
outro .blend com uma cena chamada "Scene" herdava os clips do arquivo
anterior). Agora:

  * a fonte de verdade é a lista de `AutomationClip` em memória (cache);
  * ela é espelhada como JSON numa propriedade customizada da cena
    (`scene["daw_automation_json"]`), que o Blender salva junto com o .blend;
  * `clear_cache()` é chamado no load_post, e o cache é recarregado da
    propriedade da cena sob demanda.

Sem dependência de bpy: `scene` só precisa de `.name`, `.get(key)` e
`__setitem__` (um `bpy.types.Scene` e um dict simples servem).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .clips import AutomationClip

PROP_KEY = "daw_automation_json"
FORMAT_VERSION = 1

_cache: Dict[str, List[AutomationClip]] = {}


def clips_to_data(clips: List[AutomationClip]) -> Dict[str, Any]:
    return {"version": FORMAT_VERSION, "clips": [c.to_dict() for c in clips]}


def clips_from_data(data: Any) -> List[AutomationClip]:
    """Reconstrói clips a partir de dados serializados (tolera dados inválidos)."""
    if not isinstance(data, dict):
        return []
    clips: List[AutomationClip] = []
    for item in data.get("clips", []):
        try:
            clips.append(AutomationClip.from_dict(item))
        except Exception as exc:  # um clip corrompido não pode derrubar os outros
            print(f"[DAW][automation] Clip ignorado (dados inválidos): {exc}")
    return clips


def _load_from_scene(scene) -> List[AutomationClip]:
    raw = None
    try:
        raw = scene.get(PROP_KEY)
    except Exception:
        return []
    if not raw:
        return []
    try:
        return clips_from_data(json.loads(raw))
    except (TypeError, ValueError) as exc:
        print(f"[DAW][automation] JSON de automação inválido na cena '{scene.name}': {exc}")
        return []


def get_clips(scene) -> List[AutomationClip]:
    """Lista (mutável) de clips da cena. Carrega da cena na primeira chamada."""
    key = scene.name
    if key not in _cache:
        _cache[key] = _load_from_scene(scene)
    return _cache[key]


def save_clips(scene) -> None:
    """Grava os clips atuais na propriedade da cena (vai junto com o .blend)."""
    clips = get_clips(scene)
    try:
        scene[PROP_KEY] = json.dumps(clips_to_data(clips), ensure_ascii=False)
    except Exception as exc:
        print(f"[DAW][automation] Não foi possível salvar a automação na cena: {exc}")


def replace_clips(scene, clips: List[AutomationClip]) -> None:
    """Troca todos os clips da cena (usado ao carregar um projeto .json)."""
    _cache[scene.name] = list(clips)
    save_clips(scene)


def clear_cache() -> None:
    _cache.clear()