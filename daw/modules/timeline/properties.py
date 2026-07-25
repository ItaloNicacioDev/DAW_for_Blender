"""
timeline/properties.py
Definição de todas as propriedades da timeline no Blender (PropertyGroup).
Armazena estado de clips, tracks, cursor, zoom e snapping.
"""

import bpy
from bpy.props import (
    IntProperty,
    FloatProperty,
    BoolProperty,
    StringProperty,
    EnumProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup


# ---------------------------------------------------------------------------
# Clip
# ---------------------------------------------------------------------------

class DAW_ClipProperties(PropertyGroup):
    """Um clip de áudio/MIDI posicionado numa track."""

    name: StringProperty(
        name="Nome",
        default="Clip",
    )
    track_index: IntProperty(
        name="Track",
        default=0,
        min=0,
    )
    start_beat: FloatProperty(
        name="Início (beats)",
        default=0.0,
        min=0.0,
    )
    length_beats: FloatProperty(
        name="Duração (beats)",
        default=4.0,
        min=0.0625,
    )
    color: bpy.props.FloatVectorProperty(
        name="Cor",
        subtype="COLOR",
        size=4,
        default=(0.2, 0.5, 0.9, 1.0),
        min=0.0,
        max=1.0,
    )
    muted: BoolProperty(
        name="Mudo",
        default=False,
    )
    selected: BoolProperty(
        name="Selecionado",
        default=False,
    )
    # Referência ao sample/MIDI source (nome do arquivo ou ID de track MIDI)
    source_path: StringProperty(
        name="Fonte",
        default="",
        subtype="FILE_PATH",
    )
    clip_type: EnumProperty(
        name="Tipo",
        items=[
            ("AUDIO", "Áudio", "Clip de áudio"),
            ("MIDI",  "MIDI",  "Clip MIDI"),
        ],
        default="AUDIO",
    )
    # Offset interno (trim de início dentro do sample)
    offset_beats: FloatProperty(
        name="Offset (beats)",
        default=0.0,
        min=0.0,
    )


# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------

class DAW_TrackProperties(PropertyGroup):
    """Uma faixa horizontal da timeline."""

    name: StringProperty(
        name="Nome",
        default="Track",
    )
    track_type: EnumProperty(
        name="Tipo",
        items=[
            ("AUDIO",  "Áudio",  "Track de áudio"),
            ("MIDI",   "MIDI",   "Track MIDI"),
            ("BUS",    "Bus",    "Track de roteamento"),
            ("MASTER", "Master", "Track master"),
        ],
        default="AUDIO",
    )
    muted: BoolProperty(
        name="Mudo",
        default=False,
    )
    solo: BoolProperty(
        name="Solo",
        default=False,
    )
    armed: BoolProperty(
        name="Gravação",
        default=False,
        description="Habilitar gravação nesta track",
    )
    volume: FloatProperty(
        name="Volume",
        default=1.0,
        min=0.0,
        max=2.0,
        subtype="FACTOR",
    )
    color: bpy.props.FloatVectorProperty(
        name="Cor",
        subtype="COLOR",
        size=3,
        default=(0.3, 0.3, 0.3),
        min=0.0,
        max=1.0,
    )
    height: FloatProperty(
        name="Altura (px)",
        default=60.0,
        min=24.0,
        max=200.0,
    )
    collapsed: BoolProperty(
        name="Recolhida",
        default=False,
    )
    clips: CollectionProperty(
        type=DAW_ClipProperties,
        name="Clips",
    )
    active_clip_index: IntProperty(
        name="Clip Ativo",
        default=0,
        min=0,
    )


# ---------------------------------------------------------------------------
# Marker
# ---------------------------------------------------------------------------

class DAW_MarkerProperties(PropertyGroup):
    """Marcador de posição na timeline."""

    name: StringProperty(
        name="Nome",
        default="Marker",
    )
    position_beat: FloatProperty(
        name="Posição (beat)",
        default=0.0,
        min=0.0,
    )
    color: bpy.props.FloatVectorProperty(
        name="Cor",
        subtype="COLOR",
        size=4,
        default=(1.0, 0.8, 0.0, 1.0),
        min=0.0,
        max=1.0,
    )
    locked: BoolProperty(
        name="Travado",
        default=False,
    )


# ---------------------------------------------------------------------------
# Configuração global da timeline
# ---------------------------------------------------------------------------

class DAW_TimelineSettings(PropertyGroup):
    """Configurações globais da timeline (zoom, snap, cursor, etc.)."""

    # --- Tracks e clips ---
    tracks: CollectionProperty(
        type=DAW_TrackProperties,
        name="Tracks",
    )
    active_track_index: IntProperty(
        name="Track Ativa",
        default=0,
        min=0,
    )

    # --- Marcadores ---
    markers: CollectionProperty(
        type=DAW_MarkerProperties,
        name="Marcadores",
    )
    active_marker_index: IntProperty(
        name="Marcador Ativo",
        default=0,
        min=0,
    )

    # --- Cursor / Playhead ---
    cursor_beat: FloatProperty(
        name="Cursor (beat)",
        default=0.0,
        min=0.0,
        description="Posição atual do playhead em beats",
    )
    loop_start: FloatProperty(
        name="Loop Start (beat)",
        default=0.0,
        min=0.0,
    )
    loop_end: FloatProperty(
        name="Loop End (beat)",
        default=8.0,
        min=0.0,
    )
    loop_enabled: BoolProperty(
        name="Loop",
        default=False,
    )

    # --- Zoom ---
    zoom_level: FloatProperty(
        name="Zoom",
        default=1.0,
        min=0.05,
        max=32.0,
        description="Pixels por beat",
    )
    scroll_offset: FloatProperty(
        name="Scroll (beat)",
        default=0.0,
        min=0.0,
        description="Deslocamento horizontal em beats",
    )
    scroll_y: FloatProperty(
        name="Scroll Y (px)",
        default=0.0,
        min=0.0,
        description="Deslocamento vertical em pixels",
    )
    pixels_per_beat: FloatProperty(
        name="Pixels/beat",
        default=80.0,
        min=8.0,
        max=1024.0,
    )

    # --- Snapping ---
    snap_enabled: BoolProperty(
        name="Snap",
        default=True,
    )
    snap_mode: EnumProperty(
        name="Modo de Snap",
        items=[
            ("BAR",      "Compasso",   "Snap ao compasso"),
            ("BEAT",     "Beat",       "Snap ao beat"),
            ("HALF",     "1/2",        "Snap à semínima"),
            ("QUARTER",  "1/4",        "Snap à colcheia"),
            ("EIGHTH",   "1/8",        "Snap à semicolcheia"),
            ("SIXTEENTH","1/16",       "Snap à fusa"),
            ("FREE",     "Livre",      "Sem snap"),
        ],
        default="BEAT",
    )

    # --- Exibição ---
    show_markers: BoolProperty(
        name="Mostrar Marcadores",
        default=True,
    )
    show_loop_region: BoolProperty(
        name="Mostrar Região de Loop",
        default=True,
    )
    show_beat_numbers: BoolProperty(
        name="Mostrar Números de Beat",
        default=True,
    )
    ruler_height: FloatProperty(
        name="Altura da Régua (px)",
        default=28.0,
        min=16.0,
        max=60.0,
    )
    track_header_width: FloatProperty(
        name="Largura do Header (px)",
        default=160.0,
        min=80.0,
        max=320.0,
    )

    # --- Seleção de range ---
    selection_start: FloatProperty(
        name="Seleção Início",
        default=-1.0,
    )
    selection_end: FloatProperty(
        name="Seleção Fim",
        default=-1.0,
    )


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------

CLASSES = [
    DAW_ClipProperties,
    DAW_TrackProperties,
    DAW_MarkerProperties,
    DAW_TimelineSettings,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_timeline = PointerProperty(type=DAW_TimelineSettings)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.daw_timeline