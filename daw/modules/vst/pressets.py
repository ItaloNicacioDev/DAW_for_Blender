# modules/vst/presets.py
"""
Gerenciador de presets de VST.

Presets embutidos: padrão para VSTs conhecidos
Presets do usuário: salvos em ~/.blender/extensions/blender_daw/vst_presets/

Arquivos JSON:
    presets/
        vendor/
            vst_name/
                preset_name.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import asdict

from .vst import VST, VSTProgramType, VSTProgramState


# ═══════════════════════════════════════════════════════════════
#  PRESETS EMBUTIDOS (para VSTs populares)
# ═══════════════════════════════════════════════════════════════

BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "default": {
        "name": "Default",
        "description": "Preset padrão",
        "parameters": {},
    },
    # Adicionar mais presets específicos conforme necessário
}


# ═══════════════════════════════════════════════════════════════
#  GERENCIADOR DE PRESETS
# ═══════════════════════════════════════════════════════════════

class VSTProgramPresetManager:
    """Gerencia presets de VST (embutidos + salvos pelo usuário)"""

    def __init__(self, user_preset_dir: Optional[Path] = None):
        """
        Args:
            user_preset_dir: Diretório de presets do usuário.
                            Se None, usa ~/.blender/extensions/blender_daw/vst_presets/
        """
        if user_preset_dir is None:
            # Diretório padrão
            blender_config = Path.home() / ".blender"
            user_preset_dir = blender_config / "extensions" / "blender_daw" / "vst_presets"

        self.user_preset_dir = user_preset_dir
        self.user_preset_dir.mkdir(parents=True, exist_ok=True)

        # Cache de presets carregados
        self._preset_cache: Dict[str, Dict[str, Any]] = {}

    def get_preset_path(
        self,
        vst_name: str,
        vendor: str = "user",
        preset_name: str = "default",
    ) -> Path:
        """Retorna caminho do arquivo de preset"""
        return (
            self.user_preset_dir
            / vendor
            / vst_name
            / f"{preset_name}.json"
        )

    def save_preset(
        self,
        vst: VST,
        preset_name: str,
        vendor: str = "user",
        description: str = "",
    ) -> bool:
        """
        Salva preset do VST atual.

        Args:
            vst: Modelo VST com estado atual
            preset_name: Nome do preset
            vendor: Namespace (padrão "user")
            description: Descrição do preset

        Returns:
            True se salvo com sucesso
        """
        try:
            preset_path = self.get_preset_path(vst.name, vendor, preset_name)
            preset_path.parent.mkdir(parents=True, exist_ok=True)

            preset_data = {
                "name": preset_name,
                "vst_name": vst.name,
                "vst_type": vst.vst_type.value,
                "vendor": vendor,
                "description": description,
                "parameters": vst.parameters,
                "timestamp": 0,
            }

            with open(preset_path, "w") as f:
                json.dump(preset_data, f, indent=2)

            return True

        except Exception as e:
            print(f"[VST Presets] Erro ao salvar preset: {e}")
            return False

    def load_preset(
        self,
        vst: VST,
        preset_name: str,
        vendor: str = "user",
    ) -> bool:
        """
        Carrega preset e aplica ao VST.

        Args:
            vst: Modelo VST (será modificado)
            preset_name: Nome do preset
            vendor: Namespace

        Returns:
            True se carregado com sucesso
        """
        try:
            preset_path = self.get_preset_path(vst.name, vendor, preset_name)

            if not preset_path.exists():
                print(f"[VST Presets] Preset não encontrado: {preset_path}")
                return False

            with open(preset_path, "r") as f:
                preset_data = json.load(f)

            # Restaurar parâmetros
            vst.parameters = preset_data.get("parameters", {})

            return True

        except Exception as e:
            print(f"[VST Presets] Erro ao carregar preset: {e}")
            return False

    def list_presets(
        self,
        vst_name: str,
        vendor: str = "user",
    ) -> List[str]:
        """
        Lista presets disponíveis para um VST.

        Args:
            vst_name: Nome do VST
            vendor: Namespace

        Returns:
            Lista de nomes de presets
        """
        vendor_dir = self.user_preset_dir / vendor / vst_name

        if not vendor_dir.exists():
            return []

        presets = [
            p.stem
            for p in vendor_dir.glob("*.json")
        ]

        return sorted(presets)

    def list_all_presets(self, vst_name: str) -> Dict[str, List[str]]:
        """
        Lista presets de todos os vendors.

        Returns:
            Dict[vendor, lista de presets]
        """
        all_presets = {}

        # Presets embutidos
        if vst_name in BUILTIN_PRESETS:
            all_presets["builtin"] = [vst_name]

        # Presets do usuário
        for vendor_dir in self.user_preset_dir.iterdir():
            if vendor_dir.is_dir():
                vst_dir = vendor_dir / vst_name
                if vst_dir.exists():
                    presets = self.list_presets(vst_name, vendor_dir.name)
                    if presets:
                        all_presets[vendor_dir.name] = presets

        return all_presets

    def delete_preset(
        self,
        vst_name: str,
        preset_name: str,
        vendor: str = "user",
    ) -> bool:
        """Deleta um preset"""
        try:
            preset_path = self.get_preset_path(vst_name, vendor, preset_name)
            if preset_path.exists():
                preset_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"[VST Presets] Erro ao deletar preset: {e}")
            return False

    def get_builtin_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """Obtém preset embutido"""
        return BUILTIN_PRESETS.get(name)

    def export_preset_library(self, output_path: Path) -> bool:
        """Exporta todos os presets do usuário como zip"""
        try:
            import zipfile

            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for preset_file in self.user_preset_dir.rglob("*.json"):
                    arcname = preset_file.relative_to(self.user_preset_dir)
                    zf.write(preset_file, arcname)

            return True
        except Exception as e:
            print(f"[VST Presets] Erro ao exportar: {e}")
            return False

    def import_preset_library(self, zip_path: Path) -> bool:
        """Importa biblioteca de presets de um zip"""
        try:
            import zipfile

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(self.user_preset_dir)

            return True
        except Exception as e:
            print(f"[VST Presets] Erro ao importar: {e}")
            return False

    def __repr__(self) -> str:
        return f"<VSTProgramPresetManager @ {self.user_preset_dir}>"


# Instância global
_preset_manager: Optional[VSTProgramPresetManager] = None


def get_preset_manager() -> VSTProgramPresetManager:
    """Retorna gerenciador global de presets"""
    global _preset_manager
    if _preset_manager is None:
        _preset_manager = VSTProgramPresetManager()
    return _preset_manager