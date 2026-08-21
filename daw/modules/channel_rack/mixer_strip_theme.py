# modules/channel_rack/mixer_strip_theme.py
"""
Paleta e regras de cor das channel strips do mixer (overlay novo).

Arquivo isolado de propósito (só constantes + funções puras, sem bpy/gpu)
para poder ajustar a estética sem mexer no código de desenho/hit-test.

Regra dos medidores (pedido explícito):
    verde   = nível baixo/normal
    amarelo = nível moderado (chegando perto do teto)
    vermelho = muito alto / estourando (clipping)
"""
from __future__ import annotations

from typing import Tuple

Color = Tuple[float, float, float, float]

# ------------------------------------------------------------------ #
# Limiares do medidor de nível (0.0-1.0, mesma escala de meter_level /
# meters.py). Abaixo de GREEN_MAX = verde; entre GREEN_MAX e YELLOW_MAX
# = amarelo; acima de YELLOW_MAX = vermelho (estourando).
# ------------------------------------------------------------------ #
LEVEL_GREEN_MAX: float = 0.62
LEVEL_YELLOW_MAX: float = 0.88

PALETTE = {
    # fundo geral do card do mixer
    "panel_bg":        (0.071, 0.075, 0.094, 0.97),
    "border":          (0.020, 0.021, 0.028, 1.0),

    # tira de canal (strip)
    "strip_bg":        (0.114, 0.118, 0.145, 1.0),
    "strip_bg_alt":    (0.102, 0.106, 0.131, 1.0),
    "strip_bg_muted":  (0.075, 0.078, 0.096, 1.0),
    "strip_selected_glow": (0.35, 0.95, 0.40, 0.9),

    "header_bg":       (0.145, 0.150, 0.184, 1.0),
    "header_txt":      (0.88, 0.885, 0.92, 1.0),
    "header_txt_dim":  (0.55, 0.555, 0.60, 1.0),

    # knob (pan)
    "knob_ring":       (0.30, 0.31, 0.36, 1.0),
    "knob_fill":       (0.19, 0.20, 0.24, 1.0),
    "knob_indicator":  (0.95, 0.60, 0.20, 1.0),
    "knob_txt":        (0.75, 0.755, 0.80, 1.0),

    # fader
    "fader_track":     (0.045, 0.047, 0.060, 1.0),
    "fader_cap":       (0.62, 0.64, 0.68, 1.0),
    "fader_cap_selected": (0.45, 0.92, 0.50, 1.0),
    "fader_fill":      (0.30, 0.32, 0.38, 0.55),

    # medidor (VU)
    "meter_bg":        (0.035, 0.037, 0.047, 1.0),
    "meter_green":     (0.38, 0.82, 0.30, 1.0),
    "meter_yellow":    (0.92, 0.78, 0.18, 1.0),
    "meter_red":       (0.90, 0.24, 0.22, 1.0),
    "meter_clip":      (1.00, 0.15, 0.15, 1.0),

    # botões M/S
    "mute_on":         (0.86, 0.30, 0.30, 1.0),
    "mute_off":        (0.16, 0.165, 0.21, 1.0),
    "solo_on":         (0.92, 0.78, 0.15, 1.0),
    "solo_off":        (0.16, 0.165, 0.21, 1.0),
    "btn_txt":         (0.90, 0.90, 0.92, 1.0),
    "btn_txt_on_dark":(0.10, 0.10, 0.10, 1.0),

    "empty_txt":       (0.48, 0.485, 0.54, 1.0),
}


def meter_color(level: float, clipping: bool = False) -> Color:
    """Devolve a cor do segmento do medidor para um nível 0.0-1.0.

    verde  -> level <= LEVEL_GREEN_MAX
    amarelo -> LEVEL_GREEN_MAX < level <= LEVEL_YELLOW_MAX
    vermelho -> level > LEVEL_YELLOW_MAX (ou `clipping` True)
    """
    if clipping or level > LEVEL_YELLOW_MAX:
        return PALETTE["meter_red"]
    if level > LEVEL_GREEN_MAX:
        return PALETTE["meter_yellow"]
    return PALETTE["meter_green"]


def strip_bg_for(mute: bool, alt: bool) -> Color:
    if mute:
        return PALETTE["strip_bg_muted"]
    return PALETTE["strip_bg_alt"] if alt else PALETTE["strip_bg"]