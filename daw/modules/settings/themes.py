# modules/settings/themes.py
"""
Definição de temas (paletas de cores) para a UI do DAW.

Suporta temas escuro, claro e Blender padrão. Cada tema define cores
para diferentes elementos (background, text, accent, etc).
"""
from __future__ import annotations

from typing import NamedTuple


class ColorScheme(NamedTuple):
    """Paleta de cores com campos padrão."""
    # Backgrounds
    bg_primary: tuple[float, float, float, float]      # Fundo principal (RGBA)
    bg_secondary: tuple[float, float, float, float]    # Fundo secundário
    bg_hover: tuple[float, float, float, float]        # Fundo em hover
    bg_active: tuple[float, float, float, float]       # Fundo ativo/selected
    
    # Texts
    text_primary: tuple[float, float, float, float]    # Texto principal
    text_secondary: tuple[float, float, float, float]  # Texto secundário
    text_disabled: tuple[float, float, float, float]   # Texto desativado
    
    # Accents
    accent_primary: tuple[float, float, float, float]  # Cor de destaque principal (ex: play button)
    accent_secondary: tuple[float, float, float, float] # Cor secundária (ex: record)
    accent_warning: tuple[float, float, float, float]  # Aviso (ex: clipping)
    accent_error: tuple[float, float, float, float]    # Erro
    
    # Special
    waveform_positive: tuple[float, float, float, float]  # Cor de onda (positiva)
    waveform_negative: tuple[float, float, float, float]  # Cor de onda (negativa)
    playhead: tuple[float, float, float, float]        # Linha de playhead
    border: tuple[float, float, float, float]          # Bordas


# ============================================================================
# TEMA ESCURO (Dark Neon)
# ============================================================================
THEME_DARK = ColorScheme(
    # Backgrounds
    bg_primary=(0.12, 0.12, 0.15, 1.0),        # Quase preto com toque azul
    bg_secondary=(0.18, 0.18, 0.22, 1.0),      # Cinza escuro
    bg_hover=(0.22, 0.22, 0.28, 1.0),          # Cinza mais claro
    bg_active=(0.25, 0.25, 0.35, 1.0),         # Com toque de azul
    
    # Texts
    text_primary=(0.95, 0.95, 0.98, 1.0),      # Branco quase puro
    text_secondary=(0.75, 0.75, 0.80, 1.0),    # Cinza claro
    text_disabled=(0.45, 0.45, 0.50, 1.0),     # Cinza desativado
    
    # Accents (Neon)
    accent_primary=(0.20, 0.80, 1.0, 1.0),     # Ciano neon (play)
    accent_secondary=(1.0, 0.20, 0.60, 1.0),   # Magenta neon (record)
    accent_warning=(1.0, 0.85, 0.20, 1.0),     # Amarelo neon (aviso)
    accent_error=(1.0, 0.30, 0.30, 1.0),       # Vermelho neon (erro)
    
    # Special
    waveform_positive=(0.20, 1.0, 0.80, 1.0),  # Verde ciano (crista)
    waveform_negative=(0.20, 0.80, 1.0, 0.6),  # Ciano mais escuro (vale)
    playhead=(1.0, 0.20, 0.20, 1.0),           # Vermelho para visibilidade
    border=(0.30, 0.30, 0.40, 1.0),            # Bordas suaves
)


# ============================================================================
# TEMA CLARO (Light Minimalist)
# ============================================================================
THEME_LIGHT = ColorScheme(
    # Backgrounds
    bg_primary=(0.95, 0.95, 0.96, 1.0),        # Quase branco
    bg_secondary=(0.88, 0.88, 0.90, 1.0),      # Cinza claro
    bg_hover=(0.82, 0.82, 0.85, 1.0),          # Cinza um pouco mais escuro
    bg_active=(0.75, 0.85, 0.95, 1.0),         # Azul suave
    
    # Texts
    text_primary=(0.12, 0.12, 0.15, 1.0),      # Quase preto
    text_secondary=(0.40, 0.40, 0.45, 1.0),    # Cinza escuro
    text_disabled=(0.70, 0.70, 0.75, 1.0),     # Cinza desativado
    
    # Accents (suaves)
    accent_primary=(0.15, 0.60, 0.85, 1.0),    # Azul (play)
    accent_secondary=(0.85, 0.30, 0.50, 1.0),  # Rosa (record)
    accent_warning=(0.95, 0.70, 0.15, 1.0),    # Laranja (aviso)
    accent_error=(0.90, 0.25, 0.25, 1.0),      # Vermelho (erro)
    
    # Special
    waveform_positive=(0.25, 0.75, 0.60, 1.0), # Verde
    waveform_negative=(0.40, 0.75, 0.90, 0.7), # Azul claro
    playhead=(0.90, 0.25, 0.25, 1.0),          # Vermelho
    border=(0.80, 0.80, 0.82, 1.0),            # Bordas suaves
)


# ============================================================================
# TEMA BLENDER (Padrão)
# ============================================================================
THEME_BLENDER = ColorScheme(
    # Backgrounds (usar cores Blender padrão)
    bg_primary=(0.20, 0.20, 0.20, 1.0),
    bg_secondary=(0.25, 0.25, 0.25, 1.0),
    bg_hover=(0.30, 0.30, 0.30, 1.0),
    bg_active=(0.35, 0.35, 0.40, 1.0),
    
    # Texts
    text_primary=(0.90, 0.90, 0.90, 1.0),
    text_secondary=(0.70, 0.70, 0.70, 1.0),
    text_disabled=(0.50, 0.50, 0.50, 1.0),
    
    # Accents (Blender blue)
    accent_primary=(0.40, 0.60, 1.0, 1.0),     # Azul Blender
    accent_secondary=(1.0, 0.50, 0.50, 1.0),   # Vermelho suave
    accent_warning=(1.0, 0.70, 0.20, 1.0),     # Laranja
    accent_error=(1.0, 0.40, 0.40, 1.0),       # Vermelho
    
    # Special
    waveform_positive=(0.30, 0.70, 0.30, 1.0),
    waveform_negative=(0.40, 0.60, 0.80, 0.6),
    playhead=(1.0, 1.0, 0.40, 1.0),            # Amarelo
    border=(0.40, 0.40, 0.40, 1.0),
)


# Mapeamento de tema → ColorScheme
THEMES = {
    'DARK': THEME_DARK,
    'LIGHT': THEME_LIGHT,
    'BLENDER': THEME_BLENDER,
}


def get_current_theme(theme_name: str) -> ColorScheme:
    """Retorna a paleta de cores para um tema específico."""
    return THEMES.get(theme_name, THEME_DARK)


def get_theme_by_preferences() -> ColorScheme:
    """Retorna o tema baseado nas preferências do addon."""
    try:
        from .preferences import get_preferences
        prefs = get_preferences()
        theme_name = prefs.ui.theme
        return get_current_theme(theme_name)
    except Exception:
        return THEME_DARK  # Fallback


# Atalhos de acesso direto às cores
def get_accent_play() -> tuple[float, float, float, float]:
    """Cor do botão play."""
    theme = get_theme_by_preferences()
    return theme.accent_primary


def get_accent_record() -> tuple[float, float, float, float]:
    """Cor do botão record."""
    theme = get_theme_by_preferences()
    return theme.accent_secondary


def get_accent_warning() -> tuple[float, float, float, float]:
    """Cor de aviso (clipping, etc)."""
    theme = get_theme_by_preferences()
    return theme.accent_warning


def get_accent_error() -> tuple[float, float, float, float]:
    """Cor de erro."""
    theme = get_theme_by_preferences()
    return theme.accent_error


def get_waveform_colors() -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """Retorna (cor_positiva, cor_negativa) para ondas."""
    theme = get_theme_by_preferences()
    return theme.waveform_positive, theme.waveform_negative


classes = []


def register():
    pass


def unregister():
    pass