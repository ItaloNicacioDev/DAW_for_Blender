# modules/mixer/effects.py
"""
Catálogo de tipos de efeito disponíveis para os inserts do Mixer — sem bpy.

Responsabilidade:
    Centralizar a lista de efeitos que podem ser adicionados a um insert
    (ver inserts.py) junto com seus parâmetros padrão e rótulos/ícones de
    UI, evitando strings "mágicas" espalhadas por operators.py e ui.py.

    Os parâmetros aqui definidos são apenas os valores iniciais de um
    InsertSlot.params; o processamento de áudio real de cada efeito é
    responsabilidade do módulo daw.modules.effects (ou do motor C++), este
    arquivo só descreve o que existe e como inicializar/desenhar cada um.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# Tipos de efeito suportados como insert de faixa do mixer.
EFFECT_TYPES: Tuple[str, ...] = (
    "EQ",
    "COMPRESSOR",
    "LIMITER",
    "REVERB",
    "DELAY",
    "CHORUS",
    "FLANGER",
    "PHASER",
    "DISTORTION",
)

# (identificador, rótulo legível, descrição, ícone nativo do Blender)
EFFECT_TYPE_ITEMS: Tuple[Tuple[str, str, str], ...] = (
    ("EQ", "Equalizador", "Equalizador paramétrico multibanda"),
    ("COMPRESSOR", "Compressor", "Compressor de dinâmica"),
    ("LIMITER", "Limiter", "Limitador de picos (protege de clipping)"),
    ("REVERB", "Reverb", "Reverberação / ambiência"),
    ("DELAY", "Delay", "Eco / atraso repetido do sinal"),
    ("CHORUS", "Chorus", "Duplicação modulada do sinal"),
    ("FLANGER", "Flanger", "Modulação de pente com feedback"),
    ("PHASER", "Phaser", "Filtro all-pass modulado em cascata"),
    ("DISTORTION", "Distorção", "Saturação / overdrive"),
)

EFFECT_TYPE_ICONS: Dict[str, str] = {
    "EQ": "SEQ_HISTOGRAM",
    "COMPRESSOR": "MOD_DYNAMICPAINT",
    "LIMITER": "SNAP_VOLUME",
    "REVERB": "SPEAKER",
    "DELAY": "TIME",
    "CHORUS": "MOD_WAVE",
    "FLANGER": "MOD_WAVE",
    "PHASER": "MOD_WAVE",
    "DISTORTION": "MOD_NOISE",
}

# Parâmetros padrão de cada tipo de efeito ao ser adicionado a um insert.
DEFAULT_PARAMS: Dict[str, Dict[str, float]] = {
    "EQ": {"low_gain": 0.0, "mid_gain": 0.0, "high_gain": 0.0, "mid_freq": 1000.0},
    "COMPRESSOR": {"threshold": -18.0, "ratio": 4.0, "attack": 0.01, "release": 0.15, "makeup": 0.0},
    "LIMITER": {"ceiling": -0.3, "release": 0.05},
    "REVERB": {"mix": 0.25, "size": 0.5, "damping": 0.5},
    "DELAY": {"time": 0.25, "feedback": 0.35, "mix": 0.25},
    "CHORUS": {"rate": 0.8, "depth": 0.3, "mix": 0.5},
    "FLANGER": {"rate": 0.25, "depth": 0.5, "feedback": 0.3, "mix": 0.5},
    "PHASER": {"rate": 0.3, "depth": 0.6, "stages": 4, "mix": 0.5},
    "DISTORTION": {"drive": 0.3, "tone": 0.5, "mix": 1.0},
}


def default_params_for(effect_type: str) -> Dict[str, float]:
    """Retorna uma cópia dos parâmetros padrão para o tipo de efeito informado."""
    return dict(DEFAULT_PARAMS.get(effect_type, {}))


def label_for(effect_type: str) -> str:
    for identifier, label, _desc in EFFECT_TYPE_ITEMS:
        if identifier == effect_type:
            return label
    return effect_type.title()


def icon_for(effect_type: str) -> str:
    return EFFECT_TYPE_ICONS.get(effect_type, "SHADERFX")


def is_valid_effect_type(effect_type: str) -> bool:
    return effect_type in EFFECT_TYPES


def enum_items() -> List[Tuple[str, str, str]]:
    """Formato pronto para uso em um bpy.props.EnumProperty(items=...)."""
    return list(EFFECT_TYPE_ITEMS)
