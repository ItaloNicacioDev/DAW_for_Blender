# modules/piano_roll/__init__.py
"""
Módulo Piano Roll da DAW para Blender.

Arquitetura
-----------
1. Modelo puro (sem bpy):
   notes.py        → PianoRollNote
   scales.py       → escalas musicais
   chords.py       → acordes
   quantize.py     → quantização de timing
   snap.py         → snap a grid
   humanize.py     → variação aleatória natural
   arpeggiator.py  → geração de arpejos
   ghost_notes.py  → notas fantasma de referência
   selection.py    → gerenciamento de seleção
   utils.py        → utilitários

2. Integração Blender (bpy):
   properties.py   → PropertyGroups RNA
   operators.py    → Operators
   ui.py           → Painéis, listas e menus
   register.py     → Registro/desregistro

Uso típico (fora do Blender):
    from daw.modules.piano_roll import PianoRollNote
    note = PianoRollNote(pitch=60, start_beat=0.0, duration_beats=0.5)

Uso típico (dentro do Blender):
    pr = context.scene.daw_piano_roll
    pr.notes.add()
"""
from __future__ import annotations

# ------------------------------------------------------------------ #
# Modelo puro
# ------------------------------------------------------------------ #
from .notes import PianoRollNote
from .scales import (
    SCALE_ITEMS, SCALE_INTERVALS, get_scale_notes,
    is_note_in_scale, snap_pitch_to_scale, scale_name_for_display, get_note_name,
)
from .chords import CHORD_ITEMS, CHORD_INTERVALS, get_chord_notes, chord_name_for_display, generate_chord_notes
from .quantize import quantize_beat, quantize_notes
from .snap import SNAP_ITEMS, SNAP_DIVISIONS, snap_value, get_division_value
from .humanize import humanize_timing, humanize_velocity, humanize_duration, humanize
from .arpeggiator import ARPEGGIO_ITEMS, ARPEGGIO_PATTERNS, generate_arpeggio
from .ghost_notes import GhostNote, create_ghost_notes_from_pattern, filter_ghost_notes_in_range
from .selection import (
    select_all, deselect_all, invert_selection, select_in_range,
    get_selected_notes, delete_selected, duplicate_selected,
    move_selected, transpose_selected, set_velocity_selected,
)
from .utils import (
    clamp, clamp_index, pitch_to_y, y_to_pitch, beat_to_x, x_to_beat,
    is_black_key, get_key_color, format_beat,
)

# ------------------------------------------------------------------ #
# Integração Blender
# ------------------------------------------------------------------ #
from .register import register, unregister

__all__ = [
    # Modelo puro
    "PianoRollNote",
    "SCALE_ITEMS", "SCALE_INTERVALS", "get_scale_notes",
    "is_note_in_scale", "snap_pitch_to_scale", "scale_name_for_display", "get_note_name",
    "CHORD_ITEMS", "CHORD_INTERVALS", "get_chord_notes", "chord_name_for_display", "generate_chord_notes",
    "quantize_beat", "quantize_notes",
    "SNAP_ITEMS", "SNAP_DIVISIONS", "snap_value", "get_division_value",
    "humanize_timing", "humanize_velocity", "humanize_duration", "humanize",
    "ARPEGGIO_ITEMS", "ARPEGGIO_PATTERNS", "generate_arpeggio",
    "GhostNote", "create_ghost_notes_from_pattern", "filter_ghost_notes_in_range",
    "select_all", "deselect_all", "invert_selection", "select_in_range",
    "get_selected_notes", "delete_selected", "duplicate_selected",
    "move_selected", "transpose_selected", "set_velocity_selected",
    "clamp", "clamp_index", "pitch_to_y", "y_to_pitch", "beat_to_x", "x_to_beat",
    "is_black_key", "get_key_color", "format_beat",
    # Registro Blender
    "register", "unregister",
]