# modules/mixer/__init__.py
"""
Módulo Mixer da DAW para Blender.

Arquitetura
-----------
O módulo é dividido em duas camadas:

1. Modelo puro (sem bpy) — usável fora do Blender (testes, engine de áudio):
   tracks.py   → MixerTrack     (volume, pan, mute, solo, inserts, sends)
   inserts.py  → InsertSlot     (efeito + parâmetros genéricos)
   sends.py    → Send           (envio auxiliar para bus)
   routing.py  → MixerBus       (buses de saída: Master + auxiliares)
   mixer.py    → Mixer          (contêiner central de tracks/buses)
   effects.py  → catálogo de tipos de efeito e parâmetros padrão

2. Integração Blender (bpy) — UI, operadores, RNA e medidores:
   properties.py  → PropertyGroups (MixerProperties, MixerTrackProperties, …)
   operators.py   → Operators (adicionar/remover/duplicar/mover faixas, buses, inserts, sends)
   ui.py          → Painéis, listas e menus no Sequence Editor (aba DAW)
   presets.py     → Salva/carrega presets de insert e channel strip (JSON)
   meters.py      → VU meters com timer periódico (~20 Hz)
   utils.py       → Utilitários numéricos e ponte com o motor de áudio
   register.py    → Registro/desregistro de todas as classes + garantia do bus Master

Uso típico (fora do Blender):
    from daw.modules.mixer import Mixer, MixerTrack
    mixer = Mixer()
    mixer.add_track("Kick")

Uso típico (dentro do Blender):
    mixer_props = context.scene.daw_mixer   # instância de MixerProperties
    mixer_props.tracks.add()
"""
from __future__ import annotations

# ------------------------------------------------------------------ #
# Modelo puro — exposto para importação externa
# ------------------------------------------------------------------ #
from .mixer import Mixer
from .tracks import MixerTrack, MASTER_TRACK_NAME, get_color_by_index
from .routing import MixerBus, create_master_bus, bus_names
from .inserts import InsertSlot
from .sends import Send, MAX_SENDS_PER_TRACK
from .effects import (
    EFFECT_TYPES,
    EFFECT_TYPE_ITEMS,
    default_params_for,
    label_for,
    icon_for,
    enum_items,
)

# ------------------------------------------------------------------ #
# Integração Blender — registro e desregistro
# ------------------------------------------------------------------ #
from .register import register, unregister

# ------------------------------------------------------------------ #
# Utilitários frequentemente usados por outros módulos da DAW
# ------------------------------------------------------------------ #
from .utils import (
    clamp,
    clamp_index,
    db_to_linear,
    linear_to_db,
    linear_pan_gains,
    unique_track_name,
    unique_bus_name,
)

__all__ = [
    # Modelo puro
    "Mixer",
    "MixerTrack",
    "MixerBus",
    "InsertSlot",
    "Send",
    "MASTER_TRACK_NAME",
    "MAX_SENDS_PER_TRACK",
    "get_color_by_index",
    "create_master_bus",
    "bus_names",
    # Efeitos
    "EFFECT_TYPES",
    "EFFECT_TYPE_ITEMS",
    "default_params_for",
    "label_for",
    "icon_for",
    "enum_items",
    # Registro Blender
    "register",
    "unregister",
    # Utilitários
    "clamp",
    "clamp_index",
    "db_to_linear",
    "linear_to_db",
    "linear_pan_gains",
    "unique_track_name",
    "unique_bus_name",
]