"""
DAW Application Template

Roda quando o usuário seleciona "DAW" na splash screen.
Garante 1 área VSE e remove workspaces extras.
"""

import bpy


def _get_join_point(a, b, tol=10):
    if abs(b.x + b.width - a.x) <= tol:
        y0, y1 = max(a.y, b.y), min(a.y + a.height, b.y + b.height)
        if y1 > y0:
            return (int((max(b.x + b.width, a.x) + min(b.x + b.width, a.x)) // 2), int((y0 + y1) // 2))
    if abs(a.x + a.width - b.x) <= tol:
        y0, y1 = max(a.y, b.y), min(a.y + a.height, b.y + b.height)
        if y1 > y0:
            return (int((max(a.x + a.width, b.x) + min(a.x + a.width, b.x)) // 2), int((y0 + y1) // 2))
    if abs(a.y + a.height - b.y) <= tol:
        x0, x1 = max(a.x, b.x), min(a.x + a.width, b.x + b.width)
        if x1 > x0:
            return (int((x0 + x1) // 2), int((max(a.y + a.height, b.y) + min(a.y + a.height, b.y)) // 2))
    if abs(b.y + b.height - a.y) <= tol:
        x0, x1 = max(a.x, b.x), min(a.x + a.width, b.x + b.width)
        if x1 > x0:
            return (int((x0 + x1) // 2), int((max(b.y + b.height, a.y) + min(b.y + b.height, a.y)) // 2))
    return None


def _collapse_to_one_area(window, screen):
    for _ in range(25):
        areas = list(screen.areas)
        if len(areas) <= 1:
            return True
        merged = False
        areas_sorted = sorted(areas, key=lambda a: a.width * a.height, reverse=True)
        for target in areas_sorted:
            for other in areas_sorted:
                if target == other:
                    continue
                point = _get_join_point(target, other)
                if point:
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


def _remove_extra_workspaces():
    daw_ws = bpy.data.workspaces.get("DAW")
    if not daw_ws:
        return
    for w in bpy.context.window_manager.windows:
        if w.workspace != daw_ws:
            w.workspace = daw_ws
    for ws in list(bpy.data.workspaces):
        if ws.name == "DAW":
            continue
        try:
            with bpy.context.temp_override(workspace=ws):
                bpy.ops.workspace.delete()
        except Exception:
            pass


def _fix_daw_layout():
    try:
        if not bpy.context.window_manager.windows:
            return None

        window = bpy.context.window_manager.windows[0]
        screen = window.workspace.screens[0]

        # Colapsa se necessário
        if len(screen.areas) > 1:
            _collapse_to_one_area(window, screen)

        # Configura como Sequencer
        for area in screen.areas:
            area.type = 'SEQUENCE_EDITOR'
            for sp in area.spaces:
                if sp.type == 'SEQUENCE_EDITOR':
                    sp.view_type = 'SEQUENCER'

        # Remove workspaces extras
        _remove_extra_workspaces()

        print(f"[DAW] Template: {len(screen.areas)} área(s) | {screen.areas[0].type if screen.areas else 'none'}")
        print(f"[DAW] Workspaces: {[w.name for w in bpy.data.workspaces]}")
        return None

    except Exception as e:
        print(f"[DAW] Template erro: {e}")
        return None


def register():
    bpy.app.timers.register(_fix_daw_layout, first_interval=0.3)


def unregister():
    pass