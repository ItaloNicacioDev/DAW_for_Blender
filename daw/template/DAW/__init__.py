"""
DAW Application Template

Roda quando o usuário seleciona "DAW" na splash screen.
Garante workspace DAW com 1 área Sequencer.
"""

import bpy


def register():
    try:
        window = bpy.context.window_manager.windows[0]
        ws = window.workspace

        # Renomeia para DAW
        ws.name = "DAW"
        screen = ws.screens[0]

        # Se por algum motivo vier com >1 área, cria workspace novo limpo
        if len(screen.areas) > 1:
            print(f"[DAW] Template: {len(screen.areas)} áreas detectadas, recriando workspace limpo")
            old_name = ws.name
            # Cria novo workspace limpo (1 área)
            ws_new = bpy.data.workspaces.new(name="DAW_CLEAN")
            window.workspace = ws_new
            # Deleta o antigo
            old_ws = bpy.data.workspaces.get(old_name)
            if old_ws:
                with bpy.context.temp_override(workspace=old_ws):
                    try:
                        bpy.ops.workspace.delete()
                    except Exception:
                        pass
            ws_new.name = "DAW"
            ws = ws_new
            screen = ws.screens[0]

        # Configura a área única como Sequencer
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