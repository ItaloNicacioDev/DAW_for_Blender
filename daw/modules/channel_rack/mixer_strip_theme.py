# modules/channel_rack/mixer_strip_theme.py
"""
Paleta e regras de cor das channel strips do mixer (overlay).

Arquivo isolado de propósito (só constantes + funções puras, sem bpy/gpu)
para poder ajustar a estética sem mexer no código de desenho/hit-test.

[REFINO VISUAL] Paleta revista pra dar mais profundidade (tons de
sombra/realce em vez de cores chapadas), mais contraste onde importa
(texto, estados ativos) e menos onde não importa (fundos, decoração).

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

# Medidor estilo LED segmentado (hardware de verdade) em vez de uma
# barra sólida contínua -- mais fácil de ler o nível de relance e
# visualmente mais rico.
METER_SEGMENTS = 20
METER_SEGMENT_GAP = 0.16  # fração da altura de cada segmento usada como vão

PALETTE = {
    # fundo geral do card do mixer -- ligeiramente azulado, mais escuro
    # que as strips por cima (dá profundidade/hierarquia)
    "panel_bg":        (0.055, 0.058, 0.074, 0.98),
    "panel_shadow":    (0.0, 0.0, 0.0, 0.35),
    "border":          (0.015, 0.016, 0.022, 1.0),
    "border_soft":     (0.20, 0.205, 0.24, 0.5),

    # tira de canal (strip)
    "strip_bg":        (0.122, 0.127, 0.156, 1.0),
    "strip_bg_alt":    (0.110, 0.114, 0.141, 1.0),
    "strip_bg_muted":  (0.078, 0.081, 0.098, 1.0),
    "strip_top_highlight": (1.0, 1.0, 1.0, 0.04),
    "strip_selected_glow": (0.36, 0.92, 0.42, 1.0),
    "selection_outline": (0.58, 0.66, 0.99, 0.9),

    "header_bg":       (0.158, 0.164, 0.202, 1.0),
    "header_bg_light": (0.190, 0.197, 0.240, 1.0),
    "header_txt":      (0.92, 0.925, 0.95, 1.0),
    "header_txt_dim":  (0.58, 0.585, 0.63, 1.0),
    "header_txt_soft": (0.42, 0.425, 0.47, 1.0),

    # knob (pan)
    "knob_shadow":     (0.0, 0.0, 0.0, 0.30),
    "knob_ring":       (0.26, 0.27, 0.32, 1.0),
    "knob_ring_lit":   (0.34, 0.35, 0.41, 1.0),
    "knob_fill":       (0.165, 0.172, 0.208, 1.0),
    "knob_fill_hi":    (0.205, 0.213, 0.256, 1.0),
    "knob_txt":        (0.72, 0.725, 0.77, 1.0),

    # fader
    "fader_track":     (0.038, 0.040, 0.052, 1.0),
    "fader_track_edge": (0.0, 0.0, 0.0, 0.4),
    "fader_cap":       (0.58, 0.60, 0.64, 1.0),
    "fader_cap_hi":    (0.78, 0.80, 0.83, 1.0),
    "fader_cap_lo":    (0.40, 0.42, 0.46, 1.0),
    "fader_cap_selected": (0.42, 0.88, 0.48, 1.0),
    "fader_cap_selected_hi": (0.66, 0.98, 0.70, 1.0),
    "fader_cap_selected_lo": (0.26, 0.62, 0.32, 1.0),
    "fader_fill":      (0.32, 0.34, 0.42, 0.45),

    # medidor (VU) -- LED segmentado
    "meter_bg":        (0.030, 0.032, 0.041, 1.0),
    "meter_led_off":   (1.0, 1.0, 1.0, 0.035),
    "meter_green":     (0.40, 0.85, 0.32, 1.0),
    "meter_green_dim": (0.40, 0.85, 0.32, 0.55),
    "meter_yellow":    (0.95, 0.80, 0.20, 1.0),
    "meter_yellow_dim": (0.95, 0.80, 0.20, 0.55),
    "meter_red":       (0.94, 0.26, 0.24, 1.0),
    "meter_red_dim":   (0.94, 0.26, 0.24, 0.55),
    "meter_clip":      (1.00, 0.95, 0.95, 1.0),

    # botões M/S
    "mute_on":         (0.88, 0.32, 0.32, 1.0),
    "mute_on_hi":      (0.98, 0.46, 0.44, 1.0),
    "mute_off":        (0.175, 0.18, 0.22, 1.0),
    "solo_on":         (0.95, 0.80, 0.18, 1.0),
    "solo_on_hi":      (1.0, 0.90, 0.40, 1.0),
    "solo_off":        (0.175, 0.18, 0.22, 1.0),
    "btn_txt":         (0.88, 0.88, 0.90, 1.0),
    "btn_txt_dim":     (0.50, 0.505, 0.55, 1.0),
    "btn_txt_on_dark": (0.08, 0.08, 0.08, 1.0),

    "empty_txt":       (0.46, 0.465, 0.52, 1.0),
}


def meter_color(level: float, clipping: bool = False, dim: bool = False) -> Color:
    """Devolve a cor de um segmento do medidor pra um nível 0.0-1.0.

    verde  -> level <= LEVEL_GREEN_MAX
    amarelo -> LEVEL_GREEN_MAX < level <= LEVEL_YELLOW_MAX
    vermelho -> level > LEVEL_YELLOW_MAX (ou `clipping` True)

    `dim=True` devolve a variante semi-transparente (segmento "quase
    aceso", usado como transição suave em vez de tudo-ou-nada).
    """
    suffix = "_dim" if dim else ""
    if clipping or level > LEVEL_YELLOW_MAX:
        return PALETTE[f"meter_red{suffix}"]
    if level > LEVEL_GREEN_MAX:
        return PALETTE[f"meter_yellow{suffix}"]
    return PALETTE[f"meter_green{suffix}"]


def strip_bg_for(mute: bool, alt: bool) -> Color:
    if mute:
        return PALETTE["strip_bg_muted"]
    return PALETTE["strip_bg_alt"] if alt else PALETTE["strip_bg"]