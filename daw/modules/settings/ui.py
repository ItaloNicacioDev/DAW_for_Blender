# modules/settings/ui.py
"""
Painéis de interface (Preferences UI) para o addon DAW Settings.

Exibe e permite edição das preferências diretamente em Preferences → Addons.
"""
from __future__ import annotations

import bpy
from bpy.types import Panel, UIList


class SETTINGS_PT_PreferencesHeader(Panel):
    """Painel header das preferências do addon."""
    bl_label = "DAW Settings"
    bl_idname = "SETTINGS_PT_preferences_header"
    bl_space_type = 'PREFERENCES'
    bl_region_type = 'WINDOW'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.preferences.addons.get("daw") is not None

    def draw_header(self, context):
        layout = self.layout
        layout.label(text="🎛️ DAW Configuration Panel", icon='PREFERENCES')

    def draw(self, context):
        layout = self.layout
        layout.label(text="Configure o addon DAW nos painéis abaixo")


class SETTINGS_PT_Audio(Panel):
    """Painel de configurações de áudio."""
    bl_label = "Áudio"
    bl_idname = "SETTINGS_PT_audio"
    bl_space_type = 'PREFERENCES'
    bl_region_type = 'WINDOW'
    bl_parent_id = "SETTINGS_PT_preferences_header"

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons.get("daw")
        return addon_prefs is not None

    def draw(self, context):
        layout = self.layout
        addon_prefs = context.preferences.addons["daw"].preferences

        audio_prefs = addon_prefs.audio

        box = layout.box()
        box.label(text="Dispositivo e Taxa", icon='SPEAKER')

        col = box.column(align=True)
        col.prop(audio_prefs, "output_device", text="Dispositivo de Saída")
        col.prop(audio_prefs, "samplerate", text="Sample Rate (Hz)")

        box = layout.box()
        box.label(text="Buffer", icon='FCURVE')

        col = box.column(align=True)
        col.prop(audio_prefs, "buffer_size", text="Tamanho do Buffer")
        col.prop(audio_prefs, "enable_dither", text="Ativar Dither")

        # Info de latência aproximada
        buffer_ms = (audio_prefs.buffer_size / audio_prefs.samplerate) * 1000
        box_info = layout.box()
        box_info.label(text=f"Latência aproximada: {buffer_ms:.1f} ms", icon='INFO')


class SETTINGS_PT_UI(Panel):
    """Painel de configurações de interface."""
    bl_label = "Interface (UI)"
    bl_idname = "SETTINGS_PT_ui"
    bl_space_type = 'PREFERENCES'
    bl_region_type = 'WINDOW'
    bl_parent_id = "SETTINGS_PT_preferences_header"

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons.get("daw")
        return addon_prefs is not None

    def draw(self, context):
        layout = self.layout
        addon_prefs = context.preferences.addons["daw"].preferences

        ui_prefs = addon_prefs.ui

        # === Tema ===
        box = layout.box()
        box.label(text="Tema Visual", icon='COLOR')

        row = box.row()
        row.prop(ui_prefs, "theme", text="Tema")

        if ui_prefs.theme == 'DARK':
            box_info = layout.box()
            box_info.label(text="Tema escuro com cores neon", icon='INFO')
        elif ui_prefs.theme == 'LIGHT':
            box_info = layout.box()
            box_info.label(text="Tema claro minimalista", icon='INFO')

        # === Escalas e Tamanhos ===
        box = layout.box()
        box.label(text="Escalas e Tamanhos", icon='PREFERENCES')

        col = box.column(align=True)
        col.prop(ui_prefs, "font_scale", text="Escala de Fonte")
        col.prop(ui_prefs, "panel_width", text="Largura do Painel (px)")

        # === Indicadores Visuais ===
        box = layout.box()
        box.label(text="Indicadores", icon='RESTRICT_VIEW_OFF')

        col = box.column()
        col.prop(ui_prefs, "show_tooltips", text="Mostrar Tooltips")
        col.prop(ui_prefs, "show_playhead_indicator", text="Indicador de Playhead")

        # Botão de atualizar tema
        row = layout.row()
        row.operator("settings.refresh_theme", text="Atualizar Tema Agora", icon='FILE_REFRESH')


class SETTINGS_PT_Workspace(Panel):
    """Painel de configurações de workspace."""
    bl_label = "Workspace"
    bl_idname = "SETTINGS_PT_workspace"
    bl_space_type = 'PREFERENCES'
    bl_region_type = 'WINDOW'
    bl_parent_id = "SETTINGS_PT_preferences_header"

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons.get("daw")
        return addon_prefs is not None

    def draw(self, context):
        layout = self.layout
        addon_prefs = context.preferences.addons["daw"].preferences

        workspace_prefs = addon_prefs.workspace

        box = layout.box()
        box.label(text="Layout", icon='WORKSPACE')

        col = box.column()
        col.prop(workspace_prefs, "auto_layout", text="Reorganizar Automaticamente")

        box = layout.box()
        box.label(text="Projeto", icon='FILE')

        col = box.column()
        col.prop(workspace_prefs, "remember_last_project", text="Lembrar Último Projeto")

        box = layout.box()
        box.label(text="Auto-Save", icon='FILE_BACKUP')

        col = box.column(align=True)
        col.prop(workspace_prefs, "autosave_interval", text="Intervalo (minutos)")
        if workspace_prefs.autosave_interval == 0:
            col.label(text="Auto-save desativado", icon='INFO')


class SETTINGS_PT_Keymaps(Panel):
    """Painel de gerenciamento de atalhos de teclado."""
    bl_label = "Atalhos de Teclado"
    bl_idname = "SETTINGS_PT_keymaps"
    bl_space_type = 'PREFERENCES'
    bl_region_type = 'WINDOW'
    bl_parent_id = "SETTINGS_PT_preferences_header"

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons.get("daw")
        return addon_prefs is not None

    def draw(self, context):
        layout = self.layout
        addon_prefs = context.preferences.addons["daw"].preferences

        keymap_prefs = addon_prefs.keymaps

        box = layout.box()
        box.label(text="Atalhos Padrão", icon='ANIM')

        col = box.column(align=True)
        col.label(text="Playback:", icon='PLAY')
        col.label(text=f"  Play/Pause: {keymap_prefs.play_pause}")
        col.label(text=f"  Stop: {keymap_prefs.stop}")
        col.label(text=f"  Record: {keymap_prefs.record}")

        col.separator()
        col.label(text="Edição:", icon='GREASEPENCIL')
        col.label(text=f"  Undo: {keymap_prefs.undo}")
        col.label(text=f"  Redo: {keymap_prefs.redo}")

        row = layout.row(align=True)
        row.label(text="Para customizar atalhos, acesse:")
        row = layout.row()
        row.label(text="Edit → Preferences → Keymaps → Search 'DAW'", icon='INFO')


class SETTINGS_PT_Advanced(Panel):
    """Painel de configurações avançadas."""
    bl_label = "Avançado"
    bl_idname = "SETTINGS_PT_advanced"
    bl_space_type = 'PREFERENCES'
    bl_region_type = 'WINDOW'
    bl_parent_id = "SETTINGS_PT_preferences_header"

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons.get("daw")
        return addon_prefs is not None

    def draw(self, context):
        layout = self.layout
        addon_prefs = context.preferences.addons["daw"].preferences

        box = layout.box()
        box.label(text="Debug e Manutenção", icon='CONSOLE')

        col = box.column()
        col.prop(addon_prefs, "debug_mode", text="Modo Debug")
        col.prop(addon_prefs, "check_for_updates", text="Verificar Atualizações")

        box = layout.box()
        box.label(text="Ações", icon='TOOL_SETTINGS')

        col = box.column(align=True)
        col.operator("settings.reset_to_default", text="Resetar para Padrão", icon='CANCEL')
        col.operator("settings.open_config_folder", text="Abrir Pasta de Config", icon='FILE_FOLDER')

        col.separator()
        col.operator("settings.export_settings", text="Exportar Configurações", icon='EXPORT')
        col.operator("settings.import_settings", text="Importar Configurações", icon='IMPORT')


class SETTINGS_PT_Updates(Panel):
    """Painel de verificação e instalação de atualizações via GitHub."""
    bl_label = "Atualizações"
    bl_idname = "SETTINGS_PT_updates"
    bl_space_type = 'PREFERENCES'
    bl_region_type = 'WINDOW'
    bl_parent_id = "SETTINGS_PT_preferences_header"

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons.get("daw")
        return addon_prefs is not None

    def draw(self, context):
        try:
            from ..updater.ui import draw_updater_full
            draw_updater_full(self.layout, context)
        except Exception as e:
            self.layout.label(text=f"Updater indisponível: {e}", icon='ERROR')


class SETTINGS_PT_About(Panel):
    """Painel com informações sobre o addon."""
    bl_label = "Sobre"
    bl_idname = "SETTINGS_PT_about"
    bl_space_type = 'PREFERENCES'
    bl_region_type = 'WINDOW'
    bl_parent_id = "SETTINGS_PT_preferences_header"

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons.get("daw")
        return addon_prefs is not None

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="DAW Addon for Blender", icon='BLENDER')

        col = box.column(align=True)
        col.label(text="Versão: 1.0.0")
        col.label(text="Autor: ItaloNicacio (GeckoLabs)")
        col.label(text="Categoria: Audio")

        col.separator()
        col.label(text="Um sintetizador e DAW integrado ao Blender")
        col.label(text="com suporte a samples, sequenciação e efeitos.")

        col.separator()
        col.label(text="GitHub: ItaloNicacioDev", icon='INTERNET')


classes = [
    SETTINGS_PT_PreferencesHeader,
    SETTINGS_PT_Audio,
    SETTINGS_PT_UI,
    SETTINGS_PT_Workspace,
    SETTINGS_PT_Keymaps,
    SETTINGS_PT_Advanced,
    SETTINGS_PT_Updates,
    SETTINGS_PT_About,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)