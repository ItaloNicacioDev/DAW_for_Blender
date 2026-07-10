# modules/channel_rack/icons.py
"""
Ícones do Channel Rack.

Responsabilidade:
    Centralizar o mapeamento entre tipos de canal/instrumento e os ícones
    nativos do Blender usados para representá-los na UI (evita strings
    "mágicas" espalhadas pelos painéis e operadores).
"""
from __future__ import annotations

# Ícones nativos do Blender (bpy.types.UILayout.icon) por tipo de instrumento.
# Mantém-se apenas ícones garantidos em qualquer build recente do Blender.
INSTRUMENT_TYPE_ICONS = {
    "SAMPLER": "SPEAKER",
    "SYNTH": "MOD_SIMPLEDEFORM",
    "AUDIO": "SEQ_SEQUENCER",
    "MIDI": "OUTLINER_OB_ARMATURE",
    "DRUM": "SNAP_VOLUME",
}

DEFAULT_INSTRUMENT_ICON = "SPEAKER"

# Ícones de estado usados nos botões de canal e passo do sequenciador.
ICON_MUTE_ON = "HIDE_ON"
ICON_MUTE_OFF = "HIDE_OFF"
ICON_SOLO_ON = "SOLO_ON"
ICON_SOLO_OFF = "SOLO_OFF"
ICON_STEP_ON = "RADIOBUT_ON"
ICON_STEP_OFF = "RADIOBUT_OFF"
ICON_GROUP = "GROUP"
ICON_ADD = "ADD"
ICON_REMOVE = "REMOVE"
ICON_DUPLICATE = "DUPLICATE"
ICON_COLOR = "COLOR"
ICON_LOCKED = "LOCKED"
ICON_UNLOCKED = "UNLOCKED"


def icon_for_instrument(instrument_type: str) -> str:
    """Retorna o ícone apropriado para um tipo de instrumento (fallback seguro)."""
    return INSTRUMENT_TYPE_ICONS.get(instrument_type, DEFAULT_INSTRUMENT_ICON)


def icon_for_mute(is_muted: bool) -> str:
    return ICON_MUTE_ON if is_muted else ICON_MUTE_OFF


def icon_for_solo(is_solo: bool) -> str:
    return ICON_SOLO_ON if is_solo else ICON_SOLO_OFF


def icon_for_step(is_active: bool) -> str:
    return ICON_STEP_ON if is_active else ICON_STEP_OFF