# modules/playlist/__init__.py
"""
Módulo Playlist (timeline de clips) da DAW.

CORREÇÃO: este arquivo continha, por engano, uma cópia de
`modules/piano_roll/register.py` (cabeçalho dizendo isso mesmo, e um
`from .properties import _ALL_CLASSES as property_classes,
PianoRollProperties` -- uma classe que não existe neste módulo, só no
piano_roll). Isso derrubava o playlist inteiro com
`ImportError: cannot import name 'PianoRollProperties'`. O registro
de verdade já existia certinho em `playlist/register.py`
(`PlaylistProperties`, `daw_playlist`) -- só faltava este `__init__.py`
apontar pra ele, no mesmo padrão usado pelos outros módulos (ver
`channel_rack/__init__.py`).

Responsabilidade:
    Faixas (tracks) e clips posicionados na timeline principal, com
    seleção, snapping e estado de reprodução -- pure-python (sem bpy)
    nos modelos, RNA/UI nos demais arquivos.

Arquitetura:
    tracks.py     — PlaylistTrack: modelo puro de uma faixa (sem bpy)
    clips.py      — PlaylistClip: modelo puro de um clip (sem bpy)
    markers.py    — TimelineMarker: modelo puro de marcador (sem bpy)
    playback.py   — PlaybackState: estado puro de reprodução (sem bpy)
    selection.py  — seleção de clips (sem bpy)
    snapping.py   — snap ao grid/clipes/marcadores (sem bpy)
    utils.py      — reexporta selection.py hoje (ver nota no arquivo)
    properties.py — PropertyGroups do Blender (estado real da UI)
    operators.py  — Operators do Blender (ações de edição)
    ui.py         — Painéis do Blender
    register.py   — register() / unregister()
"""
from __future__ import annotations

from .tracks import PlaylistTrack
from .clips import PlaylistClip
from .markers import TimelineMarker
from .playback import PlaybackState
from .selection import (
    select_all,
    deselect_all,
    invert_selection,
    select_in_range,
    get_selected,
    delete_selected,
    duplicate_selected,
    move_selected,
)
from .snapping import snap_to_grid, snap_to_nearest_clip_edge, snap_to_marker
from .register import register, unregister

__all__ = [
    # Modelo puro
    "PlaylistTrack", "PlaylistClip", "TimelineMarker", "PlaybackState",
    # Seleção
    "select_all", "deselect_all", "invert_selection", "select_in_range",
    "get_selected", "delete_selected", "duplicate_selected", "move_selected",
    # Snapping
    "snap_to_grid", "snap_to_nearest_clip_edge", "snap_to_marker",
    # Blender
    "register", "unregister",
]