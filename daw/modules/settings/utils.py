# modules/settings/utils.py
"""
Utilitários para o módulo Settings: salvar/carregar configurações,
validação de propriedades, etc.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


def get_config_dir() -> Path:
    """Retorna o diretório de configuração do addon."""
    # ~/.config/blender/<version>/scripts/addons/daw/config/
    blender_dir = Path(bpy.utils.script_paths()[0]).parent
    config_dir = blender_dir / "daw_config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file(name: str = "settings") -> Path:
    """Retorna o caminho de um arquivo de config."""
    return get_config_dir() / f"{name}.json"


def save_config(data: Dict[str, Any], filename: str = "settings") -> bool:
    """Salva configurações em um arquivo JSON.
    
    Args:
        data: Dicionário com as configurações
        filename: Nome do arquivo (sem extensão)
    
    Returns:
        True se sucesso, False caso contrário
    """
    try:
        config_file = get_config_file(filename)
        
        # Garante que o diretório existe
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Erro ao salvar config {filename}: {e}")
        return False


def load_config(filename: str = "settings") -> Dict[str, Any] | None:
    """Carrega configurações de um arquivo JSON.
    
    Args:
        filename: Nome do arquivo (sem extensão)
    
    Returns:
        Dicionário com as configurações, ou None se não existir
    """
    try:
        config_file = get_config_file(filename)
        
        if not config_file.exists():
            return None
        
        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data
    except Exception as e:
        print(f"Erro ao carregar config {filename}: {e}")
        return None


def delete_config(filename: str = "settings") -> bool:
    """Deleta um arquivo de config.
    
    Args:
        filename: Nome do arquivo (sem extensão)
    
    Returns:
        True se sucesso, False caso contrário
    """
    try:
        config_file = get_config_file(filename)
        
        if config_file.exists():
            config_file.unlink()
            return True
        
        return False
    except Exception as e:
        print(f"Erro ao deletar config {filename}: {e}")
        return False


def save_workspace_layout() -> bool:
    """Salva o layout atual do workspace."""
    try:
        # Obter informações do workspace atual
        workspace = bpy.context.window.workspace
        if not workspace:
            return False
        
        layout_data = {
            'workspace_name': workspace.name,
            'timestamp': __import__('time').time(),
        }
        
        return save_config(layout_data, "workspace_layout")
    except Exception as e:
        print(f"Erro ao salvar layout: {e}")
        return False


def load_workspace_layout() -> str | None:
    """Carrega o nome do último workspace salvo."""
    try:
        layout_data = load_config("workspace_layout")
        
        if layout_data and 'workspace_name' in layout_data:
            return layout_data['workspace_name']
        
        return None
    except Exception as e:
        print(f"Erro ao carregar layout: {e}")
        return None


# ============================================================================
# EXPORTAR/IMPORTAR PRESETS DE PREFERÊNCIAS
# ============================================================================

def export_preferences(filepath: str = None) -> bool:
    """Exporta as preferências atuais para um arquivo JSON.
    
    Args:
        filepath: Caminho completo do arquivo de exportação
    
    Returns:
        True se sucesso
    """
    try:
        if filepath is None:
            filepath = str(get_config_file("preferences_backup"))
        
        from .preferences import get_preferences
        prefs = get_preferences()
        
        export_data = {
            'audio': {
                'output_device': prefs.audio.output_device,
                'samplerate': prefs.audio.samplerate,
                'buffer_size': prefs.audio.buffer_size,
                'enable_dither': prefs.audio.enable_dither,
            },
            'ui': {
                'theme': prefs.ui.theme,
                'font_scale': prefs.ui.font_scale,
                'panel_width': prefs.ui.panel_width,
                'show_tooltips': prefs.ui.show_tooltips,
            },
            'workspace': {
                'auto_layout': prefs.workspace.auto_layout,
                'remember_last_project': prefs.workspace.remember_last_project,
                'autosave_interval': prefs.workspace.autosave_interval,
            },
        }
        
        return save_config(export_data, os.path.splitext(os.path.basename(filepath))[0])
    except Exception as e:
        print(f"Erro ao exportar preferências: {e}")
        return False


def import_preferences(filepath: str) -> bool:
    """Importa preferências de um arquivo JSON.
    
    Args:
        filepath: Caminho completo do arquivo de importação
    
    Returns:
        True se sucesso
    """
    try:
        if not os.path.exists(filepath):
            print(f"Arquivo não encontrado: {filepath}")
            return False
        
        with open(filepath, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        from .preferences import get_preferences
        prefs = get_preferences()
        
        # Audio
        if 'audio' in import_data:
            audio_data = import_data['audio']
            if 'output_device' in audio_data:
                prefs.audio.output_device = audio_data['output_device']
            if 'samplerate' in audio_data:
                prefs.audio.samplerate = audio_data['samplerate']
            if 'buffer_size' in audio_data:
                prefs.audio.buffer_size = audio_data['buffer_size']
            if 'enable_dither' in audio_data:
                prefs.audio.enable_dither = audio_data['enable_dither']
        
        # UI
        if 'ui' in import_data:
            ui_data = import_data['ui']
            if 'theme' in ui_data:
                prefs.ui.theme = ui_data['theme']
            if 'font_scale' in ui_data:
                prefs.ui.font_scale = ui_data['font_scale']
            if 'panel_width' in ui_data:
                prefs.ui.panel_width = ui_data['panel_width']
            if 'show_tooltips' in ui_data:
                prefs.ui.show_tooltips = ui_data['show_tooltips']
        
        # Workspace
        if 'workspace' in import_data:
            ws_data = import_data['workspace']
            if 'auto_layout' in ws_data:
                prefs.workspace.auto_layout = ws_data['auto_layout']
            if 'remember_last_project' in ws_data:
                prefs.workspace.remember_last_project = ws_data['remember_last_project']
            if 'autosave_interval' in ws_data:
                prefs.workspace.autosave_interval = ws_data['autosave_interval']
        
        return True
    except Exception as e:
        print(f"Erro ao importar preferências: {e}")
        return False


def validate_property_value(prop_name: str, value: Any) -> tuple[bool, str]:
    """Valida se um valor é adequado para uma propriedade.
    
    Args:
        prop_name: Nome da propriedade (ex: 'samplerate')
        value: Valor a validar
    
    Returns:
        (é_válido, mensagem_erro)
    """
    # Mappings de validação
    validators = {
        'samplerate': lambda v: (22050 <= v <= 192000, "Sample rate deve estar entre 22050 e 192000 Hz"),
        'buffer_size': lambda v: (64 <= v <= 4096 and (v & (v - 1)) == 0, "Buffer size deve ser potência de 2 entre 64 e 4096"),
        'font_scale': lambda v: (0.8 <= v <= 1.5, "Font scale deve estar entre 0.8 e 1.5"),
        'panel_width': lambda v: (200 <= v <= 600, "Panel width deve estar entre 200 e 600 px"),
        'autosave_interval': lambda v: (0 <= v <= 60, "Auto-save interval deve estar entre 0 e 60 minutos"),
    }
    
    if prop_name in validators:
        validator = validators[prop_name]
        try:
            is_valid, message = validator(value)
            return is_valid, message
        except Exception as e:
            return False, str(e)
    
    return True, ""


class ConfigSerializer:
    """Helper class para serializar/desserializar PropertyGroups."""
    
    @staticmethod
    def to_dict(prop_group) -> Dict[str, Any]:
        """Converte um PropertyGroup em dicionário."""
        result = {}
        for key in prop_group.keys():
            try:
                value = prop_group[key]
                # Skip PropertyGroups nested
                if not isinstance(value, type):
                    result[key] = value
            except Exception:
                pass
        return result
    
    @staticmethod
    def from_dict(prop_group, data: Dict[str, Any]) -> bool:
        """Aplica valores de um dicionário a um PropertyGroup."""
        try:
            for key, value in data.items():
                if hasattr(prop_group, key):
                    setattr(prop_group, key, value)
            return True
        except Exception as e:
            print(f"Erro ao deserializar PropertyGroup: {e}")
            return False


classes = []


def register():
    pass


def unregister():
    pass


# Necessário importar bpy aqui após definir get_config_dir
try:
    import bpy
except ImportError:
    pass  # Será importado em contexto