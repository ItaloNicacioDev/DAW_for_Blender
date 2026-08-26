"""
DAW Application Template

Roda quando o usuário seleciona "DAW" na splash screen
ou cria New > DAW. Garante 1 área VSE e remove workspaces extras.
"""

import bpy


def _fix_daw_layout():
    """Timer callback: garante layout limpo após carregamento completo."""
    try:
        if not bpy.context.window_manager.windows:
            return 0.1  # ainda não tem janela, retry

        window = bpy.context.window_manager.windows[0]
        screen = window.workspace.screens[0]

        # Se vier com mais de 1 área (fallback), funde tudo na maior
        if len(screen.areas) > 1:
            areas = sorted(screen.areas, key=lambda a: a.width * a.height, reverse=True)
            main = areas[0]
            for other in areas[1:]:
                point = _rects_adjacent(main, other)
                if point:
                    try:
                        with bpy.context.temp_override(window=window, screen=screen, area=main):
                            bpy.ops.screen.area_join(cursor=point)
                    except Exception:
                        pass

        # Configura a área (ou a única restante) como Sequencer
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

        print(f"[DAW] Template ativo: {len(screen.areas)} área(s) | tipo={screen.areas[0].type if screen.areas else 'none'}")
        return None

    except Exception as e:
        print(f"[DAW] Template layout erro: {e}")
        return None


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


def register():
    # Adia 0.5s para garantir que o Blender terminou de carregar o arquivo
    bpy.app.timers.register(_fix_daw_layout, first_interval=0.5)


def unregister():
    pass