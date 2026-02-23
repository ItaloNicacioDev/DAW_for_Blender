import bpy

DAW_WORKSPACE_NAME = "DAW"


def ensure_daw_workspace():
    """Cria o workspace DAW se não existir e configura as áreas."""
    ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)

    if ws is None:
        # Duplica o workspace Layout como base
        bpy.ops.workspace.duplicate({'workspace': bpy.data.workspaces['Layout']})
        ws = bpy.context.workspace
        ws.name = DAW_WORKSPACE_NAME

    # Configura o layout das áreas dentro do workspace
    _setup_daw_layout(ws)

    # Move o workspace DAW para ser o segundo (logo após Layout)
    _reorder_workspace(ws)


def _setup_daw_layout(ws):
    """
    Define o layout de áreas do workspace DAW.

    Layout planejado:
    ┌─────────────────────────────────────┐
    │           TRANSPORT BAR             │  ← Header customizado (N panel)
    ├──────────────┬──────────────────────┤
    │              │                      │
    │  PIANO ROLL  │    ARRANGER /        │
    │  (VIEW_3D    │    TIMELINE          │
    │   custom)    │    (SEQUENCER)       │
    │              │                      │
    ├──────────────┴──────────────────────┤
    │           MIXER                     │
    │        (NODE_EDITOR)                │
    └─────────────────────────────────────┘
    """
    screen = ws.screens[0] if ws.screens else None
    if screen is None:
        return

    areas = screen.areas

    # Tenta configurar cada área para o tipo correto
    # O layout exato depende de quantas áreas existem na tela
    _configure_areas(screen)


def _configure_areas(screen):
    """Configura os tipos de cada área para montar o layout da DAW."""
    areas = list(screen.areas)

    if len(areas) == 0:
        return

    # Área principal → Sequencer (Arranger/Timeline)
    main_area = areas[0]
    main_area.type = 'SEQUENCE_EDITOR'

    # Se houver mais de uma área, configura as outras
    if len(areas) > 1:
        areas[1].type = 'NODE_EDITOR'  # Mixer via nodes

    if len(areas) > 2:
        areas[2].type = 'VIEW_3D'  # Piano Roll (futuramente custom)

    # Garante que o header do Sequencer seja visível
    for area in areas:
        for region in area.regions:
            if region.type == 'HEADER':
                region.height  # acessa para garantir que está ativo


def _reorder_workspace(ws):
    """Tenta posicionar o workspace DAW logo após o Layout."""
    workspaces = list(bpy.data.workspaces)
    names = [w.name for w in workspaces]

    if DAW_WORKSPACE_NAME in names:
        idx = names.index(DAW_WORKSPACE_NAME)
        # Move para posição 1 (após Layout)
        for _ in range(max(0, idx - 1)):
            bpy.ops.workspace.reorder_to_back()


# ──────────────────────────────────────────────
#  Operador: abrir workspace DAW manualmente
# ──────────────────────────────────────────────
class DAW_OT_OpenWorkspace(bpy.types.Operator):
    bl_idname = "daw.open_workspace"
    bl_label = "Abrir DAW"
    bl_description = "Abre o workspace da DAW"

    def execute(self, context):
        ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)
        if ws is None:
            ensure_daw_workspace()
            ws = bpy.data.workspaces.get(DAW_WORKSPACE_NAME)

        if ws:
            context.window.workspace = ws
            self.report({'INFO'}, "Workspace DAW aberto!")
        else:
            self.report({'ERROR'}, "Não foi possível criar o workspace DAW.")

        return {'FINISHED'}


# ──────────────────────────────────────────────
#  Botão na splash screen / topbar
# ──────────────────────────────────────────────
def draw_topbar_daw_button(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("daw.open_workspace", text="🎵 DAW", icon='SPEAKER')


def register():
    bpy.utils.register_class(DAW_OT_OpenWorkspace)
    bpy.types.TOPBAR_MT_editor_menus.append(draw_topbar_daw_button)


def unregister():
    bpy.types.TOPBAR_MT_editor_menus.remove(draw_topbar_daw_button)
    bpy.utils.unregister_class(DAW_OT_OpenWorkspace)