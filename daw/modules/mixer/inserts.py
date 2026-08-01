# modules/mixer/inserts.py
"""
InsertSlot — modelo puro (sem bpy) de um slot de efeito na cadeia de
inserts de uma faixa do Mixer.

Responsabilidade:
    Representar um efeito inserido em uma faixa do mixer: qual tipo de
    efeito é (ver `effects.py`), se está habilitado/em bypass, e seus
    parâmetros nomeados (ganhos, tempos, mix, etc.).

    Este é o "dado real" do insert; o estado editável exposto ao Blender
    vive em `properties.py` (`MixerInsertSlotProperties`), que espelha
    estes mesmos campos (effect_type / enabled / bypass / params) para
    desenho da UI — ver `presets.py` (`apply_params_to_insert_slot`,
    `insert_slot_params_to_dict`) para a ponte entre os dois lados.

    Os valores padrão de `params` para cada tipo de efeito vêm do
    catálogo em `effects.py` (`default_params_for`); o processamento de
    áudio real de cada efeito é responsabilidade de outro módulo (o
    processamento em si, não a UI/estado) — aqui só vive o estado.

Arquitetura (ver mixer/__init__.py para o mapa completo do módulo):
    tracks.py   — MixerTrack: modelo puro de uma faixa
    inserts.py  — InsertSlot: slot de efeito dentro de uma faixa (este arquivo)
    sends.py    — Send: envio auxiliar de uma faixa para um bus
    routing.py  — buses/roteamento de saída (Master + auxiliares)
    mixer.py    — Mixer: contêiner central de faixas/buses (sem bpy)
    effects.py  — catálogo de tipos de efeito e parâmetros padrão
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .effects import default_params_for, is_valid_effect_type


@dataclass
class InsertSlot:
    """Um slot de efeito na cadeia de inserts de uma faixa do mixer."""

    effect_type: str = "EQ"
    enabled: bool = True
    bypass: bool = False
    params: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Se nenhum parâmetro foi passado explicitamente na criação, inicia
        # com os valores padrão do catálogo de efeitos (ver effects.py) —
        # mesmo comportamento que o lado RNA aplica via
        # `presets.apply_params_to_insert_slot(slot, default_params_for(...))`.
        if not self.params and is_valid_effect_type(self.effect_type):
            self.params = default_params_for(self.effect_type)

    # ------------------------------------------------------------------
    # Parâmetros
    # ------------------------------------------------------------------
    def get_param(self, name: str, default: float = 0.0) -> float:
        return self.params.get(name, default)

    def set_param(self, name: str, value: float) -> None:
        self.params[name] = float(value)

    def reset_params(self) -> None:
        """Restaura os parâmetros para os valores padrão do tipo de efeito."""
        self.params = default_params_for(self.effect_type)

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    def is_active(self) -> bool:
        """Um insert processa áudio se estiver habilitado e não em bypass."""
        return self.enabled and not self.bypass

    def duplicate(self) -> "InsertSlot":
        return InsertSlot(
            effect_type=self.effect_type,
            enabled=self.enabled,
            bypass=self.bypass,
            params=dict(self.params),
        )

    # ------------------------------------------------------------------
    # Serialização (mesmo formato usado por mixer/presets.py no lado RNA)
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "effect_type": self.effect_type,
            "enabled": self.enabled,
            "bypass": self.bypass,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InsertSlot":
        return cls(
            effect_type=data.get("effect_type", "EQ"),
            enabled=bool(data.get("enabled", True)),
            bypass=bool(data.get("bypass", False)),
            params=dict(data.get("params", {})),
        )

    def __repr__(self) -> str:
        state = "bypass" if self.bypass else ("off" if not self.enabled else "on")
        return f"<InsertSlot {self.effect_type} ({state})>"