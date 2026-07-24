# modules/patterns/groups.py
"""
Grupos de Patterns — sem dependência de bpy.

Responsabilidade:
    Agrupar patterns logicamente (ex: "Intro", "Verse", "Chorus")
    para organização e navegação rápida no projeto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .colors import get_color_by_index


@dataclass
class PatternGroup:
    """Um grupo lógico de patterns."""

    name: str = "Novo Grupo"
    color: tuple = field(default_factory=lambda: get_color_by_index(0))
    pattern_names: List[str] = field(default_factory=list)

    def add_pattern(self, name: str) -> bool:
        if name not in self.pattern_names:
            self.pattern_names.append(name)
            return True
        return False

    def remove_pattern(self, name: str) -> bool:
        if name in self.pattern_names:
            self.pattern_names.remove(name)
            return True
        return False

    def __repr__(self) -> str:
        return f"PatternGroup(name={self.name!r}, patterns={len(self.pattern_names)})"