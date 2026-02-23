"""
COMO USAR:
1. Abra o Blender com um arquivo novo vazio (General)
2. Vá em Scripting
3. Abra este arquivo e clique Run Script (▶)
4. Reinicie o Blender — "DAW" vai aparecer na splash screen
"""

import bpy
import os
from pathlib import Path

TEMPLATE = Path(os.environ["APPDATA"]) / \
    "Blender Foundation" / "Blender" / "5.0" / \
    "scripts" / "startup" / "bl_app_templates_user" / "DAW"

def gerar():
    TEMPLATE.mkdir(parents=True, exist_ok=True)

    # Remove textos/scripts abertos
    for text in list(bpy.data.texts):
        bpy.data.texts.remove(text)

    # Limpa a cena
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Configura workspace
    window = bpy.context.window_manager.windows[0]
    ws = window.workspace
    ws.name = "DAW"

    # Sequencer em tela cheia
    for area in ws.screens[0].areas:
        area.type = 'SEQUENCE_EDITOR'
        for space in area.spaces:
            if space.type == 'SEQUENCE_EDITOR':
                space.view_type = 'SEQUENCER'

    # Remove workspaces extras
    for other in list(bpy.data.workspaces):
        if other.name != "DAW":
            with bpy.context.temp_override(workspace=other):
                try:
                    bpy.ops.workspace.delete()
                except:
                    pass

    bpy.ops.wm.save_as_mainfile(filepath=str(TEMPLATE / "startup.blend"))
    print(f"✅ startup.blend salvo em: {TEMPLATE}")
    print("Reinicie o Blender!")

gerar()
