import bpy

DAW_WORKSPACE_NAME = "DAW"


def ensure_daw_workspace():
    """Cria workspace DAW se não existir."""
    ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
    if ws is None:
        ws = bpy.data.workspaces.new(name=DAW_WORKSPACE_NAME)
    return ws


def _recreate_and_apply(window):
    """
    Recria workspace DAW do zero com 1 área Sequencer.
    [FIX] Usa workspaces.new() em vez de duplicar Layout.
    """
    try:
        current_ws = window.workspace
        if current_ws.name == DAW_WORKSPACE_NAME:
            fallback = next(
                (w for w in bpy.data.workspaces if w.name != DAW_WORKSPACE_NAME),
                None
            )
            if fallback:
                window.workspace = fallback

        old = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
        if old:
            with bpy.context.temp_override(workspace=old):
                bpy.ops.workspace.delete()
            print("[DAW] Workspace antigo removido")

        # [CRITICAL] Cria workspace NOVO do zero (1 área limpa)
        ws = bpy.data.workspaces.new(name=DAW_WORKSPACE_NAME)
        window.workspace = ws
        screen = ws.screens[0]

        def _do_setup():
            try:
                ws2 = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
                if not ws2:
                    return
                scr = ws2.screens[0]
                for area in scr.areas:
                    area.type = 'SEQUENCE_EDITOR'
                    for sp in area.spaces:
                        if sp.type == 'SEQUENCE_EDITOR':
                            sp.view_type = 'SEQUENCER'
                print(f"[DAW] Layout aplicado: {len(scr.areas)} área(s) | tipo={scr.areas[0].type}")
            except Exception as e:
                print(f"[DAW] Erro no setup: {e}")
            return None

        bpy.app.timers.register(_do_setup, first_interval=0.25)

    except Exception as e:
        print(f"[DAW] Erro ao recriar workspace: {e}")


def remove_daw_workspace():
    ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
    if ws:
        try:
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


class DAW_OT_OpenWorkspace(bpy.types.Operator):
    bl_idname = "daw.open_workspace"
    bl_label = "Abrir DAW"
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