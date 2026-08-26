"""
DAW Application Template

Roda quando o usuário seleciona "DAW" na splash screen.
Garante 1 área VSE e remove workspaces extras.
"""

import bpy


def _fix_daw_layout():
    try:
        if not bpy.context.window_manager.windows:
            return None

        window = bpy.context.window_manager.windows[0]
        screen = window.workspace.screens[0]

        # Configura todas as áreas como Sequencer
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