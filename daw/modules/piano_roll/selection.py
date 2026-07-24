# modules/piano_roll/selection.py
"""
Gerenciamento de seleção de notas no Piano Roll.

Responsabilidade:
    Manter o estado de seleção de notas, permitir seleção por
    retângulo (box select), inverter seleção, e operar apenas
    sobre notas selecionadas.
"""
from __future__ import annotations

from typing import List, Optional

from .notes import PianoRollNote


def select_all(notes: List[PianoRollNote]) -> None:
    for note in notes:
        note.selected = True


def deselect_all(notes: List[PianoRollNote]) -> None:
    for note in notes:
        note.selected = False


def invert_selection(notes: List[PianoRollNote]) -> None:
    for note in notes:
        note.selected = not note.selected


def select_in_range(notes: List[PianoRollNote],
                    beat_start: float, beat_end: float,
                    pitch_min: int = 0, pitch_max: int = 127,
                    add_to_selection: bool = False) -> None:
    """Seleciona notas dentro de um retângulo tempo x pitch."""
    if not add_to_selection:
        deselect_all(notes)

    for note in notes:
        if (beat_start <= note.start_beat < beat_end and
                pitch_min <= note.pitch <= pitch_max):
            note.selected = True


def get_selected_notes(notes: List[PianoRollNote]) -> List[PianoRollNote]:
    """Retorna apenas as notas selecionadas."""
    return [n for n in notes if n.selected]


def delete_selected(notes: List[PianoRollNote]) -> None:
    """Remove as notas selecionadas de uma lista in-place."""
    notes[:] = [n for n in notes if not n.selected]


def duplicate_selected(notes: List[PianoRollNote],
                       offset_beats: float = 0.0) -> List[PianoRollNote]:
    """Duplica as notas selecionadas, retornando as novas notas."""
    selected = get_selected_notes(notes)
    new_notes = []
    for note in selected:
        dup = note.duplicate()
        dup.start_beat += offset_beats
        dup.selected = True
        note.selected = False  # desseleciona original
        new_notes.append(dup)
    return new_notes


def move_selected(notes: List[PianoRollNote],
                  delta_beats: float, delta_pitch: int) -> None:
    """Move todas as notas selecionadas."""
    for note in notes:
        if note.selected:
            note.move(delta_beats, delta_pitch)


def transpose_selected(notes: List[PianoRollNote], semitones: int) -> None:
    """Transpõe as notas selecionadas em semitons."""
    move_selected(notes, 0.0, semitones)


def set_velocity_selected(notes: List[PianoRollNote], velocity: float) -> None:
    """Define a velocity de todas as notas selecionadas."""
    for note in notes:
        if note.selected:
            note.velocity = max(0.0, min(1.0, velocity))