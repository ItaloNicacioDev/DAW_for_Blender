"""
DAW Application Template

Roda quando o usuário seleciona "DAW" na splash screen.
Garante 1 área VSE e remove workspaces extras.
"""

import bpy


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


def _fix_daw_layout():
    try:
        if not bpy.context.window_manager.windows:
            return None

        window = bpy.context.window_manager.windows[0]
        screen = window.workspace.screens[0]

        # Se veio com >1 área, funde tudo numa só
        if len(screen.areas) > 1:
            ok = _collapse_to_one_area(window, screen)
            print(f"[DAW] Template colapso: {'OK' if ok else 'parcial'} — {len(list(screen.areas))} área(s)")

        # Configura a área única como Sequencer
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

        print(f"[DAW] Template ativo: {len(screen.areas)} área(s) | {screen.areas[0].type if screen.areas else 'none'}")
        return None

    except Exception as e:
        print(f"[DAW] Template erro: {e}")
        return None


def register():
    bpy.app.timers.register(_fix_daw_layout, first_interval=0.3)


def unregister():
    pass