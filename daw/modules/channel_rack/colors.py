# modules/channel_rack/colors.py
"""
Paleta de cores do Channel Rack.

Responsabilidade:
    Fornecer a paleta padrão de cores usada para identificar canais
    visualmente (barra lateral colorida, ícone, steps ativos), além de
    utilitários de conversão HEX <-> RGB(A) usados pela UI e pelas
    propriedades RNA (FloatVectorProperty subtype='COLOR').
"""
from __future__ import annotations

from typing import List, Tuple

Color = Tuple[float, float, float]


# Paleta padrão (RGB 0-1), inspirada em DAWs baseadas em step sequencer.
# A ordem importa: é usada para atribuir cores automaticamente por índice.
DEFAULT_PALETTE: List[Color] = [
    (0.90, 0.30, 0.30),   # vermelho
    (0.95, 0.55, 0.20),   # laranja
    (0.95, 0.80, 0.25),   # amarelo
    (0.55, 0.85, 0.35),   # verde-limão
    (0.25, 0.75, 0.45),   # verde
    (0.25, 0.75, 0.75),   # ciano
    (0.30, 0.55, 0.95),   # azul
    (0.45, 0.35, 0.90),   # roxo-azulado
    (0.70, 0.35, 0.90),   # roxo
    (0.90, 0.35, 0.70),   # magenta
    (0.85, 0.45, 0.55),   # rosa
    (0.60, 0.60, 0.60),   # cinza neutro
]


def get_color_by_index(index: int) -> Color:
    """Retorna uma cor da paleta padrão, ciclando se o índice exceder o tamanho."""
    if not DEFAULT_PALETTE:
        return (0.5, 0.5, 0.5)
    return DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)]


def hex_to_rgb(hex_color: str) -> Color:
    """Converte '#RRGGBB' (ou 'RRGGBB') em uma tupla RGB 0-1."""
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) != 6:
        return (0.8, 0.8, 0.8)
    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        return (0.8, 0.8, 0.8)


def rgb_to_hex(color: Color) -> str:
    """Converte uma tupla RGB 0-1 em '#RRGGBB'."""
    r, g, b = (max(0, min(255, round(c * 255))) for c in color)
    return f"#{r:02X}{g:02X}{b:02X}"


def lighten(color: Color, amount: float = 0.15) -> Color:
    """Clareia uma cor RGB em `amount` (0-1), útil para estados de hover/seleção."""
    return tuple(min(1.0, c + amount) for c in color)  # type: ignore[return-value]


def darken(color: Color, amount: float = 0.15) -> Color:
    """Escurece uma cor RGB em `amount` (0-1), útil para o estado 'mutado'."""
    return tuple(max(0.0, c - amount) for c in color)  # type: ignore[return-value]