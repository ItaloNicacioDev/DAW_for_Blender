# modules/project/operators.py
"""
Operators do Blender para o módulo Project.

Responsabilidade:
    Ações de gerenciamento de projeto: novo, abrir, salvar, salvar como,
    exportar, importar, backup, e aplicar templates.
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import Operator

from .save import save_project
from .load import load_project
from .backup import create_backup, restore_backup
from .autosave import start_autosave, stop_autosave
from .templates import apply_template, apply_user_template, save_user_template, list_user_templates
from .utils import ensure_extension, is_valid_project_file, get_default_project_dir


def _proj(context):
    return context.scene.daw_project


# ---------------------------------------------------------------------- #
# Novo projeto
# ---------------------------------------------------------------------- #
class DAW_OT_ProjectNew(Operator):
    bl_idname = "daw.project_new"
    bl_label = "Novo Projeto"
    bl_description = "Cria um novo projeto (descarta o atual)"
    bl_options = {'REGISTER', 'UNDO'}

    template: StringProperty(default="empty")
    confirm: BoolProperty(default=False)

    def execute(self, context):
        scene = context.scene
        proj = _proj(scene)

        # Aplica o template
        if not apply_template(scene, self.template):
            self.report({'ERROR'}, f"Template '{self.template}' não encontrado")
            return {'CANCELLED'}

        proj.name = "Untitled"
        proj.filepath = ""
        proj.is_modified = False
        scene.daw_project_name = "Untitled"

        self.report({'INFO'}, f"Novo projeto criado ({self.template})")
        return {'FINISHED'}

    def invoke(self, context, event):
        if not self.confirm:
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def draw(self, context):
        self.layout.label(text="Criar novo projeto? O atual será perdido.")
        self.layout.prop(self, "template")


# ---------------------------------------------------------------------- #
# Abrir projeto
# ---------------------------------------------------------------------- #
class DAW_OT_ProjectOpen(Operator):
    bl_idname = "daw.project_open"
    bl_label = "Abrir Projeto"
    bl_description = "Abre um projeto existente"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        if not self.filepath or not is_valid_project_file(self.filepath):
            self.report({'ERROR'}, "Arquivo de projeto inválido")
            return {'CANCELLED'}

        if load_project(self.filepath, context.scene):
            proj = _proj(context)
            proj.filepath = self.filepath
            proj.is_modified = False
            context.scene.daw_project_name = proj.display_name
            self.report({'INFO'}, f"Projeto '{proj.display_name}' aberto")
            return {'FINISHED'}

        self.report({'ERROR'}, "Falha ao carregar o projeto")
        return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# ---------------------------------------------------------------------- #
# Salvar projeto
# ---------------------------------------------------------------------- #
class DAW_OT_ProjectSave(Operator):
    bl_idname = "daw.project_save"
    bl_label = "Salvar"
    bl_description = "Salva o projeto atual"
    bl_options = {'REGISTER'}

    def execute(self, context):
        proj = _proj(context)
        if not proj.has_filepath:
            # Se não tem caminho, abre "Salvar Como"
            bpy.ops.daw.project_save_as('INVOKE_DEFAULT')
            return {'FINISHED'}

        if save_project(proj.filepath, context.scene):
            proj.is_modified = False
            self.report({'INFO'}, f"Projeto salvo: {proj.display_name}")
            return {'FINISHED'}

        self.report({'ERROR'}, "Falha ao salvar o projeto")
        return {'CANCELLED'}


class DAW_OT_ProjectSaveAs(Operator):
    bl_idname = "daw.project_save_as"
    bl_label = "Salvar Como..."
    bl_description = "Salva o projeto com um novo nome"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "Nenhum caminho especificado")
            return {'CANCELLED'}

        filepath = ensure_extension(self.filepath)
        if save_project(filepath, context.scene):
            proj = _proj(context)
            proj.filepath = filepath
            proj.name = proj.display_name
            proj.is_modified = False
            context.scene.daw_project_name = proj.display_name
            self.report({'INFO'}, f"Projeto salvo: {proj.display_name}")
            return {'FINISHED'}

        self.report({'ERROR'}, "Falha ao salvar o projeto")
        return {'CANCELLED'}

    def invoke(self, context, event):
        proj = _proj(context)
        if proj.has_filepath:
            self.filepath = proj.filepath
        else:
            self.filepath = str(get_default_project_dir() / f"{proj.name}.dawproj")
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# ---------------------------------------------------------------------- #
# Backup
# ---------------------------------------------------------------------- #
class DAW_OT_ProjectBackup(Operator):
    bl_idname = "daw.project_backup"
    bl_label = "Criar Backup"
    bl_description = "Cria um backup manual do projeto atual"
    bl_options = {'REGISTER'}

    def execute(self, context):
        proj = _proj(context)
        filepath = create_backup(context.scene, proj.display_name)
        if filepath:
            self.report({'INFO'}, f"Backup criado: {filepath}")
            return {'FINISHED'}
        self.report({'ERROR'}, "Falha ao criar backup")
        return {'CANCELLED'}


class DAW_OT_ProjectRestoreBackup(Operator):
    bl_idname = "daw.project_restore_backup"
    bl_label = "Restaurar Backup"
    bl_description = "Restaura um backup anterior"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        if restore_backup(self.filepath, context.scene):
            self.report({'INFO'}, "Backup restaurado")
            return {'FINISHED'}
        self.report({'ERROR'}, "Falha ao restaurar backup")
        return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# ---------------------------------------------------------------------- #
# Autosave
# ---------------------------------------------------------------------- #
class DAW_OT_ProjectToggleAutosave(Operator):
    bl_idname = "daw.project_toggle_autosave"
    bl_label = "Autosave"
    bl_description = "Ativa/desativa o autosave automático"
    bl_options = {'REGISTER'}

    def execute(self, context):
        settings = _proj(context).settings
        settings.autosave_enabled = not settings.autosave_enabled
        if settings.autosave_enabled:
            start_autosave()
            self.report({'INFO'}, "Autosave ativado")
        else:
            stop_autosave()
            self.report({'INFO'}, "Autosave desativado")
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Templates
# ---------------------------------------------------------------------- #
class DAW_OT_ProjectApplyTemplate(Operator):
    bl_idname = "daw.project_apply_template"
    bl_label = "Aplicar Template"
    bl_description = "Aplica um template ao projeto atual"
    bl_options = {'REGISTER', 'UNDO'}

    template_name: StringProperty(default="empty")

    def execute(self, context):
        if apply_template(context.scene, self.template_name):
            _proj(context).is_modified = True
            self.report({'INFO'}, f"Template '{self.template_name}' aplicado")
            return {'FINISHED'}
        self.report({'ERROR'}, f"Template '{self.template_name}' não encontrado")
        return {'CANCELLED'}


class DAW_OT_ProjectSaveTemplate(Operator):
    bl_idname = "daw.project_save_template"
    bl_label = "Salvar como Template"
    bl_description = "Salva o estado atual como template"
    bl_options = {'REGISTER'}

    template_name: StringProperty(name="Nome", default="Meu Template")

    def execute(self, context):
        if save_user_template(context.scene, self.template_name):
            self.report({'INFO'}, f"Template '{self.template_name}' salvo")
            return {'FINISHED'}
        self.report({'ERROR'}, "Falha ao salvar template")
        return {'CANCELLED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "template_name")


# ---------------------------------------------------------------------- #
# Exportar / Importar
# ---------------------------------------------------------------------- #
class DAW_OT_ProjectExport(Operator):
    bl_idname = "daw.project_export"
    bl_label = "Exportar Projeto"
    bl_description = "Exporta o projeto para um arquivo JSON"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        if not self.filepath:
            return {'CANCELLED'}
        if save_project(self.filepath, context.scene):
            self.report({'INFO'}, "Projeto exportado")
            return {'FINISHED'}
        self.report({'ERROR'}, "Falha ao exportar")
        return {'CANCELLED'}

    def invoke(self, context, event):
        self.filepath = str(get_default_project_dir() / "export.dawproj")
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class DAW_OT_ProjectImport(Operator):
    bl_idname = "daw.project_import"
    bl_label = "Importar Projeto"
    bl_description = "Importa um projeto de um arquivo JSON"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        if not self.filepath:
            return {'CANCELLED'}
        if load_project(self.filepath, context.scene):
            self.report({'INFO'}, "Projeto importado")
            return {'FINISHED'}
        self.report({'ERROR'}, "Falha ao importar")
        return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


classes = [
    DAW_OT_ProjectNew,
    DAW_OT_ProjectOpen,
    DAW_OT_ProjectSave,
    DAW_OT_ProjectSaveAs,
    DAW_OT_ProjectBackup,
    DAW_OT_ProjectRestoreBackup,
    DAW_OT_ProjectToggleAutosave,
    DAW_OT_ProjectApplyTemplate,
    DAW_OT_ProjectSaveTemplate,
    DAW_OT_ProjectExport,
    DAW_OT_ProjectImport,
]