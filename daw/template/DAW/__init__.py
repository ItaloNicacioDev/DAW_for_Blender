"""
DAW Application Template

Roda quando o usuário seleciona "DAW" na splash screen.
Garante 1 área Sequencer, mesmo se o startup.blend estiver com layout quebrado.
"""

import bpy


def _rects_adjacent(a, b, tol=2):
    if abs(a.x + a.width - b.x) <= tol or abs(b.x + b.width - a.x) <= tol:
        y0, y1 = max(a.y, b.y), min(a.y + a.height, b.y + b.height)
        if y1 > y0:
            edge_x = a.x + a.width if a.x + a.width <= b.x + tol else a.x
            return (edge_x, (y0 + y1) // 2)
    if abs(a.y + a.height - b.y) <= tol or abs(b.y + b.height - a.y) <= tol:
        x0, x1 = max(a.x, b.x), min(a.x + a.width, b.x + b.width)
        if x1 > x0:
            edge_y = a.y + a.height if a.y + a.height <= b.y + tol else a.y
            return ((x0 + x1) // 2, edge_y)
    return None


def _collapse_to_single_area(window, screen):
    for _ in range(25):
        areas = list(screen.areas)
        if len(areas) <= 1:
            return True

        areas_sorted = sorted(areas, key=lambda a: a.width * a.height, reverse=True)
        main = areas_sorted[0]

        joined = False
        for other in areas_sorted[1:]:
            point = _rects_adjacent(main, other)
            if point is None:
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


def register():
    try:
        window = bpy.context.window_manager.windows[0]
        ws = window.workspace

        # Renomeia para DAW
        ws.name = "DAW"
        screen = ws.screens[0]

        # Colapsa para 1 área (maior absorve menor)
        if len(screen.areas) > 1:
            _collapse_to_single_area(window, screen)

        # Configura como Sequencer
        for area in screen.areas:
            area.type = 'SEQUENCE_EDITOR'
            for sp in area.spaces:
                if sp.type == 'SEQUENCE_EDITOR':
                    sp.view_type = 'SEQUENCER'

        # Remove workspaces extras
        for other in list(bpy.data.workspaces):
            if other.name != "DAW":
                try:
                    with bpy.context.temp_override(workspace=other):
                        bpy.ops.workspace.delete()
                except Exception:
                    pass

        print(f"[DAW] Template ativo: {len(screen.areas)} área(s)")

    except Exception as e:
        print(f"[DAW] Erro no template: {e}")


def unregister():
    pass