"""
daw/template_installer.py

Instalação automática do Application Template DAW na splash screen.
Chamado pelo register() do addon — sem intervenção manual.
"""

import bpy
import os
import shutil
from pathlib import Path

# [FIX AUTO-REGENERAÇÃO] Bump este número toda vez que
# `_generate_startup_blend` mudar de um jeito que precise refletir num
# `startup.blend` já instalado (ex.: o fix do workspace quádruplo).
# `install_template()` compara com o que está salvo em
# `.template_version` dentro da pasta do template e regenera sozinho
# se estiver desatualizado -- sem precisar apagar nada manualmente.
_TEMPLATE_VERSION = 4


def _get_template_dest() -> Path:
    """Retorna o caminho de destino do template no Blender do usuário."""
    # Caminho padrão: scripts/startup/bl_app_templates_user/DAW/
    scripts = Path(bpy.utils.resource_path('USER')) / "scripts"
    return scripts / "startup" / "bl_app_templates_user" / "DAW"


def _get_template_src() -> Path:
    """Retorna a pasta template/ que está dentro do addon."""
    return Path(__file__).parent / "template" / "DAW"


def _maximize_one_area(window, screen, area) -> bool:
    """[FIX SIMPLIFICADO] Em vez de tentar fundir/destruir fisicamente
    as outras áreas (frágil -- depende de geometria de tela já
    finalizada, que nem sempre está disponível no momento em que o
    template é gerado, ver histórico da versão anterior desta função),
    usa o recurso nativo do Blender de MAXIMIZAR área (o mesmo do
    atalho Ctrl+Espaço / 'Toggle Maximize Area'): a área escolhida
    passa a ocupar a janela inteira, escondendo as outras -- sem
    precisar reestruturar nada. Esse estado (`screen.show_fullscreen`)
    é salvo normalmente junto com o .blend, então ao abrir o template
    o usuário já vê só a área maximizada."""
    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    if region is None:
        return False
    try:
        with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
            if not screen.show_fullscreen:
                bpy.ops.screen.screen_full_area(use_hide_panels=False)
        return bool(screen.show_fullscreen)
    except Exception as e:
        print(f"[DAW] Não consegui maximizar a área: {e}")
        return False


def _generate_startup_blend(dest: Path):
    """
    Gera o startup.blend do template diretamente via API do Blender.
    Cria workspace DAW com Sequence Editor -- visualmente só ele
    aparece (as outras áreas padrão do Blender continuam existindo na
    tela por baixo, só que escondidas via 'maximizar área', igual
    Ctrl+Espaço na interface).
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

        # Configura TODAS as áreas como Sequence Editor -- mesmo as que
        # vão ficar escondidas atrás da maximizada, pra não sobrar
        # nenhuma "aba estranha" caso o usuário algum dia desmaximize
        # (Ctrl+Espaço de novo).
        for area in screen.areas:
            area.type = 'SEQUENCE_EDITOR'
            for space in area.spaces:
                if space.type == 'SEQUENCE_EDITOR':
                    space.view_type = 'SEQUENCER'

        # [FIX WORKSPACE QUÁDRUPLO] Maximiza a primeira área -- visualmente
        # fica só o Sequencer ocupando a tela inteira, sem depender de
        # geometria exata de área pra fundir/destruir nada.
        if screen.areas:
            _maximize_one_area(window, screen, screen.areas[0])

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

    [FIX AUTO-REGENERAÇÃO] Antes, se `dest` já existisse, a função
    parava ali (`return True`) sem nunca checar se o `startup.blend`
    salvo era de uma versão ANTIGA e quebrada do gerador (ex.: o bug do
    workspace quádruplo -- ver `_generate_startup_blend`). Corrigir o
    código do gerador não bastava: era preciso apagar manualmente o
    `startup.blend` velho pra alguma vez ele ser regenerado. Agora um
    arquivo marcador (`.template_version`) guarda com qual versão do
    gerador o `startup.blend` atual foi criado -- se não bater com
    `_TEMPLATE_VERSION` (a versão deste arquivo), ele é regenerado
    sozinho, sem precisar apagar nada na mão.
    """
    dest = _get_template_dest()
    src  = _get_template_src()
    version_marker = dest / ".template_version"

    def _stored_version() -> int:
        try:
            return int(version_marker.read_text().strip())
        except Exception:
            return 0

    needs_regen = force or not dest.exists() or _stored_version() != _TEMPLATE_VERSION

    # Já instalado E na versão atual? Não faz nada.
    if dest.exists() and not needs_regen:
        print(f"[DAW] Template já instalado em: {dest} (v{_TEMPLATE_VERSION})")
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

        # Gera (ou regenera, se a versão do gerador mudou) o startup.blend
        startup = dest / "startup.blend"
        if not startup.exists() or _stored_version() != _TEMPLATE_VERSION:
            if startup.exists():
                print(f"[DAW] startup.blend desatualizado (v{_stored_version()} "
                      f"-> v{_TEMPLATE_VERSION}) -- regenerando...")
            if _generate_startup_blend(dest):
                version_marker.write_text(str(_TEMPLATE_VERSION))

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