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


def _get_join_point(a, b, tol=10):
    """
    Retorna ponto na borda compartilhada entre duas áreas adjacentes.
    Tolerância alta para headers/toolbars do Blender 5.x.
    """
    # a à direita de b
    if abs(b.x + b.width - a.x) <= tol:
        y0, y1 = max(a.y, b.y), min(a.y + a.height, b.y + b.height)
        if y1 > y0:
            return (int((max(b.x + b.width, a.x) + min(b.x + b.width, a.x)) // 2), int((y0 + y1) // 2))
    # a à esquerda de b
    if abs(a.x + a.width - b.x) <= tol:
        y0, y1 = max(a.y, b.y), min(a.y + a.height, b.y + b.height)
        if y1 > y0:
            return (int((max(a.x + a.width, b.x) + min(a.x + a.width, b.x)) // 2), int((y0 + y1) // 2))
    # a acima de b
    if abs(a.y + a.height - b.y) <= tol:
        x0, x1 = max(a.x, b.x), min(a.x + a.width, b.x + b.width)
        if x1 > x0:
            return (int((x0 + x1) // 2), int((max(a.y + a.height, b.y) + min(a.y + a.height, b.y)) // 2))
    # a abaixo de b
    if abs(b.y + b.height - a.y) <= tol:
        x0, x1 = max(a.x, b.x), min(a.x + a.width, b.x + b.width)
        if x1 > x0:
            return (int((x0 + x1) // 2), int((max(b.y + b.height, a.y) + min(b.y + b.height, a.y)) // 2))
    return None


def _collapse_to_one_area(window, screen):
    """Funde áreas adjacentes até sobrar 1."""
    for _ in range(25):
        areas = list(screen.areas)
        if len(areas) <= 1:
            return True

        merged = False
        # Ordena por tamanho decrescente — maior absorve menor
        areas_sorted = sorted(areas, key=lambda a: a.width * a.height, reverse=True)

        for target in areas_sorted:
            for other in areas_sorted:
                if target == other:
                    continue
                point = _get_join_point(target, other)
                if point:
                    try:
                        with bpy.context.temp_override(window=window, screen=screen, area=target):
                            bpy.ops.screen.area_join(cursor=point)
                        merged = True
                        break
                    except Exception:
                        pass
            if merged:
                break

        if not merged:
            print(f"[DAW] Colapso parou: {len(list(screen.areas))} área(s)")
            break

    return len(list(screen.areas)) == 1


def _remove_extra_workspaces():
    """Remove todos os workspaces exceto DAW."""
    daw_ws = bpy.data.workspaces.get("DAW")
    if not daw_ws:
        return

    # Garante que todas as janelas estejam no DAW antes de deletar
    for w in bpy.context.window_manager.windows:
        if w.workspace != daw_ws:
            w.workspace = daw_ws

    # Deleta um por um
    for ws in list(bpy.data.workspaces):
        if ws.name == "DAW":
            continue
        try:
            with bpy.context.temp_override(workspace=ws):
                bpy.ops.workspace.delete()
            print(f"[DAW] Workspace removido: {ws.name}")
        except Exception as e:
            print(f"[DAW] Não removeu {ws.name}: {e}")


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

        # Duplica Layout (funciona sempre)
        base = bpy.data.workspaces.get('Layout') or bpy.data.workspaces[0]
        with bpy.context.temp_override(workspace=base):
            bpy.ops.workspace.duplicate()

        ws = bpy.context.workspace
        ws.name = "DAW"
        window.workspace = ws

        screen = ws.screens[0]
        print(f"[DAW] Workspace duplicado: {len(screen.areas)} área(s)")

        # Colapsa para 1 área
        if len(screen.areas) > 1:
            ok = _collapse_to_one_area(window, screen)
            print(f"[DAW] Colapso: {'OK' if ok else 'parcial'} — {len(screen.areas)} área(s)")

        # Configura como Sequencer
        for area in screen.areas:
            area.type = 'SEQUENCE_EDITOR'
            for sp in area.spaces:
                if sp.type == 'SEQUENCE_EDITOR':
                    sp.view_type = 'SEQUENCER'

        # Remove workspaces extras
        _remove_extra_workspaces()

        # Salva
        startup_path = str(dest / "startup.blend")
        bpy.ops.wm.save_as_mainfile(filepath=startup_path)
        final_areas = len(screen.areas)
        final_type = screen.areas[0].type if screen.areas else 'none'
        print(f"[DAW] startup.blend: {startup_path} ({final_areas} área, {final_type})")
        print(f"[DAW] Workspaces restantes: {[w.name for w in bpy.data.workspaces]}")
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