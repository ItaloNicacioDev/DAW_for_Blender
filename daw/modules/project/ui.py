# modules/project/ui.py
"""
Painéis de UI do Blender para o módulo Project.

Segue o padrão:
    - bl_space_type = 'SEQUENCE_EDITOR'
    - bl_category   = "DAW"
"""
from __future__ import annotations

import bpy
from bpy.types import Menu, Panel

from .templates import get_builtin_template_names, list_user_templates


# ---------------------------------------------------------------------- #
# Menus
# ---------------------------------------------------------------------- #
class DAW_MT_ProjectFile(Menu):
    """Menu de arquivo do projeto."""
    bl_idname = "DAW_MT_project_file"
    bl_label = "Arquivo"

    def draw(self, context):
        layout = self.layout
        layout.operator("daw.project_new", text="Novo", icon='FILE_NEW')
        layout.operator("daw.project_open", text="Abrir...", icon='FILE_FOLDER')
        layout.separator()
        layout.operator("daw.project_save", text="Salvar", icon='FILE_TICK')
        layout.operator("daw.project_save_as", text="Salvar Como...", icon='SAVE_AS')
        layout.separator()
        layout.operator("daw.project_export", text="Exportar...", icon='EXPORT')
        layout.operator("daw.project_import", text="Importar...", icon='IMPORT')


class DAW_MT_ProjectTemplates(Menu):
    """Menu de templates."""
    bl_idname = "DAW_MT_project_templates"
    bl_label = "Templates"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Embutidos:")
        for name in get_builtin_template_names():
            op = layout.operator("daw.project_apply_template", text=name.title())
            op.template_name = name

        user_templates = list_user_templates()
        if user_templates:
            layout.separator()
            layout.label(text="Do Usuário:")
            for name in user_templates:
                op = layout.operator("daw.project_apply_template", text=name)
                op.template_name = name

        layout.separator()
        layout.operator("daw.project_save_template", text="Salvar Atual como Template...", icon='ADD')


class DAW_MT_ProjectBackup(Menu):
    """Menu de backup."""
    bl_idname = "DAW_MT_project_backup"
    bl_label = "Backup"

    def draw(self, context):
        layout = self.layout
        layout.operator("daw.project_backup", text="Criar Backup Agora", icon='FILE_BACKUP')
        layout.operator("daw.project_restore_backup", text="Restaurar Backup...", icon='RECOVER_LAST')
        layout.separator()
        proj = context.scene.daw_project
        layout.prop(proj.settings, "autosave_enabled", text="Autosave")
        if proj.settings.autosave_enabled:
            layout.prop(proj.settings, "autosave_interval")
        layout.operator("daw.project_toggle_autosave", text="Alternar Autosave")


# ---------------------------------------------------------------------- #
# Painéis
# ---------------------------------------------------------------------- #
class DAW_PT_Project(Panel):
    bl_label = "Projeto"
    bl_idname = "DAW_PT_project"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        proj = context.scene.daw_project

        # Nome do projeto
        box = layout.box()
        row = box.row()
        row.label(text="Projeto:", icon='FILE_BLEND')
        row.label(text=proj.display_name)
        if proj.is_modified:
            row.label(text="*", icon='DOT')

        # Arquivo
        if proj.filepath:
            box.label(text=proj.filepath, icon='FILEBROWSER')

        # Menu de arquivo
        row = layout.row(align=True)
        row.menu("DAW_MT_project_file", text="Arquivo", icon='FILEBROWSER')
        row.menu("DAW_MT_project_templates", text="Templates", icon='PRESET')
        row.menu("DAW_MT_project_backup", text="Backup", icon='FILE_BACKUP')


class DAW_PT_ProjectSettings(Panel):
    bl_label = "Configurações"
    bl_idname = "DAW_PT_project_settings"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_parent_id = "DAW_PT_project"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        proj = context.scene.daw_project
        settings = proj.settings

        box = layout.box()
        box.label(text="Autosave", icon='TIME')
        box.prop(settings, "autosave_enabled")
        if settings.autosave_enabled:
            box.prop(settings, "autosave_interval")
        box.prop(settings, "max_backups")

        box = layout.box()
        box.label(text="Padrões", icon='SETTINGS')
        box.prop(settings, "default_bpm")
        row = box.row(align=True)
        row.prop(settings, "default_time_signature_num")
        row.prop(settings, "default_time_signature_den")


classes = [
    DAW_MT_ProjectFile,
    DAW_MT_ProjectTemplates,
    DAW_MT_ProjectBackup,
    DAW_PT_Project,
    DAW_PT_ProjectSettings,
]