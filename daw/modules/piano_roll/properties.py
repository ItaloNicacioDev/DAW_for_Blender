# modules/piano_roll/properties.py
"""
Propriedades RNA do Blender para o módulo Piano Roll.

Responsabilidade:
    Espelhar em PropertyGroups o estado do editor piano roll,
    incluindo notas, configurações de snap, escala, e seleção.
    Fica em context.scene.daw_piano_roll.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .scales import SCALE_ITEMS, get_scale_notes
from .chords import CHORD_ITEMS
from .snap import SNAP_ITEMS


# ------------------------------------------------------------------ #
# Nota individual no piano roll
# ------------------------------------------------------------------ #
class PianoRollNoteProperties(PropertyGroup):
    """Uma nota no piano roll — espelho RNA de notes.PianoRollNote."""

    pitch: IntProperty(name="Nota", default=60, min=0, max=127)
    start_beat: FloatProperty(name="Início (beats)", default=0.0, min=0.0)
    duration_beats: FloatProperty(name="Duração (beats)", default=0.25, min=0.01)
    velocity: FloatProperty(name="Velocity", default=0.8, min=0.0, max=1.0, subtype='FACTOR')

    selected: BoolProperty(name="Selecionada", default=False)
    muted: BoolProperty(name="Muda", default=False)


# ------------------------------------------------------------------ #
# Configurações do editor
# ------------------------------------------------------------------ #
class PianoRollSettingsProperties(PropertyGroup):
    """Configurações do editor piano roll."""

    # --- Snap ---
    snap_enabled: BoolProperty(name="Snap", default=True)
    snap_division: EnumProperty(
        name="Divisão",
        items=SNAP_ITEMS,
        default="SIXTEENTH",
    )

    # --- Escala ---
    scale_enabled: BoolProperty(name="Snap à Escala", default=False)
    scale_root: IntProperty(name="Tônica", default=60, min=0, max=127)
    scale_name: EnumProperty(
        name="Escala",
        items=SCALE_ITEMS,
        default="MAJOR",
    )
    scale_highlight: BoolProperty(name="Destacar Notas da Escala", default=True)

    # --- Visualização ---
    zoom_x: FloatProperty(name="Zoom Horizontal", default=1.0, min=0.1, max=10.0)
    zoom_y: FloatProperty(name="Zoom Vertical", default=1.0, min=0.1, max=10.0)
    scroll_x: FloatProperty(name="Scroll X", default=0.0)
    scroll_y: FloatProperty(name="Scroll Y", default=0.0)

    # --- Playback ---
    follow_playhead: BoolProperty(name="Seguir Playhead", default=True)
    show_ghost_notes: BoolProperty(name="Ghost Notes", default=True)

    # --- Quantize / Humanize ---
    quantize_strength: FloatProperty(name="Força Quantize", default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    quantize_grid: EnumProperty(
        name="Grid Quantize",
        items=SNAP_ITEMS,
        default="SIXTEENTH",
    )
    humanize_timing: FloatProperty(name="Humanize Timing", default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    humanize_velocity: FloatProperty(name="Humanize Velocity", default=0.0, min=0.0, max=1.0, subtype='FACTOR')


# ------------------------------------------------------------------ #
# Estado global do Piano Roll
# ------------------------------------------------------------------ #
class PianoRollProperties(PropertyGroup):
    """Estado completo do editor Piano Roll para uma cena."""

    # Notas do pattern sendo editado
    notes: CollectionProperty(type=PianoRollNoteProperties)
    active_note_index: IntProperty(name="Nota Ativa", default=0, min=0)

    # Nome do pattern sendo editado
    edited_pattern_name: StringProperty(name="Pattern Editando", default="")

    # Configurações do editor
    settings: PointerProperty(type=PianoRollSettingsProperties)

    # --- Seleção ---
    selection_box_active: BoolProperty(name="Box Select Ativo", default=False)
    selection_box_x1: FloatProperty(name="Box X1", default=0.0)
    selection_box_y1: FloatProperty(name="Box Y1", default=0.0)
    selection_box_x2: FloatProperty(name="Box X2", default=0.0)
    selection_box_y2: FloatProperty(name="Box Y2", default=0.0)

    # ------------------------------------------------------------------
    # Conveniências
    # ------------------------------------------------------------------
    @property
    def active_note(self):
        if 0 <= self.active_note_index < len(self.notes):
            return self.notes[self.active_note_index]
        return None

    @property
    def selected_notes(self):
        return [n for n in self.notes if n.selected]

    @property
    def note_count(self) -> int:
        return len(self.notes)

    def get_notes_in_range(self, beat_start: float, beat_end: float,
                           pitch_min: int = 0, pitch_max: int = 127):
        return [
            n for n in self.notes
            if beat_start <= n.start_beat < beat_end
            and pitch_min <= n.pitch <= pitch_max
        ]

    def clear_notes(self) -> None:
        self.notes.clear()
        self.active_note_index = 0


_ALL_CLASSES = [
    PianoRollNoteProperties,
    PianoRollSettingsProperties,
    PianoRollProperties,
]


def register() -> None:
    for cls in _ALL_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_piano_roll = bpy.props.PointerProperty(type=PianoRollProperties)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "daw_piano_roll"):
        del bpy.types.Scene.daw_piano_roll
    for cls in reversed(_ALL_CLASSES):
        bpy.utils.unregister_class(cls)