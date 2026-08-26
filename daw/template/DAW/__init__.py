"""
DAW Application Template

Roda quando o usuário seleciona "DAW" na splash screen.
Garante 1 área VSE e remove workspaces extras.
"""

import bpy


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
        for ws in list(bpy.data.workspaces):
            if ws.name != "DAW":
                try:
                    with bpy.context.temp_override(workspace=ws):
                        bpy.ops.workspace.delete()
                except Exception:
                    pass

        print(f"[DAW] Template: {len(screen.areas)} área(s) | {screen.areas[0].type if screen.areas else 'none'}")
        return None

    except Exception as e:
        print(f"[DAW] Template erro: {e}")
        return None


def register():
    bpy.app.timers.register(_fix_daw_layout, first_interval=0.3)


def unregister():
    pass