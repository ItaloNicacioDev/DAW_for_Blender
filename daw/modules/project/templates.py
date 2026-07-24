# modules/project/templates.py
"""
Templates de projeto da DAW.

Responsabilidade:
    Criar projetos pré-configurados (vazio, básico com faixas,
    template de eletrônica, etc.) e salvá-los como templates
    reutilizáveis.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List

import bpy

from .save import serialize_project, CURRENT_PROJECT_VERSION
from .load import deserialize_project
from .utils import get_templates_dir, TEMPLATE_EXTENSION


# Templates embutidos
BUILTIN_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "empty": {
        "version": CURRENT_PROJECT_VERSION,
        "project_name": "Empty Project",
        "modules": {
            "mixer": {
                "master_volume": 0.85,
                "meters_enabled": True,
                "meter_decay_speed": 8.0,
                "tracks": [],
                "buses": [
                    {"name": "Master", "volume": 0.8, "mute": False, "is_master": True}
                ],
            },
            "patterns": {"patterns": [], "clips": [], "groups": []},
            "piano_roll": {"edited_pattern_name": "", "notes": [], "settings": {}},
            "playlist": {"tracks": [], "clips": [], "markers": [], "playback": {}},
        },
    },
    "basic": {
        "version": CURRENT_PROJECT_VERSION,
        "project_name": "Basic Project",
        "modules": {
            "mixer": {
                "master_volume": 0.85,
                "meters_enabled": True,
                "meter_decay_speed": 8.0,
                "tracks": [
                    {"name": "Kick", "color": [0.9, 0.3, 0.3], "volume": 0.78, "pan": 0.0, "mute": False, "solo": False, "output_bus": "Master", "source_index": -1, "inserts": [], "sends": []},
                    {"name": "Snare", "color": [0.95, 0.55, 0.2], "volume": 0.78, "pan": 0.0, "mute": False, "solo": False, "output_bus": "Master", "source_index": -1, "inserts": [], "sends": []},
                    {"name": "Hi-Hat", "color": [0.95, 0.8, 0.25], "volume": 0.6, "pan": 0.0, "mute": False, "solo": False, "output_bus": "Master", "source_index": -1, "inserts": [], "sends": []},
                    {"name": "Bass", "color": [0.25, 0.75, 0.45], "volume": 0.78, "pan": 0.0, "mute": False, "solo": False, "output_bus": "Master", "source_index": -1, "inserts": [], "sends": []},
                    {"name": "Lead", "color": [0.3, 0.55, 0.95], "volume": 0.78, "pan": 0.0, "mute": False, "solo": False, "output_bus": "Master", "source_index": -1, "inserts": [], "sends": []},
                ],
                "buses": [
                    {"name": "Master", "volume": 0.8, "mute": False, "is_master": True}
                ],
            },
            "patterns": {"patterns": [], "clips": [], "groups": []},
            "piano_roll": {"edited_pattern_name": "", "notes": [], "settings": {}},
            "playlist": {
                "tracks": [
                    {"name": "Kick", "mixer_track_index": 0, "color": [0.9, 0.3, 0.3], "muted": False, "solo": False, "locked": False, "height": 40},
                    {"name": "Snare", "mixer_track_index": 1, "color": [0.95, 0.55, 0.2], "muted": False, "solo": False, "locked": False, "height": 40},
                    {"name": "Hi-Hat", "mixer_track_index": 2, "color": [0.95, 0.8, 0.25], "muted": False, "solo": False, "locked": False, "height": 40},
                    {"name": "Bass", "mixer_track_index": 3, "color": [0.25, 0.75, 0.45], "muted": False, "solo": False, "locked": False, "height": 40},
                    {"name": "Lead", "mixer_track_index": 4, "color": [0.3, 0.55, 0.95], "muted": False, "solo": False, "locked": False, "height": 40},
                ],
                "clips": [],
                "markers": [],
                "playback": {"current_bpm": 128.0, "time_signature_num": 4, "time_signature_den": 4, "loop_enabled": False, "loop_start_beat": 0.0, "loop_end_beat": 16.0, "metronome_enabled": False},
            },
        },
    },
}


def get_builtin_template_names() -> List[str]:
    return list(BUILTIN_TEMPLATES.keys())


def apply_template(scene, template_name: str) -> bool:
    """Aplica um template embutido a uma cena."""
    if template_name not in BUILTIN_TEMPLATES:
        return False
    from .load import deserialize_project
    deserialize_project(scene, BUILTIN_TEMPLATES[template_name])
    scene.daw_project_name = BUILTIN_TEMPLATES[template_name]["project_name"]
    return True


def save_user_template(scene, template_name: str) -> bool:
    """Salva o estado atual como um template do usuário."""
    templates_dir = get_templates_dir()
    filepath = templates_dir / f"{template_name}{TEMPLATE_EXTENSION}"
    data = serialize_project(scene)
    data["template_name"] = template_name
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def load_user_template(template_name: str) -> Optional[Dict[str, Any]]:
    """Carrega um template do usuário."""
    templates_dir = get_templates_dir()
    filepath = templates_dir / f"{template_name}{TEMPLATE_EXTENSION}"
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_user_templates() -> List[str]:
    """Lista os templates salvos pelo usuário."""
    templates_dir = get_templates_dir()
    return sorted([p.stem for p in templates_dir.glob(f"*{TEMPLATE_EXTENSION}")])


def apply_user_template(scene, template_name: str) -> bool:
    """Aplica um template do usuário a uma cena."""
    data = load_user_template(template_name)
    if data is None:
        return False
    from .load import deserialize_project
    deserialize_project(scene, data)
    scene.daw_project_name = data.get("template_name", template_name)
    return True