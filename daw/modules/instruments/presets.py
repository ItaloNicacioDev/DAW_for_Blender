# modules/instruments/presets.py
"""
Presets de Instrumentos.

Responsabilidade:
    Combinar presets embutidos (combinações prontas de timbre GM + volume/
    pan/oitava) com presets salvos pelo usuário em disco, usados pelos
    operadores (operators.py) para configurar rapidamente um instrumento.

Presets do usuário são salvos como JSON em:
    <diretório de scripts do usuário>/presets/daw_instruments/instruments.json
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

import bpy

from .instruments import Instrument

BUILTIN_PRESETS: Dict[str, Instrument] = {
    "Piano Padrão":     Instrument(name="Piano Padrão", instrument_id=0, volume=0.85),
    "Rhodes Suave":     Instrument(name="Rhodes Suave", instrument_id=1, volume=0.7, pan=-0.1),
    "Pad de Cordas":    Instrument(name="Pad de Cordas", instrument_id=2, volume=0.6, octave_shift=0, mono=False),
    "Órgão Hammond":    Instrument(name="Órgão Hammond", instrument_id=3, volume=0.75),
    "Baixo Grave":      Instrument(name="Baixo Grave", instrument_id=4, volume=0.9, octave_shift=-1, mono=True, polyphony=1),
    "Lead Supersaw":    Instrument(name="Lead Supersaw", instrument_id=5, volume=0.8, mono=True, polyphony=1),
    "Vibrafone":        Instrument(name="Vibrafone", instrument_id=6, volume=0.7),
    "Coral Etéreo":     Instrument(name="Coral Etéreo", instrument_id=7, volume=0.55, octave_shift=1),
}


def _user_presets_file() -> Path:
    base = Path(bpy.utils.user_resource('SCRIPTS', path="presets/daw_instruments", create=True))
    return base / "instruments.json"


def load_user_presets() -> Dict[str, Dict[str, Any]]:
    """Carrega os presets de instrumento salvos pelo usuário (dict cru, não objetos)."""
    path = _user_presets_file()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_user_preset(name: str, instrument: Instrument) -> bool:
    """Salva/atualiza um preset de instrumento do usuário em disco."""
    if not name.strip():
        return False

    presets = load_user_presets()
    data = asdict(instrument)
    data.pop("name", None)  # o nome do preset é a chave; não precisa duplicar dentro
    presets[name] = data

    try:
        path = _user_presets_file()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def delete_user_preset(name: str) -> bool:
    """Remove um preset de instrumento salvo pelo usuário."""
    presets = load_user_presets()
    if name not in presets:
        return False
    del presets[name]
    try:
        path = _user_presets_file()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def list_all_preset_names() -> list[str]:
    """Lista todos os presets disponíveis: embutidos seguidos dos do usuário."""
    builtin = list(BUILTIN_PRESETS.keys())
    user = list(load_user_presets().keys())
    return builtin + [n for n in user if n not in builtin]


def get_preset(name: str) -> Optional[Instrument]:
    """Retorna um Instrument configurado a partir de um preset (embutido ou do usuário)."""
    if name in BUILTIN_PRESETS:
        base = BUILTIN_PRESETS[name]
        return Instrument(**asdict(base))

    user = load_user_presets()
    if name in user:
        data = dict(user[name])
        data["name"] = name
        valid = {f: data[f] for f in Instrument.__dataclass_fields__ if f in data}
        return Instrument(**valid)

    return None