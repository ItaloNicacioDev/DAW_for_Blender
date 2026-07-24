# modules/patterns/properties.py
"""
Propriedades RNA do Blender para o módulo Patterns.

Responsabilidade:
    Espelhar em PropertyGroups (RNA) os modelos puros de patterns.py,
    clips.py e groups.py, para que a UI e os operadores do Blender
    possam ler/editar o estado. Fica em context.scene.daw_patterns.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .colors import get_color_by_index


# ------------------------------------------------------------------ #
# Nota individual dentro de um pattern
# ------------------------------------------------------------------ #
class PatternNoteProperties(PropertyGroup):
    """Uma nota no grid de um pattern."""

    pitch: IntProperty(name="Nota", default=60, min=0, max=127)
    velocity: FloatProperty(name="Velocity", default=0.8, min=0.0, max=1.0, subtype='FACTOR')
    start_step: IntProperty(name="Step Início", default=0, min=0)
    duration_steps: IntProperty(name="Duração (steps)", default=1, min=1)
    enabled: BoolProperty(name="Ativa", default=True)


# ------------------------------------------------------------------ #
# Pattern
# ------------------------------------------------------------------ #
class PatternProperties(PropertyGroup):
    """Um pattern/sequência musical."""

    name: StringProperty(name="Nome", default="Novo Pattern")
    color: FloatVectorProperty(
        name="Cor", subtype='COLOR', size=3,
        min=0.0, max=1.0, default=get_color_by_index(0),
    )

    length_steps: IntProperty(
        name="Comprimento (steps)", default=16, min=1, max=256,
    )
    bpm: FloatProperty(name="BPM", default=120.0, min=1.0, max=999.0)
    time_signature_num: IntProperty(name="Compasso (num)", default=4, min=1, max=32)
    time_signature_den: IntProperty(name="Compasso (den)", default=4, min=1, max=32)

    notes: CollectionProperty(type=PatternNoteProperties)
    active_note_index: IntProperty(name="Nota Ativa", default=0, min=0)

    is_looping: BoolProperty(name="Loop", default=True)
    swing: FloatProperty(name="Swing", default=0.0, min=0.0, max=1.0, subtype='FACTOR')

    @property
    def note_count(self) -> int:
        return len(self.notes)


# ------------------------------------------------------------------ #
# Clip (instância de pattern na timeline)
# ------------------------------------------------------------------ #
class PatternClipProperties(PropertyGroup):
    """Uma ocorrência de pattern na timeline."""

    pattern_name: StringProperty(name="Pattern", default="")
    track_index: IntProperty(name="Faixa", default=0, min=0)

    start_beat: FloatProperty(name="Início (beats)", default=0.0, min=0.0)
    duration_beats: FloatProperty(name="Duração (beats)", default=4.0, min=0.25)
    offset_beats: FloatProperty(name="Offset (beats)", default=0.0, min=0.0)

    enabled: BoolProperty(name="Ativo", default=True)
    use_color_override: BoolProperty(name="Sobrescrever Cor", default=False)
    color_override: FloatVectorProperty(
        name="Cor Customizada", subtype='COLOR', size=3,
        min=0.0, max=1.0, default=(0.8, 0.8, 0.8),
    )


# ------------------------------------------------------------------ #
# Grupo de patterns
# ------------------------------------------------------------------ #
class PatternGroupProperties(PropertyGroup):
    """Um grupo lógico de patterns."""

    name: StringProperty(name="Nome", default="Novo Grupo")
    color: FloatVectorProperty(
        name="Cor", subtype='COLOR', size=3,
        min=0.0, max=1.0, default=get_color_by_index(0),
    )
    # Armazena nomes de patterns separados por vírgula (simplificado para RNA)
    pattern_names_csv: StringProperty(name="Patterns", default="")

    @property
    def pattern_names(self) -> list:
        return [n.strip() for n in self.pattern_names_csv.split(",") if n.strip()]

    def add_pattern_name(self, name: str) -> None:
        names = self.pattern_names
        if name not in names:
            names.append(name)
            self.pattern_names_csv = ",".join(names)

    def remove_pattern_name(self, name: str) -> None:
        names = [n for n in self.pattern_names if n != name]
        self.pattern_names_csv = ",".join(names)


# ------------------------------------------------------------------ #
# Estado global do Patterns — anexado a context.scene.daw_patterns
# ------------------------------------------------------------------ #
class PatternsProperties(PropertyGroup):
    """Estado completo do módulo Patterns para uma cena."""

    patterns: CollectionProperty(type=PatternProperties)
    active_pattern_index: IntProperty(name="Pattern Ativo", default=0, min=0)

    clips: CollectionProperty(type=PatternClipProperties)
    active_clip_index: IntProperty(name="Clip Ativo", default=0, min=0)

    groups: CollectionProperty(type=PatternGroupProperties)
    active_group_index: IntProperty(name="Grupo Ativo", default=0, min=0)

    # --- Grid editor settings ---
    grid_step_division: IntProperty(name="Divisão do Grid", default=4, min=1, max=64)
    piano_roll_zoom: FloatProperty(name="Zoom", default=1.0, min=0.1, max=10.0)

    # ------------------------------------------------------------------
    # Conveniências
    # ------------------------------------------------------------------
    @property
    def active_pattern(self):
        if 0 <= self.active_pattern_index < len(self.patterns):
            return self.patterns[self.active_pattern_index]
        return None

    @property
    def active_clip(self):
        if 0 <= self.active_clip_index < len(self.clips):
            return self.clips[self.active_clip_index]
        return None

    @property
    def active_group(self):
        if 0 <= self.active_group_index < len(self.groups):
            return self.groups[self.active_group_index]
        return None

    def get_pattern_by_name(self, name: str):
        for p in self.patterns:
            if p.name == name:
                return p
        return None

    def get_clips_for_pattern(self, pattern_name: str):
        return [c for c in self.clips if c.pattern_name == pattern_name]


_ALL_CLASSES = [
    PatternNoteProperties,
    PatternProperties,
    PatternClipProperties,
    PatternGroupProperties,
    PatternsProperties,
]


def register() -> None:
    for cls in _ALL_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_patterns = bpy.props.PointerProperty(type=PatternsProperties)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "daw_patterns"):
        del bpy.types.Scene.daw_patterns
    for cls in reversed(_ALL_CLASSES):
        bpy.utils.unregister_class(cls)