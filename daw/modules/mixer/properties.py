# modules/mixer/properties.py
"""
Propriedades RNA do Blender para o módulo Mixer.

Responsabilidade:
    Espelhar em PropertyGroups (RNA) o modelo puro definido em tracks.py,
    routing.py e sends.py, para que a UI (ui.py) e os operadores
    (operators.py) do Blender possam ler/editar o estado do mixer.
    Este é o "dado vivo": fica em context.scene.daw_mixer.

    meters.py lê e escreve diretamente nestas propriedades (mixer_props.
    channels/master/meter) para animar os VU meters; utils.py (funções
    unique_track_name, unique_bus_name, any_solo_active, is_track_audible)
    também opera sobre estas mesmas propriedades — por isso os nomes de
    atributo aqui (tracks/buses/name/solo/mute/volume/pan) são mantidos
    idênticos ao que aqueles dois módulos esperam.

Arquitetura (ver mixer/__init__.py para o mapa completo do módulo):
    tracks.py    — MixerTrack: modelo puro de uma faixa (sem bpy)
    routing.py   — MixerBus: buses/roteamento (sem bpy)
    sends.py     — Send: envio auxiliar de uma faixa (sem bpy)
    effects.py   — catálogo de tipos de efeito para os inserts
    utils.py     — ponte com o motor de áudio + utilitários sobre RNA
    meters.py    — VU meters, lê/escreve nestas propriedades
    properties.py — este arquivo: espelho RNA de tudo isso
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

from .tracks import MASTER_TRACK_NAME, get_color_by_index
from .effects import EFFECT_TYPE_ITEMS
from .sends import MAX_SENDS_PER_TRACK
from .utils import (
    any_solo_active,
    is_track_audible,
    push_volume_to_engine,
    push_pan_to_engine,
    push_mute_to_engine,
    push_solo_to_engine,
    push_master_volume_to_engine,
)


# ------------------------------------------------------------------ #
# Callbacks de update — ponte com o motor de áudio (ver utils.py)
# ------------------------------------------------------------------ #
def _on_track_volume_change(self: "MixerTrackProperties", context) -> None:
    push_volume_to_engine(self.source_index, self.volume)


def _on_track_pan_change(self: "MixerTrackProperties", context) -> None:
    push_pan_to_engine(self.source_index, self.pan)


def _on_track_mute_change(self: "MixerTrackProperties", context) -> None:
    push_mute_to_engine(self.source_index, self.mute)


def _on_track_solo_change(self: "MixerTrackProperties", context) -> None:
    push_solo_to_engine(self.source_index, self.solo)


def _on_master_volume_change(self: "MixerProperties", context) -> None:
    push_master_volume_to_engine(self.master_volume)


def _on_active_track_index_change(self: "MixerProperties", context) -> None:
    """Garante que o índice ativo nunca fique fora do range da coleção."""
    if len(self.tracks) == 0:
        return
    if self.active_track_index >= len(self.tracks):
        self.active_track_index = len(self.tracks) - 1


def _on_active_bus_index_change(self: "MixerProperties", context) -> None:
    if len(self.buses) == 0:
        return
    if self.active_bus_index >= len(self.buses):
        self.active_bus_index = len(self.buses) - 1


# ------------------------------------------------------------------ #
# Medidor (VU meter) — lido/escrito por meters.py
# ------------------------------------------------------------------ #
class MixerMeterProperties(PropertyGroup):
    """Estado de um medidor de nível (canal ou master)."""

    peak_left: FloatProperty(name="Pico Esquerda", default=0.0, min=0.0)
    peak_right: FloatProperty(name="Pico Direita", default=0.0, min=0.0)

    peak_hold_left: FloatProperty(name="Hold Esquerda", default=0.0, min=0.0)
    peak_hold_right: FloatProperty(name="Hold Direita", default=0.0, min=0.0)

    rms_left: FloatProperty(name="RMS Esquerda", default=0.0, min=0.0)
    rms_right: FloatProperty(name="RMS Direita", default=0.0, min=0.0)

    clipping: BoolProperty(name="Clipping", default=False)


# ------------------------------------------------------------------ #
# Inserts (efeitos) — catálogo genérico (ver effects.py)
# ------------------------------------------------------------------ #
class MixerInsertParamProperties(PropertyGroup):
    """Um parâmetro (nome/valor) genérico de um insert de efeito."""

    name: StringProperty(name="Parâmetro", default="")
    value: FloatProperty(name="Valor", default=0.0)


class MixerInsertSlotProperties(PropertyGroup):
    """Um slot de efeito na cadeia de inserts de uma faixa do mixer."""

    effect_type: EnumProperty(
        name="Tipo",
        description="Tipo de efeito deste insert",
        items=EFFECT_TYPE_ITEMS,
        default="EQ",
    )
    enabled: BoolProperty(name="Ativo", default=True)
    bypass: BoolProperty(name="Bypass", default=False)

    params: CollectionProperty(type=MixerInsertParamProperties)

    def get_param(self, name: str, default: float = 0.0) -> float:
        for p in self.params:
            if p.name == name:
                return p.value
        return default

    def set_param(self, name: str, value: float) -> None:
        for p in self.params:
            if p.name == name:
                p.value = value
                return
        p = self.params.add()
        p.name = name
        p.value = value


# ------------------------------------------------------------------ #
# Sends (envios auxiliares)
# ------------------------------------------------------------------ #
class MixerSendProperties(PropertyGroup):
    """Um envio auxiliar de uma faixa para um bus (ver sends.py)."""

    bus_name: StringProperty(name="Bus", default="")
    level: FloatProperty(
        name="Nível", default=0.0, min=0.0, max=1.0, subtype='FACTOR'
    )
    pre_fader: BoolProperty(name="Pré-Fader", default=False)
    enabled: BoolProperty(name="Ativo", default=True)


# ------------------------------------------------------------------ #
# Faixa (channel strip)
# ------------------------------------------------------------------ #
class MixerTrackProperties(PropertyGroup):
    """Uma faixa do mixer — espelho RNA de tracks.MixerTrack."""

    name: StringProperty(name="Nome", default="Nova Faixa")

    color: FloatVectorProperty(
        name="Cor",
        subtype='COLOR',
        size=3,
        min=0.0,
        max=1.0,
        default=get_color_by_index(0),
    )

    volume: FloatProperty(
        name="Volume",
        default=0.78,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        update=_on_track_volume_change,
    )
    pan: FloatProperty(
        name="Pan",
        default=0.0,
        min=-1.0,
        max=1.0,
        subtype='FACTOR',
        update=_on_track_pan_change,
    )
    mute: BoolProperty(name="Mudo", default=False, update=_on_track_mute_change)
    solo: BoolProperty(name="Solo", default=False, update=_on_track_solo_change)

    output_bus: StringProperty(name="Saída", default=MASTER_TRACK_NAME)

    # Índice do canal correspondente no motor de áudio (ver utils.get_engine).
    # -1 = faixa ainda não vinculada a um canal real (modo local/simulado).
    source_index: IntProperty(name="Canal do Motor", default=-1, min=-1)

    inserts: CollectionProperty(type=MixerInsertSlotProperties)
    active_insert_index: IntProperty(name="Insert Ativo", default=0, min=0)

    sends: CollectionProperty(type=MixerSendProperties)
    active_send_index: IntProperty(name="Send Ativo", default=0, min=0)

    meter: PointerProperty(type=MixerMeterProperties)

    @property
    def is_audible(self) -> bool:
        """Mesma regra de tracks.MixerTrack.is_audible, aplicada à faixa RNA."""
        mixer_props = getattr(self.id_data, "daw_mixer", None)
        solo_active = any_solo_active(mixer_props) if mixer_props is not None else self.solo
        return is_track_audible(self, solo_active)

    def get_send(self, bus_name: str):
        for send in self.sends:
            if send.bus_name == bus_name:
                return send
        return None

    def can_add_send(self) -> bool:
        return len(self.sends) < MAX_SENDS_PER_TRACK


# ------------------------------------------------------------------ #
# Bus (Master + auxiliares)
# ------------------------------------------------------------------ #
class MixerBusProperties(PropertyGroup):
    """Um bus de saída (Master ou auxiliar) — espelho RNA de routing.MixerBus."""

    name: StringProperty(name="Nome", default="Bus")
    volume: FloatProperty(
        name="Volume", default=0.8, min=0.0, max=1.0, subtype='FACTOR'
    )
    mute: BoolProperty(name="Mudo", default=False)
    is_master: BoolProperty(name="É o Master", default=False)

    meter: PointerProperty(type=MixerMeterProperties)


# ------------------------------------------------------------------ #
# Estado global do Mixer — anexado a context.scene.daw_mixer
# ------------------------------------------------------------------ #
class MixerProperties(PropertyGroup):
    """Estado completo do Mixer para uma cena."""

    tracks: CollectionProperty(type=MixerTrackProperties)
    active_track_index: IntProperty(
        name="Faixa Ativa", default=0, min=0, update=_on_active_track_index_change
    )

    buses: CollectionProperty(type=MixerBusProperties)
    active_bus_index: IntProperty(
        name="Bus Ativo", default=0, min=0, update=_on_active_bus_index_change
    )

    master_volume: FloatProperty(
        name="Volume Master",
        default=0.85,
        min=0.0,
        max=2.0,
        subtype='FACTOR',
        update=_on_master_volume_change,
    )

    # --- Medição (usado por meters.py) ---
    meters_enabled: BoolProperty(name="Medidores Ativos", default=True)
    meter_decay_speed: FloatProperty(
        name="Velocidade de Decaimento", default=8.0, min=0.1, max=60.0
    )

    # ------------------------------------------------------------------
    # Conveniências
    # ------------------------------------------------------------------
    @property
    def active_track(self):
        if 0 <= self.active_track_index < len(self.tracks):
            return self.tracks[self.active_track_index]
        return None

    @property
    def active_bus(self):
        if 0 <= self.active_bus_index < len(self.buses):
            return self.buses[self.active_bus_index]
        return None

    @property
    def channels(self):
        """Alias esperado por meters.py (mixer_props.channels)."""
        return self.tracks

    @property
    def master(self):
        """Alias esperado por meters.py (mixer_props.master.meter / .volume).

        O bus Master é sempre o índice 0 de `buses` (ver register.py, que
        garante sua criação ao registrar o addon / carregar um arquivo).
        """
        if len(self.buses) > 0:
            return self.buses[0]
        return None

    def any_solo_active(self) -> bool:
        return any(t.solo for t in self.tracks)


_ALL_CLASSES = [
    MixerMeterProperties,
    MixerInsertParamProperties,
    MixerInsertSlotProperties,
    MixerSendProperties,
    MixerTrackProperties,
    MixerBusProperties,
    MixerProperties,
]


def register() -> None:
    for cls in _ALL_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_mixer = bpy.props.PointerProperty(type=MixerProperties)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "daw_mixer"):
        del bpy.types.Scene.daw_mixer
    for cls in reversed(_ALL_CLASSES):
        bpy.utils.unregister_class(cls)