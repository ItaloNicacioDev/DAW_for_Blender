# modules/patterns/__init__.py
"""
Módulo Patterns da DAW para Blender.

Arquitetura
-----------
O módulo é dividido em duas camadas:

1. Modelo puro (sem bpy):
   patterns.py  → Pattern, PatternNote
   clips.py     → PatternClip
   groups.py    → PatternGroup
   colors.py    → paleta de cores

2. Integração Blender (bpy):
   properties.py  → PropertyGroups RNA
   operators.py   → Operators
   ui.py          → Painéis, listas e menus
   utils.py       → Utilitários
   register.py    → Registro/desregistro

Uso típico (fora do Blender):
    from daw.modules.patterns import Pattern, PatternNote
    p = Pattern(name="Kick", length_steps=16)
    p.add_note(pitch=36, start_step=0)

Uso típico (dentro do Blender):
    patterns_props = context.scene.daw_patterns
    patterns_props.patterns.add()
"""
from __future__ import annotations

# ------------------------------------------------------------------ #
# Modelo puro
# ------------------------------------------------------------------ #
from .patterns import Pattern, PatternNote, DEFAULT_PATTERN_LENGTH
from .clips import PatternClip
from .groups import PatternGroup
from .colors import get_color_by_index, DEFAULT_PALETTE

# ------------------------------------------------------------------ #
# Integração Blender
# ------------------------------------------------------------------ #
from .register import register, unregister

# ------------------------------------------------------------------ #
# Utilitários
# ------------------------------------------------------------------ #
from .utils import (
    clamp,
    clamp_index,
    unique_pattern_name,
    unique_group_name,
    beat_to_step,
    step_to_beat,
    midi_note_name,
)

__all__ = [
    # Modelo puro
    "Pattern",
    "PatternNote",
    "PatternClip",
    "PatternGroup",
    "DEFAULT_PATTERN_LENGTH",
    "get_color_by_index",
    "DEFAULT_PALETTE",
    # Registro Blender
    "register",
    "unregister",
    # Utilitários
    "clamp",
    "clamp_index",
    "unique_pattern_name",
    "unique_group_name",
    "beat_to_step",
    "step_to_beat",
    "midi_note_name",
]