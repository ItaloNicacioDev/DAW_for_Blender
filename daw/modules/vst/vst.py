# modules/vst/vst.py
"""
Modelo puro de um plugin VST (efeito ou instrumento).

Responsabilidades:
    - Representar um VST carregado com seus parâmetros
    - Armazenar path do VST, tipo (effect/instrument), bypass, presets
    - Expor interface de get/set de parâmetros por ID ou nome
    - SEM dependência de bpy (portável para motor C++/audio)

Processamento real: delegado a DawdreamerIPCBridge (ipc_engine.py)
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
        self.plugin_format: str = "UNKNOWN"  # "VST2" | "VST3" | "UNKNOWN"

        # Ponte para o motor real de processamento (dawdreamer).
        # None enquanto não carregado. Ver modules/vst/engine.py.
        self.bridge = None

    # ------------------------------------------------------------------
    # Ciclo de vida (carregamento real via dawdreamer)
    # ------------------------------------------------------------------
    def load(self, sample_rate: int = 44100, block_size: int = 512) -> bool:
        """
        Carrega o plugin de verdade através do worker IPC (ipc_engine.py).

        Detecta automaticamente VST2 x VST3 pela extensão do arquivo e
        escolhe o modo de processamento certo (efeito ou instrumento MIDI)
        de acordo com `self.vst_type` — o usuário não precisa informar,
        cada VST é tratado conforme seu próprio tipo.

        Retorna True em caso de sucesso. Em caso de erro, `self.error` é
        preenchido e `self.loaded` permanece False.
        """
        from .engine import detect_plugin_format
        from .ipc_engine import DawdreamerIPCBridge, is_available, install_instructions

        self.error = None
        self.plugin_format = detect_plugin_format(self.path)

        if not is_available():
            self.error = install_instructions()
            self.loaded = False
            return False

        try:
            bridge = DawdreamerIPCBridge(sample_rate=sample_rate, block_size=block_size)
            bridge.load(self.path, self.vst_type)
            self.bridge = bridge
            self._refresh_parameters_from_bridge()
            self.loaded = True
            return True
        except Exception as e:
            self.error = str(e)
            self.loaded = False
            self.bridge = None
            return False

    def unload(self) -> None:
        """Libera o plugin e o motor associado."""
        if self.bridge is not None:
            try:
                self.bridge.unload()
            except Exception:
                pass
        self.bridge = None
        self.loaded = False

    def _refresh_parameters_from_bridge(self) -> None:
        """Preenche parameter_info/parameters a partir do plugin real carregado."""
        if self.bridge is None:
            return
        self.parameter_info.clear()
        self.parameters.clear()
        for param in self.bridge.list_parameters():
            self.parameter_info[param.id] = param
            self.parameters[param.id] = param.value

    # ------------------------------------------------------------------
    # Processamento real (delegado ao bridge)
    # ------------------------------------------------------------------
    def process_effect(self, audio):
        """
        Processa um buffer de áudio (numpy array estéreo) através deste VST,
        desde que seja um efeito e esteja carregado. Aplica bypass e os
        valores atuais de `self.parameters` antes de processar.
        """
        if self.bridge is None or not self.loaded:
            raise RuntimeError(f"VST '{self.name}' não está carregado")
        if self.bypass:
            return audio
        self._push_parameters_to_bridge()
        return self.bridge.process_effect(audio)

    def render_instrument(self, midi_notes, duration: float):
        """
        Renderiza este VST instrumento a partir de uma lista de notas MIDI:
        [(pitch, start_seconds, duration_seconds, velocity), ...]
        """
        if self.bridge is None or not self.loaded:
            raise RuntimeError(f"VST '{self.name}' não está carregado")
        self._push_parameters_to_bridge()
        return self.bridge.render_instrument(midi_notes, duration)

    def _push_parameters_to_bridge(self) -> None:
        if self.bridge is None:
            return
        for param_id, value in self.parameters.items():
            try:
                self.bridge.set_parameter(param_id, value)
            except Exception:
                pass

    def open_editor(self) -> bool:
        """
        Abre a janela nativa (GUI) do plugin, se ele suportar. Não
        bloqueia o Blender -- o worker roda isso numa thread separada
        e responde na hora.
        """
        if self.bridge is None or not self.loaded:
            return False
        return self.bridge.open_editor()

    def is_editor_open(self) -> bool:
        if self.bridge is None or not self.loaded:
            return False
        return self.bridge.is_editor_open()

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