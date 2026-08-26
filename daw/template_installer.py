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


def _has_full_edge(a, b, tol=3):
    """
    Verifica se duas áreas compartilham uma borda COMPLETA.
    Retorna (ponto_para_join, area_que_absorve) ou None.
    """
    # a à direita de b  (b.x + b.w == a.x)
    if abs(b.x + b.width - a.x) <= tol:
        y0, y1 = max(a.y, b.y), min(a.y + a.height, b.y + b.height)
        if (y1 - y0) >= min(a.height, b.height) - tol:
            return (int(a.x), int((y0 + y1) // 2)), a

    # a à esquerda de b  (a.x + a.w == b.x)
    if abs(a.x + a.width - b.x) <= tol:
        y0, y1 = max(a.y, b.y), min(a.y + a.height, b.y + b.height)
        if (y1 - y0) >= min(a.height, b.height) - tol:
            return (int(b.x), int((y0 + y1) // 2)), b

    # a acima de b  (a.y == b.y + b.h)
    if abs(a.y - (b.y + b.height)) <= tol:
        x0, x1 = max(a.x, b.x), min(a.x + a.width, b.x + b.width)
        if (x1 - x0) >= min(a.width, b.width) - tol:
            return (int((x0 + x1) // 2), int(a.y)), a

    # a abaixo de b  (a.y + a.h == b.y)
    if abs(a.y + a.height - b.y) <= tol:
        x0, x1 = max(a.x, b.x), min(a.x + a.width, b.x + b.width)
        if (x1 - x0) >= min(a.width, b.width) - tol:
            return (int((x0 + x1) // 2), int(b.y)), b

    return None


def _collapse_to_one_area(window, screen):
    """Funde áreas que compartilham borda completa até sobrar 1."""
    for _ in range(20):
        areas = list(screen.areas)
        if len(areas) <= 1:
            return True

        merged = False
        for i, a in enumerate(areas):
            for b in areas[i + 1:]:
                result = _has_full_edge(a, b)
                if result:
                    point, target = result
                    try:
                        with bpy.context.temp_override(window=window, screen=screen, area=target):
                            bpy.ops.screen.area_join(cursor=point)
                        merged = True
                        break
                    except Exception as e:
                        print(f"[DAW] Join fail {a.type}<-{b.type}: {e}")

            if merged:
                break

        if not merged:
            print(f"[DAW] Colapso parou: {len(areas)} área(s)")
            break

    return len(list(screen.areas)) == 1


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

        # [FIX] Duplica Layout (funciona sempre) e renomeia
        base = bpy.data.workspaces.get('Layout') or bpy.data.workspaces[0]
        with bpy.context.temp_override(workspace=base):
            bpy.ops.workspace.duplicate()

        ws = bpy.context.workspace
        ws.name = "DAW"
        window.workspace = ws

        screen = ws.screens[0]
        print(f"[DAW] Workspace duplicado: {len(screen.areas)} área(s)")

        # Colapsa para 1 área (junta só quem tem borda completa)
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

        # Sempre deleta startup.blend antigo
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