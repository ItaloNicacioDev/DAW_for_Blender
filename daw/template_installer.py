"""
daw/template_installer.py

Instalação automática do Application Template DAW na splash screen.
Chamado pelo register() do addon — sem intervenção manual.
"""

import bpy
import os
import shutil
from pathlib import Path


def _get_template_dest() -> Path:
    """Retorna o caminho de destino do template no Blender do usuário."""
    # Caminho padrão: scripts/startup/bl_app_templates_user/DAW/
    scripts = Path(bpy.utils.resource_path('USER')) / "scripts"
    return scripts / "startup" / "bl_app_templates_user" / "DAW"


def _get_template_src() -> Path:
    """Retorna a pasta template/ que está dentro do addon."""
    return Path(__file__).parent / "template" / "DAW"


def _generate_startup_blend(dest: Path):
    """
    Gera o startup.blend do template diretamente via API do Blender.
    Cria workspace DAW com Sequence Editor limpo.
    """
    try:
        # Remove textos/scripts abertos
        for text in list(bpy.data.texts):
            bpy.data.texts.remove(text)

        # Limpa objetos da cena padrão
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

        # Pega o workspace atual e renomeia para DAW
        window = bpy.context.window_manager.windows[0]
        ws = window.workspace
        ws.name = "DAW"

        # Configura todas as áreas como Sequence Editor
        for area in ws.screens[0].areas:
            area.type = 'SEQUENCE_EDITOR'
            for space in area.spaces:
                if space.type == 'SEQUENCE_EDITOR':
                    space.view_type = 'SEQUENCER'

        # Remove workspaces extras (Layout, Modeling, etc.)
        for other_ws in list(bpy.data.workspaces):
            if other_ws.name != "DAW":
                with bpy.context.temp_override(workspace=other_ws):
                    try:
                        bpy.ops.workspace.delete()
                    except Exception:
                        pass

        # Salva o startup.blend dentro do template
        startup_path = str(dest / "startup.blend")
        bpy.ops.wm.save_as_mainfile(filepath=startup_path)
        print(f"[DAW] startup.blend salvo em: {startup_path}")
        return True

    except Exception as e:
        print(f"[DAW] Aviso: não foi possível gerar startup.blend: {e}")
        return False


def install_template(force: bool = False) -> bool:
    """
    Instala o Application Template DAW.

    Args:
        force: Se True, reinstala mesmo que já exista.

    Returns:
        True se instalado com sucesso, False caso contrário.
    """
    dest = _get_template_dest()
    src  = _get_template_src()

    # Já instalado?
    if dest.exists() and not force:
        print(f"[DAW] Template já instalado em: {dest}")
        return True

    try:
        dest.mkdir(parents=True, exist_ok=True)

        # Copia __init__.py do template
        init_src = src / "__init__.py"
        init_dst = dest / "__init__.py"

        if init_src.exists():
            shutil.copy2(str(init_src), str(init_dst))
        else:
            # Cria __init__.py mínimo inline se não existir
            init_dst.write_text(
                "# DAW Application Template\n"
                "def register(): pass\n"
                "def unregister(): pass\n"
            )

        print(f"[DAW] Template instalado em: {dest}")

        # Gera startup.blend se não existir
        startup = dest / "startup.blend"
        if not startup.exists():
            _generate_startup_blend(dest)

        return True

    except Exception as e:
        print(f"[DAW] Erro ao instalar template: {e}")
        return False


def uninstall_template():
    """Remove o Application Template DAW (chamado no unregister do addon)."""
    dest = _get_template_dest()
    if dest.exists():
        try:
            shutil.rmtree(str(dest))
            print(f"[DAW] Template removido de: {dest}")
        except Exception as e:
            print(f"[DAW] Erro ao remover template: {e}")


def is_installed() -> bool:
    """Verifica se o template já está instalado."""
    return (_get_template_dest() / "__init__.py").exists()