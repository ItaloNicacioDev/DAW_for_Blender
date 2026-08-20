# modules/channel_rack/icons.py
"""
Ícones do Channel Rack.

Responsabilidade:
    Centralizar o mapeamento entre tipos de canal/instrumento e os ícones
    nativos do Blender usados para representá-los na UI (evita strings
    "mágicas" espalhadas pelos painéis e operadores).

Também gera, sob demanda, pequenos ícones de cor sólida a partir de
`channel.color` (via bpy.utils.previews) -- a API nativa do Blender não
permite pintar o fundo de uma linha de layout com uma cor arbitrária,
mas um ícone gerado em runtime pode ter qualquer cor, e um `label(icon_value=...)`
grande o suficiente funciona visualmente como um "chip" de cor sólida
ao lado do nome do track -- o mais próximo que dá pra chegar do
bloco colorido cheio da imagem de referência sem sair dos widgets
nativos do Blender.
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


# ═══════════════════════════════════════════════════════════════
#  CHIPS DE COR DINÂMICOS  (bpy.utils.previews)
# ═══════════════════════════════════════════════════════════════
_preview_collection = None
_color_icon_cache: dict[tuple, int] = {}

_CHIP_SIZE = 16  # pixels -- pequeno o bastante pra não pesar gerar em runtime


def _get_preview_collection():
    global _preview_collection
    if _preview_collection is None:
        import bpy.utils.previews
        _preview_collection = bpy.utils.previews.new()
    return _preview_collection


def get_color_icon_value(color) -> int:
    """
    Devolve o `icon_value` (int) de um ícone sólido gerado na cor
    `color` (tupla RGB 0.0-1.0, mesma que `channel.color`), cacheado por
    cor arredondada -- evita gerar um ícone novo a cada redraw do
    painel (o Blender redesenha os painéis com bastante frequência).

    Uso: `layout.label(text="", icon_value=get_color_icon_value(ch.color))`
    """
    key = (round(color[0], 2), round(color[1], 2), round(color[2], 2))
    cached = _color_icon_cache.get(key)
    if cached is not None:
        return cached

    pcoll = _get_preview_collection()
    name = f"daw_chip_{key[0]}_{key[1]}_{key[2]}"

    r, g, b = (max(0.0, min(1.0, c)) for c in color)
    pixel = (r, g, b, 1.0)
    pixels = [c for _ in range(_CHIP_SIZE * _CHIP_SIZE) for c in pixel]

    try:
        img = pcoll.new(name)
        img.image_size = (_CHIP_SIZE, _CHIP_SIZE)
        img.image_pixels_float = pixels
        icon_value = img.icon_id
    except Exception:
        # Se algo der errado gerando o ícone (raro, mas não deve
        # quebrar o painel inteiro por causa disso), cai pro ícone de
        # cor genérico do Blender em vez de propagar a exceção.
        return 0

    _color_icon_cache[key] = icon_value
    return icon_value


def clear_color_icon_cache() -> None:
    """Libera os ícones gerados -- chamado no unregister() do módulo."""
    global _preview_collection
    _color_icon_cache.clear()
    if _preview_collection is not None:
        import bpy.utils.previews
        try:
            bpy.utils.previews.remove(_preview_collection)
        except Exception:
            pass
        _preview_collection = None