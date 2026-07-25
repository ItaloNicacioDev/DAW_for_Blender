# modules/settings/operators.py
"""
Operadores Blender para gerenciamento de settings:
reset, salvar/carregar presets, export/import, etc.
"""
from __future__ import annotations

import bpy
from bpy.types import Operator, OperatorFileListElement
from bpy.props import StringProperty

from . import utils
from .preferences import get_preferences
from .shortcuts import reset_keymaps_to_default
from .themes import get_theme_by_preferences


class SETTINGS_OT_ResetToDefault(Operator):
    """Reseta todas as configurações para valores padrão."""
    bl_idname = "settings.reset_to_default"
    bl_label = "Resetar para Padrão"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            prefs = get_preferences()
            
            # Audio
            prefs.audio.output_device = "Default"
            prefs.audio.samplerate = 48000
            prefs.audio.buffer_size = 512
            prefs.audio.enable_dither = False
            
            # UI
            prefs.ui.theme = 'DARK'
            prefs.ui.font_scale = 1.0
            prefs.ui.panel_width = 300
            prefs.ui.show_tooltips = True
            prefs.ui.show_playhead_indicator = True
            
            # Workspace
            prefs.workspace.auto_layout = True
            prefs.workspace.remember_last_project = True
            prefs.workspace.autosave_interval = 5
            
            # Keymaps
            reset_keymaps_to_default()
            
            self.report({'INFO'}, "Configurações resetadas para padrão")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Erro ao resetar: {str(e)}")
            return {'CANCELLED'}


class SETTINGS_OT_SavePreset(Operator):
    """Salva as preferências atuais como preset."""
    bl_idname = "settings.save_preset"
    bl_label = "Salvar Preset"
    bl_options = {'REGISTER'}

    preset_name: StringProperty(
        name="Nome do Preset",
        description="Nome para identificar este preset",
        default="Meu Preset"
    )

    def execute(self, context):
        try:
            prefs = get_preferences()
            
            preset_data = {
                'name': self.preset_name,
                'audio': utils.ConfigSerializer.to_dict(prefs.audio),
                'ui': utils.ConfigSerializer.to_dict(prefs.ui),
                'workspace': utils.ConfigSerializer.to_dict(prefs.workspace),
            }
            
            filename = f"preset_{self.preset_name.replace(' ', '_').lower()}"
            if utils.save_config(preset_data, filename):
                self.report({'INFO'}, f"Preset '{self.preset_name}' salvo")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Erro ao salvar preset")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class SETTINGS_OT_LoadPreset(Operator):
    """Carrega um preset salvo."""
    bl_idname = "settings.load_preset"
    bl_label = "Carregar Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset_name: StringProperty(
        name="Nome do Preset",
        default="Meu Preset"
    )

    def execute(self, context):
        try:
            filename = f"preset_{self.preset_name.replace(' ', '_').lower()}"
            preset_data = utils.load_config(filename)
            
            if not preset_data:
                self.report({'ERROR'}, f"Preset '{self.preset_name}' não encontrado")
                return {'CANCELLED'}
            
            prefs = get_preferences()
            
            # Restaura configurações
            if 'audio' in preset_data:
                utils.ConfigSerializer.from_dict(prefs.audio, preset_data['audio'])
            if 'ui' in preset_data:
                utils.ConfigSerializer.from_dict(prefs.ui, preset_data['ui'])
            if 'workspace' in preset_data:
                utils.ConfigSerializer.from_dict(prefs.workspace, preset_data['workspace'])
            
            self.report({'INFO'}, f"Preset '{self.preset_name}' carregado")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class SETTINGS_OT_ExportSettings(Operator):
    """Exporta as configurações para um arquivo JSON."""
    bl_idname = "settings.export_settings"
    bl_label = "Exportar Configurações"
    bl_options = {'REGISTER'}

    filepath: StringProperty(
        name="Caminho do Arquivo",
        subtype='FILE_PATH',
    )
    
    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'}
    )

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "Nenhum arquivo selecionado")
            return {'CANCELLED'}
        
        if utils.export_preferences(self.filepath):
            self.report({'INFO'}, f"Configurações exportadas para {self.filepath}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Erro ao exportar configurações")
            return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class SETTINGS_OT_ImportSettings(Operator):
    """Importa configurações de um arquivo JSON."""
    bl_idname = "settings.import_settings"
    bl_label = "Importar Configurações"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(
        name="Caminho do Arquivo",
        subtype='FILE_PATH',
    )
    
    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'}
    )

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "Nenhum arquivo selecionado")
            return {'CANCELLED'}
        
        if utils.import_preferences(self.filepath):
            self.report({'INFO'}, f"Configurações importadas de {self.filepath}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Erro ao importar configurações")
            return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class SETTINGS_OT_RefreshTheme(Operator):
    """Recarrega o tema visual."""
    bl_idname = "settings.refresh_theme"
    bl_label = "Atualizar Tema"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            theme = get_theme_by_preferences()
            # Trigger UI redraw
            for area in context.screen.areas:
                area.tag_redraw()
            
            self.report({'INFO'}, "Tema atualizado")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class SETTINGS_OT_OpenConfigFolder(Operator):
    """Abre a pasta de configuração do addon."""
    bl_idname = "settings.open_config_folder"
    bl_label = "Abrir Pasta de Config"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            import subprocess
            import sys
            
            config_dir = utils.get_config_dir()
            
            if sys.platform == 'win32':
                subprocess.Popen(['explorer', str(config_dir)])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(config_dir)])
            else:  # Linux
                subprocess.Popen(['xdg-open', str(config_dir)])
            
            self.report({'INFO'}, f"Pasta aberta: {config_dir}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class SETTINGS_OT_ValidateSetting(Operator):
    """Valida um valor de configuração específico."""
    bl_idname = "settings.validate_setting"
    bl_label = "Validar Configuração"
    bl_options = {'REGISTER'}

    property_name: StringProperty(name="Propriedade")
    test_value: StringProperty(name="Valor a Testar")

    def execute(self, context):
        try:
            # Converte valor para tipo apropriado
            try:
                if self.property_name in ['samplerate', 'buffer_size', 'panel_width', 'autosave_interval']:
                    value = int(self.test_value)
                elif self.property_name == 'font_scale':
                    value = float(self.test_value)
                else:
                    value = self.test_value
            except ValueError:
                self.report({'ERROR'}, "Tipo de valor inválido")
                return {'CANCELLED'}
            
            is_valid, message = utils.validate_property_value(self.property_name, value)
            
            if is_valid:
                self.report({'INFO'}, f"✓ Valor válido para {self.property_name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"✗ {message}")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


classes = [
    SETTINGS_OT_ResetToDefault,
    SETTINGS_OT_SavePreset,
    SETTINGS_OT_LoadPreset,
    SETTINGS_OT_ExportSettings,
    SETTINGS_OT_ImportSettings,
    SETTINGS_OT_RefreshTheme,
    SETTINGS_OT_OpenConfigFolder,
    SETTINGS_OT_ValidateSetting,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)