"""
daw/template_installer.py

Instalação automática do Application Template DAW na splash screen.
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
    """
    Gera startup.blend limpo com workspace DAW de 1 área.
    [FIX] Usa workspaces.new() em vez de duplicar Layout — evita herdar
    as 4 áreas do workspace padrão do Blender.
    """
    try:
        # Limpa cena
        for text in list(bpy.data.texts):
            bpy.data.texts.remove(text)
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

        window = bpy.context.window_manager.windows[0]

        # [FIX CRITICAL] Cria workspace NOVO do zero (1 área) em vez de duplicar Layout (4 áreas)
        ws = bpy.data.workspaces.new(name="DAW")
        window.workspace = ws

        screen = ws.screens[0]
        print(f"[DAW] Novo workspace criado: {len(screen.areas)} área(s)")

        # Configura a única área como Sequencer
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
        print(f"[DAW] startup.blend gerado: {startup_path} ({len(screen.areas)} área)")
        return True

    except Exception as e:
        print(f"[DAW] Erro ao gerar startup.blend: {e}")
        return False


def install_template(force: bool = False) -> bool:
    dest = _get_template_dest()
    src  = _get_template_src()

    try:
        dest.mkdir(parents=True, exist_ok=True)

        # Copia __init__.py do template
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

        # Deleta startup.blend antigo (se existir) e gera novo
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