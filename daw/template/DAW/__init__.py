"""
DAW Application Template __init__.py

Roda automaticamente quando o usuário seleciona "DAW" na splash screen.
Garante que o layout tenha apenas 1 área, mesmo se o startup.blend
estiver corrompido ou desatualizado.
"""

import bpy


def _ensure_single_area():
    """Garante que o workspace DAW tenha exatamente 1 área (SEQUENCE_EDITOR)."""
    try:
        window = bpy.context.window_manager.windows[0]
        ws = window.workspace
        if ws.name != "DAW":
            return

        screen = ws.screens[0]

        # Funde áreas até sobrar 1
        for _ in range(20):
            areas = list(screen.areas)
            if len(areas) <= 1:
                break

            # Tenta juntar a primeira área com qualquer vizinha
            a = areas[0]
            joined = False
            for b in areas[1:]:
                # Tenta juntar horizontalmente ou verticalmente
                if a.x + a.width == b.x or b.x + b.width == a.x:
                    point = (max(a.x, b.x), (max(a.y, b.y) + min(a.y + a.height, b.y + b.height)) // 2)
                elif a.y + a.height == b.y or b.y + b.height == a.y:
                    point = ((max(a.x, b.x) + min(a.x + a.width, b.x + b.width)) // 2, max(a.y, b.y))
                else:
                    continue

                try:
                    with bpy.context.temp_override(window=window, screen=screen, area=a):
                        bpy.ops.screen.area_join(cursor=point)
                    joined = True
                    break
                except Exception:
                    continue

            if not joined:
                break

        # Configura a área restante
        if len(screen.areas) >= 1:
            main = screen.areas[0]
            main.type = 'SEQUENCE_EDITOR'
            for sp in main.spaces:
                if sp.type == 'SEQUENCE_EDITOR':
                    sp.view_type = 'SEQUENCER'

        print("[DAW] Template: layout garantido como 1 área")

    except Exception as e:
        print(f"[DAW] Template: erro ao ajustar layout: {e}")


def register():
    # Adia 0.1s para garantir que o Blender terminou de carregar o startup.blend
    bpy.app.timers.register(_ensure_single_area, first_interval=0.1)


def unregister():
    pass