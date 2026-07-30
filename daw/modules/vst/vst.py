# modules/vst/vst.py
"""
Modelo puro de um plugin VST (efeito ou instrumento).

Responsabilidades:
    - Representar um VST carregado com seus parâmetros
    - Armazenar path do VST, tipo (effect/instrument), bypass, presets
    - Expor interface de get/set de parâmetros por ID ou nome
    - SEM dependência de bpy (portável para motor C++/audio)

Processamento real: delegado a DawdreamerBridge (vst_bridge.py)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class VSTProgramType(Enum):
    """Tipo de VST"""
    EFFECT = "EFFECT"
    INSTRUMENT = "INSTRUMENT"


@dataclass
class VSTProgramParameter:
    """Representa um parâmetro do VST"""
    id: int
    name: str
    value: float  # 0.0 - 1.0 (normalizado)
    min_value: float = 0.0
    max_value: float = 1.0
    label: str = ""
    is_automatable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VSTProgramParameter:
        return cls(**data)


@dataclass
class VSTProgramState:
    """Estado completo de um programa VST (snapshot)"""
    name: str
    parameters: Dict[int, float]  # param_id -> normalized value (0.0-1.0)
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "parameters": self.parameters,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VSTProgramState:
        return cls(**data)


class VST:
    """Modelo puro de um plugin VST"""

    def __init__(
        self,
        path: str | Path,
        name: str,
        vst_type: VSTProgramType = VSTProgramType.EFFECT,
        vst_id: str = "",
        bypass: bool = False,
    ):
        self.path = Path(path)
        self.name = name
        self.vst_type = vst_type
        self.vst_id = vst_id or self.name.lower().replace(" ", "_")
        self.bypass = bypass

        # Estado de parâmetros: {param_id: normalized_value}
        self.parameters: Dict[int, float] = {}
        self.parameter_info: Dict[int, VSTProgramParameter] = {}

        # Histórico de programas (presets)
        self.programs: Dict[str, VSTProgramState] = {}
        self.current_program: str = "default"

        # Metadados
        self.vst_version = "3.x"
        self.vendor = ""
        self.loaded = False
        self.error: Optional[str] = None

    def is_instrument(self) -> bool:
        """Retorna True se é um instrumento, False se é efeito"""
        return self.vst_type == VSTProgramType.INSTRUMENT

    def is_effect(self) -> bool:
        """Retorna True se é um efeito"""
        return self.vst_type == VSTProgramType.EFFECT

    def set_parameter(self, param_id: int, value: float) -> None:
        """
        Define um parâmetro (0.0 - 1.0 normalizado)
        Clamp automático para 0.0 - 1.0
        """
        clamped = max(0.0, min(1.0, value))
        self.parameters[param_id] = clamped

    def get_parameter(self, param_id: int) -> float:
        """Obtém valor normalizado do parâmetro"""
        return self.parameters.get(param_id, 0.0)

    def set_parameter_by_name(self, param_name: str, value: float) -> None:
        """Define parâmetro por nome (mais legível)"""
        for param_id, info in self.parameter_info.items():
            if info.name.lower() == param_name.lower():
                self.set_parameter(param_id, value)
                return
        raise KeyError(f"Parâmetro '{param_name}' não encontrado")

    def get_parameter_by_name(self, param_name: str) -> float:
        """Obtém valor do parâmetro por nome"""
        for param_id, info in self.parameter_info.items():
            if info.name.lower() == param_name.lower():
                return self.get_parameter(param_id)
        raise KeyError(f"Parâmetro '{param_name}' não encontrado")

    def save_program(self, name: str) -> None:
        """Salva snapshot do estado atual como programa"""
        program = VSTProgramState(
            name=name,
            parameters=self.parameters.copy(),
        )
        self.programs[name] = program

    def load_program(self, name: str) -> None:
        """Restaura programa anterior"""
        if name not in self.programs:
            raise KeyError(f"Programa '{name}' não encontrado")
        program = self.programs[name]
        self.parameters = program.parameters.copy()
        self.current_program = name

    def export_state(self) -> Dict[str, Any]:
        """Exporta estado completo (para salvar em JSON)"""
        return {
            "path": str(self.path),
            "name": self.name,
            "vst_type": self.vst_type.value,
            "vst_id": self.vst_id,
            "bypass": self.bypass,
            "parameters": self.parameters,
            "programs": {
                name: program.to_dict()
                for name, program in self.programs.items()
            },
            "current_program": self.current_program,
        }

    @classmethod
    def import_state(cls, data: Dict[str, Any]) -> VST:
        """Reconstrói VST a partir de estado exportado"""
        vst = cls(
            path=data["path"],
            name=data["name"],
            vst_type=VSTProgramType(data["vst_type"]),
            vst_id=data["vst_id"],
            bypass=data["bypass"],
        )
        vst.parameters = data.get("parameters", {})
        vst.programs = {
            name: VSTProgramState.from_dict(prog)
            for name, prog in data.get("programs", {}).items()
        }
        vst.current_program = data.get("current_program", "default")
        return vst

    def __repr__(self) -> str:
        status = "✓" if self.loaded else "✗"
        return (
            f"<VST {status} '{self.name}' ({self.vst_type.value}) "
            f"@ {self.path.name}>"
        )