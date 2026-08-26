import bpy

DAW_WORKSPACE_NAME = "DAW"


def ensure_daw_workspace():
    """Cria workspace DAW se não existir (sem layout)."""
    ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
    if ws is None:
        base = bpy.data.workspaces.get('Layout') or bpy.data.workspaces[0]
        with bpy.context.temp_override(workspace=base):
            bpy.ops.workspace.duplicate()
        ws = bpy.context.workspace
        ws.name = DAW_WORKSPACE_NAME
    return ws


# ═══════════════════════════════════════════════════════════════
#  CRIAÇÃO DO LAYOUT — apenas uma área central
#
#  ┌──────────────────────────────┐
#  │      SEQUENCE_EDITOR         │
#  │         (100%)               │
#  └──────────────────────────────┘
# ═══════════════════════════════════════════════════════════════

def _recreate_and_apply(window):
    """
    Deleta o workspace DAW existente, recria do zero a partir do Layout
    (que sempre tem 1 área), e define como SEQUENCE_EDITOR único.
    """
    try:
        # 1. Garante que não estamos no workspace DAW antes de deletar
        current_ws = window.workspace
        if current_ws.name == DAW_WORKSPACE_NAME:
            fallback = next(
                (w for w in bpy.data.workspaces if w.name != DAW_WORKSPACE_NAME),
                None
            )
            if fallback:
                window.workspace = fallback

        # 2. Deleta workspace DAW antigo
        old = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
        if old:
            with bpy.context.temp_override(workspace=old):
                bpy.ops.workspace.delete()
            print("[DAW] Workspace antigo removido")

        # 3. Duplica o Layout (sempre tem 1 área limpa)
        base = bpy.data.workspaces.get('Layout') or bpy.data.workspaces[0]
        with bpy.context.temp_override(workspace=base):
            bpy.ops.workspace.duplicate()

        ws = bpy.context.workspace
        ws.name = DAW_WORKSPACE_NAME

        # 4. Troca para o novo workspace DAW
        window.workspace = ws

        # 5. Define a área única como SEQUENCE_EDITOR
        def _do_setup():
            try:
                ws2 = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
                if not ws2:
                    return

                screen = ws2.screens[0]
                print(f"[DAW] Áreas disponíveis: {len(screen.areas)}")

                main = screen.areas[0]
                main.type = 'SEQUENCE_EDITOR'

                for sp in main.spaces:
                    if sp.type == 'SEQUENCE_EDITOR':
                        sp.view_type = 'SEQUENCER'

                print("[DAW] Layout aplicado: Sequencer 100% ✅")

            except Exception as e:
                print(f"[DAW] Erro ao configurar área: {e}")
            return None

        bpy.app.timers.register(_do_setup, first_interval=0.25)

    except Exception as e:
        print(f"[DAW] Erro ao recriar workspace: {e}")


# ═══════════════════════════════════════════════════════════════
#  REMOÇÃO (uninstall)
# ═══════════════════════════════════════════════════════════════

def remove_daw_workspace():
    """Remove o workspace DAW ao desinstalar o addon."""
    ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
    if ws:
        try:
            # Troca para outro workspace antes
            for w in bpy.context.window_manager.windows:
                if w.workspace.name == DAW_WORKSPACE_NAME:
                    fallback = next(
                        (x for x in bpy.data.workspaces if x.name != DAW_WORKSPACE_NAME),
                        None
                    )
                    if fallback:
                        w.workspace = fallback
            with bpy.context.temp_override(workspace=ws):
                bpy.ops.workspace.delete()
            print("[DAW] Workspace DAW removido")
        except Exception as e:
            print(f"[DAW] Aviso ao remover workspace: {e}")


# ═══════════════════════════════════════════════════════════════
#  OPERADOR
# ═══════════════════════════════════════════════════════════════

class DAW_OT_OpenWorkspace(bpy.types.Operator):
    bl_idname      = "daw.open_workspace"
    bl_label       = "Abrir DAW"
    bl_description = "Abre o workspace DAW (Sequencer único)"

    def execute(self, context):
        window = context.window
        _recreate_and_apply(window)
        return {'FINISHED'}


def draw_topbar_daw_button(self, context):
    self.layout.separator()
    self.layout.operator("daw.open_workspace", text="🎵 DAW", icon='SPEAKER')


def register():
    bpy.utils.register_class(DAW_OT_OpenWorkspace)
    bpy.types.TOPBAR_MT_editor_menus.append(draw_topbar_daw_button)


def unregister():
    bpy.types.TOPBAR_MT_editor_menus.remove(draw_topbar_daw_button)
    bpy.utils.unregister_class(DAW_OT_OpenWorkspace)