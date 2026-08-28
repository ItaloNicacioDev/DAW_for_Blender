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
_TEMPLATE_VERSION = 3


def _get_template_dest() -> Path:
    """Retorna o caminho de destino do template no Blender do usuário."""
    # Caminho padrão: scripts/startup/bl_app_templates_user/DAW/
    scripts = Path(bpy.utils.resource_path('USER')) / "scripts"
    return scripts / "startup" / "bl_app_templates_user" / "DAW"


def _get_template_src() -> Path:
    """Retorna a pasta template/ que está dentro do addon."""
    return Path(__file__).parent / "template" / "DAW"


def _collapse_screen_to_single_area(window, screen, max_iters: int = 60) -> bool:
    """[FIX WORKSPACE QUÁDRUPLO] Funde TODAS as áreas da tela numa única
    área. Sem isso, `_generate_startup_blend` estava convertendo cada
    área que o Blender já tinha por padrão (viewport 3D, timeline,
    outliner, propriedades -- normalmente 4) em Sequence Editor,
    mantendo as divisões originais -- daí o layout "quádruplo" salvo
    no startup.blend.

    [FIX v2] A primeira versão calculava a borda compartilhada exata
    entre duas áreas (`a.x + a.width == b.x`) e passava esse ponto pro
    operador -- mas isso depende de coordenadas de área já finalizadas
    e sem nenhum arredondamento, o que nem sempre é verdade no momento
    em que o template está sendo gerado (a tela pode não ter passado
    por um layout/redraw completo ainda). Resultado: nenhum par batia
    a igualdade exata, e nada era fundido.

    Esta versão é mais robusta: pra cada área, tenta o operador com o
    cursor em cada uma das 4 bordas DA PRÓPRIA área (não precisa saber
    qual é a vizinha) -- é o operador que decide com quem fundir a
    partir de onde o cursor está, igual a arrastar a borda na
    interface. Confirma sucesso comparando a contagem de áreas antes/
    depois de cada tentativa, em vez de confiar em não ter dado
    exceção."""
    for _ in range(max_iters):
        areas = list(screen.areas)
        if len(areas) <= 1:
            return True

        before = len(areas)
        progressed = False

        for a in areas:
            candidates = [
                (a.x + 1,              a.y + a.height // 2),   # borda esquerda
                (a.x + a.width - 1,    a.y + a.height // 2),   # borda direita
                (a.x + a.width // 2,   a.y + 1),               # borda inferior
                (a.x + a.width // 2,   a.y + a.height - 1),    # borda superior
            ]
            for cx, cy in candidates:
                try:
                    with bpy.context.temp_override(window=window, screen=screen, area=a):
                        bpy.ops.screen.area_join(cursor=(cx, cy))
                except Exception as e:
                    print(f"[DAW] area_join({cx},{cy}) falhou: {e}")
                    continue

                if len(screen.areas) < before:
                    progressed = True
                    break
            if progressed:
                break

        if not progressed:
            print(f"[DAW] Aviso: não consegui fundir todas as áreas "
                  f"({len(list(screen.areas))} restante(s))")
            return False

    return len(list(screen.areas)) <= 1


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