# modules/patterns/colors.py
"""
Paleta de cores para o módulo Patterns.

Responsabilidade:
    Fornecer cores distintas para patterns, clips e grupos,
    similar ao mixer mas com uma paleta própria opcional.
"""
from __future__ import annotations

# Paleta padrão (RGB 0-1)
DEFAULT_PALETTE = [
    (0.90, 0.25, 0.25),   # vermelho
    (0.95, 0.60, 0.15),   # laranja
    (0.90, 0.85, 0.20),   # amarelo
    (0.40, 0.85, 0.35),   # verde-limão
    (0.20, 0.75, 0.50),   # verde
    (0.20, 0.70, 0.80),   # ciano
    (0.25, 0.50, 0.95),   # azul
    (0.50, 0.30, 0.90),   # roxo-azulado
    (0.75, 0.30, 0.85),   # roxo
    (0.90, 0.30, 0.65),   # magenta
    (0.95, 0.50, 0.40),   # coral
    (0.60, 0.70, 0.30),   # oliva
]


def get_color_by_index(index: int):
    if not DEFAULT_PALETTE:
        return (0.6, 0.6, 0.6)
    return DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)]