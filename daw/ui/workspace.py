import bpy

DAW_WORKSPACE_NAME = "DAW"


def _collapse_to_one_area(window, screen):
    for _ in range(20):
        areas = list(screen.areas)
        if len(areas) <= 1:
            return True

        areas_sorted = sorted(areas, key=lambda a: a.width * a.height, reverse=True)
        main = areas_sorted[0]

        joined = False
        for other in areas_sorted[1:]:
            if abs(main.x + main.width - other.x) <= 2:
                point = (main.x + main.width, (max(main.y, other.y) + min(main.y + main.height, other.y + other.height)) // 2)
            elif abs(other.x + other.width - main.x) <= 2:
                point = (other.x + other.width, (max(main.y, other.y) + min(main.y + main.height, other.y + other.height)) // 2)
            elif abs(main.y + main.height - other.y) <= 2:
                point = ((max(main.x, other.x) + min(main.x + main.width, other.x + other.width)) // 2, main.y + main.height)
            elif abs(other.y + other.height - main.y) <= 2:
                point = ((max(main.x, other.x) + min(main.x + main.width, other.x + other.width)) // 2, other.y + other.height)
            else:
                continue

            try:
                with bpy.context.temp_override(window=window, screen=screen, area=main):
                    bpy.ops.screen.area_join(cursor=point)
                joined = True
                break
            except Exception:
                continue

        if not joined:
            break

    return len(list(screen.areas)) == 1


def ensure_daw_workspace():
    ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
    if ws is None:
        bpy.ops.workspace.add()
        ws = bpy.context.workspace
        ws.name = DAW_WORKSPACE_NAME
    return ws


def _recreate_and_apply(window):
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

        # Cria workspace novo
        bpy.ops.workspace.add()
        ws = bpy.context.workspace
        ws.name = DAW_WORKSPACE_NAME
        window.workspace = ws

        screen = ws.screens[0]

        # Funde se necessário
        if len(screen.areas) > 1:
            _collapse_to_one_area(window, screen)

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
                print(f"[DAW] Layout: {len(scr.areas)} área(s) | {scr.areas[0].type}")
            except Exception as e:
                print(f"[DAW] Setup erro: {e}")
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