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


def _rects_adjacent(a, b):
    """Verifica se duas áreas compartilham uma borda inteira (condição
    pra `screen.area_join` conseguir fundir as duas em uma só). Retorna
    o ponto (x, y) em coordenadas de tela bem no meio da borda
    compartilhada -- é onde o operador precisa que o cursor esteja,
    igual a clicar/arrastar sobre a borda na interface."""
    if a.x + a.width == b.x or b.x + b.width == a.x:
        y0, y1 = max(a.y, b.y), min(a.y + a.height, b.y + b.height)
        if y1 > y0:
            edge_x = a.x + a.width if a.x + a.width == b.x else a.x
            return (edge_x, (y0 + y1) // 2)
    if a.y + a.height == b.y or b.y + b.height == a.y:
        x0, x1 = max(a.x, b.x), min(a.x + a.width, b.x + b.width)
        if x1 > x0:
            edge_y = a.y + a.height if a.y + a.height == b.y else a.y
            return ((x0 + x1) // 2, edge_y)
    return None


def _collapse_screen_to_single_area(window, screen, max_iters: int = 25) -> None:
    """[FIX WORKSPACE QUÁDRUPLO] Funde TODAS as áreas da tela numa única
    área, uma junção por vez, até sobrar só uma. Sem isso,
    `_generate_startup_blend` estava convertendo cada área que o
    Blender já tinha por padrão (viewport 3D, timeline, outliner,
    propriedades -- normalmente 4) em Sequence Editor, mantendo as
    divisões originais -- daí o layout "quádruplo" salvo no
    startup.blend."""
    for _ in range(max_iters):
        areas = list(screen.areas)
        if len(areas) <= 1:
            return
        joined = False
        for a in areas:
            for b in areas:
                if a == b:
                    continue
                point = _rects_adjacent(a, b)
                if point is None:
                    continue
                try:
                    with bpy.context.temp_override(window=window, screen=screen, area=a):
                        bpy.ops.screen.area_join(cursor=point)
                    joined = True
                except Exception:
                    continue
                break
            if joined:
                break
        if not joined:
            # nenhuma fusão possível nesta rodada (layout não-retangular
            # incomum) -- para aqui pra não ficar em loop infinito
            print(f"[DAW] Aviso: não consegui fundir todas as áreas "
                  f"({len(list(screen.areas))} restante(s))")
            return


def _generate_startup_blend(dest: Path):
    """
    Gera o startup.blend do template diretamente via API do Blender.
    Cria workspace DAW com Sequence Editor limpo (UMA área só,
    ocupando a tela inteira).
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
        screen = ws.screens[0]

        # [FIX WORKSPACE QUÁDRUPLO] Funde tudo numa área só ANTES de
        # trocar o tipo -- antes, cada uma das áreas padrão do Blender
        # (viewport, timeline, outliner, propriedades) virava um
        # Sequence Editor separado, preservando a divisão em 4.
        _collapse_screen_to_single_area(window, screen)

        # Configura a área restante (idealmente só uma) como Sequence Editor
        for area in screen.areas:
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