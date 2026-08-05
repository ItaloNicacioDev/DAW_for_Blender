# modules/update/operators.py
"""
Operadores do sistema de auto-atualização.

Todos os operadores retornam imediatamente ({'FINISHED'}) — o trabalho
pesado (rede/disco) roda em background (ver jobs.py) e a UI se atualiza
sozinha via `bpy.app.timers`.
"""
from __future__ import annotations

import subprocess
import webbrowser

import bpy
from bpy.types import Operator

from . import config, jobs
from .properties import get_updater_state


class DAW_OT_updater_check(Operator):
    """Verifica se há uma nova versão da DAW disponível no GitHub"""
    bl_idname = "daw.updater_check"
    bl_label = "Verificar Atualizações"
    bl_options = {'REGISTER'}

    def execute(self, context):
        jobs.run_check_update(silent=False)
        self.report({'INFO'}, "Verificando atualizações no GitHub...")
        return {'FINISHED'}


class DAW_OT_updater_download_install(Operator):
    """Baixa e instala a atualização mais recente"""
    bl_idname = "daw.updater_download_install"
    bl_label = "Baixar e Instalar Atualização"
    bl_options = {'REGISTER'}

    def execute(self, context):
        st = get_updater_state(context)
        if not st.download_url:
            self.report({'ERROR'}, "Nenhuma URL de download disponível. Verifique atualizações primeiro.")
            return {'CANCELLED'}

        jobs.run_download_and_install(st.download_url)
        self.report({'INFO'}, "Baixando e instalando a atualização...")
        return {'FINISHED'}


class DAW_OT_updater_open_releases(Operator):
    """Abre a página de releases do addon no GitHub"""
    bl_idname = "daw.updater_open_releases"
    bl_label = "Ver no GitHub"
    bl_options = {'REGISTER'}

    def execute(self, context):
        st = get_updater_state(context)
        url = st.release_url or config.releases_page_url()
        webbrowser.open(url)
        return {'FINISHED'}


class DAW_OT_updater_restart_blender(Operator):
    """Fecha e reabre o Blender para concluir a atualização (salve seu trabalho antes)"""
    bl_idname = "daw.updater_restart_blender"
    bl_label = "Reiniciar o Blender"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        try:
            args = [bpy.app.binary_path]
            if bpy.data.filepath:
                args.append(bpy.data.filepath)
            subprocess.Popen(args)
        except Exception as e:
            self.report(
                {'ERROR'},
                f"Não foi possível reabrir automaticamente ({e}). "
                f"Feche e abra o Blender manualmente.",
            )
            return {'CANCELLED'}

        bpy.ops.wm.quit_blender()
        return {'FINISHED'}


classes = [
    DAW_OT_updater_check,
    DAW_OT_updater_download_install,
    DAW_OT_updater_open_releases,
    DAW_OT_updater_restart_blender,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)