import bpy

DAW_WORKSPACE_NAME = "DAW"


def ensure_daw_workspace():
    ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
    if ws is None:
        base = bpy.data.workspaces.get('Layout') or bpy.data.workspaces[0]
        with bpy.context.temp_override(workspace=base):
            bpy.ops.workspace.duplicate()
        ws = bpy.context.workspace
        ws.name = DAW_WORKSPACE_NAME
    return ws


# ═══════════════════════════════════════════════════════════════
#  LAYOUT
#
#  ┌──────────────────────────┬──────────────┐
#  │                          │  PROPERTIES  │
#  │   SEQUENCE_EDITOR (70%)  │    (~65%)    │
#  │                          ├──────────────┤
#  │                          │ FILE_BROWSER │
#  │                          │    (~35%)    │
#  └──────────────────────────┴──────────────┘
# ═══════════════════════════════════════════════════════════════

def _apply_layout(window):
    """Aplica splits no workspace DAW. Requer janela já ativa no workspace."""
    try:
        ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
        if not ws:
            print("[DAW] workspace não encontrado")
            return

        screen = ws.screens[0] if ws.screens else None
        if not screen:
            print("[DAW] screen não encontrado")
            return

        print(f"[DAW] Aplicando layout — {len(screen.areas)} área(s) encontrada(s)")

        # ── Etapa 1: pega a maior área disponível ────────────────
        main = max(screen.areas, key=lambda a: a.width * a.height)
        main.type = 'SEQUENCE_EDITOR'

        win_region = _window_region(main)
        if not win_region:
            print("[DAW] region WINDOW não encontrada")
            return

        # ── Etapa 2: split vertical 70/30 ────────────────────────
        print("[DAW] Split vertical...")
        with bpy.context.temp_override(window=window, screen=screen,
                                       area=main, region=win_region):
            bpy.ops.screen.area_split(direction='VERTICAL', factor=0.70)

        # Identifica esquerda e direita
        sorted_x = sorted(screen.areas, key=lambda a: a.x)
        left  = sorted_x[0]
        right = sorted_x[-1]
        print(f"[DAW] Esquerda: {left.type} | Direita: {right.type}")

        left.type = 'SEQUENCE_EDITOR'
        for sp in left.spaces:
            if sp.type == 'SEQUENCE_EDITOR':
                sp.view_type = 'SEQUENCER'

        # ── Etapa 3: split horizontal na coluna direita 35/65 ─────
        win_right = _window_region(right)
        if not win_right:
            right.type = 'PROPERTIES'
            return

        print("[DAW] Split horizontal na coluna direita...")
        with bpy.context.temp_override(window=window, screen=screen,
                                       area=right, region=win_right):
            bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.35)

        # Identifica cima/baixo na coluna direita
        mid_x = left.x + left.width
        right_col = sorted(
            [a for a in screen.areas if a.x >= mid_x - 10],
            key=lambda a: a.y
        )
        print(f"[DAW] Coluna direita: {len(right_col)} área(s)")

        if len(right_col) >= 2:
            right_col[0].type = 'FILE_BROWSER'
            right_col[-1].type = 'PROPERTIES'
            for sp in right_col[-1].spaces:
                if sp.type == 'PROPERTIES':
                    sp.context = 'OUTPUT'
                    break
            print("[DAW] Layout aplicado com sucesso!")
        elif right_col:
            right_col[0].type = 'PROPERTIES'

    except Exception as e:
        print(f"[DAW] Erro ao aplicar layout: {e}")


def _window_region(area):
    return next((r for r in area.regions if r.type == 'WINDOW'), None)


def _reorder_workspace(ws):
    names = [w.name for w in bpy.data.workspaces]
    if DAW_WORKSPACE_NAME in names:
        idx = names.index(DAW_WORKSPACE_NAME)
        for _ in range(max(0, idx - 1)):
            bpy.ops.workspace.reorder_to_back()


# ═══════════════════════════════════════════════════════════════
#  OPERADOR
# ═══════════════════════════════════════════════════════════════

class DAW_OT_OpenWorkspace(bpy.types.Operator):
    bl_idname      = "daw.open_workspace"
    bl_label       = "Abrir DAW"
    bl_description = "Abre o workspace da DAW"

    def execute(self, context):
        # 1. Cria workspace se necessário
        ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
        if ws is None:
            ws = ensure_daw_workspace()

        # 2. Guarda referência da janela ANTES de trocar
        window = context.window

        # 3. Troca para o workspace DAW
        context.window.workspace = ws
        _reorder_workspace(ws)

        # 4. Aplica layout com delay — guarda window na closure
        def _delayed():
            _apply_layout(window)
            return None  # roda só uma vez

        bpy.app.timers.register(_delayed, first_interval=0.3)
        return {'FINISHED'}


def draw_topbar_daw_button(self, context):
    self.layout.separator()
    self.layout.operator("daw.open_workspace", text="🎵 DAW", icon='SPEAKER')


def register():
    bpy.utils.register_class(DAW_OT_OpenWorkspace)
    bpy.types.TOPBAR_MT_editor_menus.append(draw_topbar_daw_button)


def unregister():
    bpy.types.TOPBAR_MT_editor_menus.remove(draw_topbar_daw_button)
    bpy.utils.unregister_class(DAW_OT_OpenWorkspace)