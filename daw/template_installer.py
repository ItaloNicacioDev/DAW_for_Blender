"""
daw/template_installer.py
Gera startup.blend com workspace DAW de 1 área VSE.
"""

import bpy
import shutil
from pathlib import Path


def _get_template_dest() -> Path:
    scripts = Path(bpy.utils.resource_path('USER')) / "scripts"
    return scripts / "startup" / "bl_app_templates_user" / "DAW"


def _get_template_src() -> Path:
    return Path(__file__).parent / "template" / "DAW"


def _generate_startup_blend(dest: Path):
    try:
        # Limpa cena
        for text in list(bpy.data.texts):
            bpy.data.texts.remove(text)
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

        window = bpy.context.window_manager.windows[0]

        # Deleta DAW antigo
        old = bpy.data.workspaces.get("DAW")
        if old:
            if window.workspace == old:
                fallback = next((w for w in bpy.data.workspaces if w.name != "DAW"), None)
                if fallback:
                    window.workspace = fallback
            with bpy.context.temp_override(workspace=old):
                bpy.ops.workspace.delete()

        # [FIX] Cria workspace NOVO via operador (1 área limpa, template General)
        bpy.ops.workspace.add()
        ws = bpy.context.workspace
        ws.name = "DAW"
        window.workspace = ws

        screen = ws.screens[0]
        print(f"[DAW] Workspace novo: {len(screen.areas)} área(s)")

        # Troca a área única para Sequencer
        for area in screen.areas:
            area.type = 'SEQUENCE_EDITOR'
            for sp in area.spaces:
                if sp.type == 'SEQUENCE_EDITOR':
                    sp.view_type = 'SEQUENCER'

        # Remove workspaces extras
        for other_ws in list(bpy.data.workspaces):
            if other_ws.name != "DAW":
                with bpy.context.temp_override(workspace=other_ws):
                    try:
                        bpy.ops.workspace.delete()
                    except Exception:
                        pass

        # Salva
        startup_path = str(dest / "startup.blend")
        bpy.ops.wm.save_as_mainfile(filepath=startup_path)
        print(f"[DAW] startup.blend: {startup_path} ({len(screen.areas)} área, {screen.areas[0].type})")
        return True

    except Exception as e:
        print(f"[DAW] Erro ao gerar startup.blend: {e}")
        return False


def install_template(force: bool = False) -> bool:
    dest = _get_template_dest()
    src = _get_template_src()

    try:
        dest.mkdir(parents=True, exist_ok=True)

        init_src = src / "__init__.py"
        init_dst = dest / "__init__.py"
        if init_src.exists():
            shutil.copy2(str(init_src), str(init_dst))
        else:
            init_dst.write_text(
                "# DAW Application Template\n"
                "def register(): pass\n"
                "def unregister(): pass\n"
            )

        startup = dest / "startup.blend"
        if startup.exists():
            startup.unlink()
            print("[DAW] startup.blend antigo removido")

        _generate_startup_blend(dest)
        print(f"[DAW] Template instalado em: {dest}")
        return True

    except Exception as e:
        print(f"[DAW] Erro ao instalar template: {e}")
        return False


def uninstall_template():
    dest = _get_template_dest()
    if dest.exists():
        try:
            shutil.rmtree(str(dest))
            print(f"[DAW] Template removido de: {dest}")
        except Exception as e:
            print(f"[DAW] Erro ao remover template: {e}")


def is_installed() -> bool:
    return (_get_template_dest() / "__init__.py").exists()