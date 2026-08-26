import bpy

DAW_WORKSPACE_NAME = "DAW"


def _has_full_edge(a, b, tol=3):
    if abs(b.x + b.width - a.x) <= tol:
        y0, y1 = max(a.y, b.y), min(a.y + a.height, b.y + b.height)
        if (y1 - y0) >= min(a.height, b.height) - tol:
            return (int(a.x), int((y0 + y1) // 2)), a
    if abs(a.x + a.width - b.x) <= tol:
        y0, y1 = max(a.y, b.y), min(a.y + a.height, b.y + b.height)
        if (y1 - y0) >= min(a.height, b.height) - tol:
            return (int(b.x), int((y0 + y1) // 2)), b
    if abs(a.y - (b.y + b.height)) <= tol:
        x0, x1 = max(a.x, b.x), min(a.x + a.width, b.x + b.width)
        if (x1 - x0) >= min(a.width, b.width) - tol:
            return (int((x0 + x1) // 2), int(a.y)), a
    if abs(a.y + a.height - b.y) <= tol:
        x0, x1 = max(a.x, b.x), min(a.x + a.width, b.x + b.width)
        if (x1 - x0) >= min(a.width, b.width) - tol:
            return (int((x0 + x1) // 2), int(b.y)), b
    return None


def _collapse_to_one_area(window, screen):
    for _ in range(20):
        areas = list(screen.areas)
        if len(areas) <= 1:
            return True
        merged = False
        for i, a in enumerate(areas):
            for b in areas[i + 1:]:
                result = _has_full_edge(a, b)
                if result:
                    point, target = result
                    try:
                        with bpy.context.temp_override(window=window, screen=screen, area=target):
                            bpy.ops.screen.area_join(cursor=point)
                        merged = True
                        break
                    except Exception:
                        pass
            if merged:
                break
        if not merged:
            break
    return len(list(screen.areas)) == 1


def ensure_daw_workspace():
    ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
    if ws is None:
        base = bpy.data.workspaces.get('Layout') or bpy.data.workspaces[0]
        with bpy.context.temp_override(workspace=base):
            bpy.ops.workspace.duplicate()
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

        # Duplica Layout
        base = bpy.data.workspaces.get('Layout') or bpy.data.workspaces[0]
        with bpy.context.temp_override(workspace=base):
            bpy.ops.workspace.duplicate()

        ws = bpy.context.workspace
        ws.name = DAW_WORKSPACE_NAME
        window.workspace = ws

        screen = ws.screens[0]

        # Colapsa
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