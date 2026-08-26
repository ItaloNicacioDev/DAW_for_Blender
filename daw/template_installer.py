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


def _rects_adjacent(a, b, tol=2):
    """Retorna ponto no meio da borda compartilhada entre duas áreas."""
    if abs(a.x + a.width - b.x) <= tol or abs(b.x + b.width - a.x) <= tol:
        y0, y1 = max(a.y, b.y), min(a.y + a.height, b.y + b.height)
        if y1 > y0:
            edge_x = a.x + a.width if a.x + a.width <= b.x + tol else a.x
            return (edge_x, (y0 + y1) // 2)
    if abs(a.y + a.height - b.y) <= tol or abs(b.y + b.height - a.y) <= tol:
        x0, x1 = max(a.x, b.x), min(a.x + a.width, b.x + b.width)
        if x1 > x0:
            edge_y = a.y + a.height if a.y + a.height <= b.y + tol else a.y
            return ((x0 + x1) // 2, edge_y)
    return None


def _collapse_screen_to_single_area(window, screen, max_iters=25):
    """
    [ROBUSTO] Funde TODAS as áreas numa só.
    Estratégia: a área MAIOR sempre absorve a MENOR vizinha.
    """
    for _ in range(max_iters):
        areas = list(screen.areas)
        if len(areas) <= 1:
            return True

        # Ordena por tamanho (maior primeiro) — maior absorve menor
        areas_sorted = sorted(areas, key=lambda a: a.width * a.height, reverse=True)
        main = areas_sorted[0]

        joined = False
        for other in areas_sorted[1:]:
            point = _rects_adjacent(main, other)
            if point is None:
                continue
            try:
                with bpy.context.temp_override(window=window, screen=screen, area=main):
                    bpy.ops.screen.area_join(cursor=point)
                joined = True
                break
            except Exception:
                continue

        if not joined:
            print(f"[DAW] Colapso parou: {len(list(screen.areas))} área(s) restante(s)")
            return False

    return len(list(screen.areas)) == 1


def _generate_startup_blend(dest: Path):
    """
    Gera startup.blend limpo com 1 área DAW.
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

        # Remove DAW antigo
        old = bpy.data.workspaces.get("DAW")
        if old:
            if window.workspace == old:
                fallback = next((w for w in bpy.data.workspaces if w.name != "DAW"), None)
                if fallback:
                    window.workspace = fallback
            with bpy.context.temp_override(workspace=old):
                bpy.ops.workspace.delete()

        # Duplica Layout (geralmente 1 área)
        layout = bpy.data.workspaces.get('Layout') or bpy.data.workspaces[0]
        with bpy.context.temp_override(workspace=layout):
            bpy.ops.workspace.duplicate()

        ws = bpy.context.workspace
        ws.name = "DAW"
        window.workspace = ws

        screen = ws.screens[0]

        # Colapsa se Layout tinha >1 área
        if len(screen.areas) > 1:
            _collapse_screen_to_single_area(window, screen)

        # Configura a área restante como Sequencer
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

        # [CRITICAL] SEMPRE deleta o startup.blend antigo antes de gerar novo
        startup = dest / "startup.blend"
        if startup.exists():
            startup.unlink()
            print("[DAW] startup.blend antigo removido")

        # Gera novo startup.blend
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