# modules/effects/utils.py
"""
Utilitários do módulo de Efeitos.

Responsabilidade:
    Funções auxiliares usadas pelos operadores e pela UI: obter/criar a
    cadeia de um canal, sincronizar dicts de parâmetros com os
    PropertyGroups RNA, e outras conveniências.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from .properties import EffectsRackProperties, EffectsChainProperties, EffectSlotProperties


def clamp_index(index: int, length: int) -> int:
    """Restringe um índice ao range válido [0, length-1]. Retorna 0 se length <= 0."""
    if length <= 0:
        return 0
    return max(0, min(index, length - 1))


def get_chain(rack_props: "EffectsRackProperties", channel_index: int) -> Optional["EffectsChainProperties"]:
    """Retorna a EffectsChainProperties associada a um canal, ou None se não existir."""
    for chain in rack_props.chains:
        if chain.channel_index == channel_index:
            return chain
    return None


def get_or_create_chain(rack_props: "EffectsRackProperties", channel_index: int) -> "EffectsChainProperties":
    """Retorna a cadeia do canal, criando uma nova entrada em `chains` se necessário."""
    chain = get_chain(rack_props, channel_index)
    if chain is not None:
        return chain

    chain = rack_props.chains.add()
    chain.channel_index = channel_index
    return chain


def params_attr_name(effect_type: str) -> str:
    """Nome do atributo em EffectSlotProperties que guarda os parâmetros de `effect_type`."""
    return effect_type.lower()


def apply_params_dict_to_slot(slot: "EffectSlotProperties", params_dict: Dict[str, Any]) -> None:
    """
    Copia um dict de parâmetros (vindo de um preset ou de um EffectSlot puro)
    para o PropertyGroup RNA correspondente ao effect_type do slot.
    """
    target = slot.get_active_params()

    if slot.effect_type == "EQ":
        bands_data = params_dict.get("bands", [])
        target.bands.clear()
        for band_data in bands_data:
            band = target.bands.add()
            for key in ("enabled", "band_type", "freq", "gain_db", "q"):
                if key in band_data:
                    setattr(band, key, band_data[key])
        return

    for key, value in params_dict.items():
        if hasattr(target, key):
            setattr(target, key, value)


def slot_params_to_dict(slot: "EffectSlotProperties") -> Dict[str, Any]:
    """Converte os parâmetros RNA atuais do slot (conforme effect_type) para um dict simples."""
    target = slot.get_active_params()

    if slot.effect_type == "EQ":
        return {
            "bands": [
                {
                    "enabled": b.enabled,
                    "band_type": b.band_type,
                    "freq": b.freq,
                    "gain_db": b.gain_db,
                    "q": b.q,
                }
                for b in target.bands
            ]
        }

    result: Dict[str, Any] = {}
    for prop in target.bl_rna.properties:
        if prop.is_readonly or prop.identifier in ("rna_type",):
            continue
        result[prop.identifier] = getattr(target, prop.identifier)
    return result


def any_bypassed_count(chain: "EffectsChainProperties") -> int:
    """Conta quantos slots da cadeia estão em bypass (útil para indicadores na UI)."""
    return sum(1 for s in chain.slots if s.bypass or not s.enabled)