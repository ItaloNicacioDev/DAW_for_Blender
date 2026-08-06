"""
ui/panels.py

Interface visual da DAW — Painéis e Barras de Ferramentas.
Apenas desenha os elementos na tela e chama os operadores centrais.

Estado de transporte (play/pause/record, bpm, loop, metrônomo) vem de
`scene.daw_transport` (ver modules/transport/), que já é acionado pelo
player nativo do Blender (bpy.ops.screen.animation_play). Estado de
projeto (nome, sample rate, bit depth) vem de `scene.daw` (ver
core/register.py).
"""

import bpy


def _bar_beat_label(context):
    """Retorna o label 'Compasso:Beat' da posição atual do cursor,
    usando o módulo timeline se disponível. Cai para '1:1' se o módulo
    timeline não estiver registrado (ex.: falhou ao carregar)."""
    try:
        from ..modules.timeline.cursor import get_cursor_beat
        from ..modules.timeline.utils import format_beat_label
        transport = context.scene.daw_transport
        return format_beat_label(get_cursor_beat(context), transport.beats_per_bar)
    except Exception:
        return "1:1"


# ──────────────────────────────────────────────
#  Panel: Transport Bar (aparece no Header do Sequencer)
# ──────────────────────────────────────────────
class DAW_PT_TransportBar(bpy.types.Panel):
    bl_label = "Transport"
    # NOTA: renomeado de "DAW_PT_transport" para evitar colisão de
    # bl_idname com o painel equivalente em modules/transport/ui.py
    # (DAW_PT_transport), que é a implementação completa de
    # transporte usada na aba "DAW" da 3D Viewport.
    bl_idname = "DAW_PT_transport_header_bar"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'HEADER'
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout
        project = context.scene.daw
        transport = context.scene.daw_transport

        row = layout.row(align=True)

        # Projeto
        row.label(text=f"📁 {project.project_name}")
        row.separator()

        # BPM
        row.label(text="BPM:")
        row.prop(transport, "bpm", text="")
        row.separator()

        # Posição
        row.label(text=_bar_beat_label(context))
        row.separator()

        # Botões de transporte (operadores nativos do módulo transport,
        # que usam bpy.ops.screen.animation_play/cancel por baixo)
        sub = row.row(align=True)
        sub.operator("daw.transport_stop", text="", icon='REW')

        play_icon = 'PAUSE' if transport.is_playing else 'PLAY'
        sub.operator("daw.transport_play", text="", icon=play_icon)

        rec_icon = 'CANCEL' if transport.is_recording else 'REC'
        sub.operator("daw.transport_record", text="", icon=rec_icon)

        row.separator()

        # Loop e Metrônomo
        row.prop(transport, "loop_enabled", text="", icon='FILE_REFRESH')
        row.prop(transport, "metronome_enabled", text="", icon='SPEAKER')


# ──────────────────────────────────────────────
#  Panel: DAW Info (N-Panel lateral no Sequencer)
# ──────────────────────────────────────────────
class DAW_PT_ProjectInfo(bpy.types.Panel):
    bl_label = "Projeto DAW"
    bl_idname = "DAW_PT_project_info"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"

    def draw(self, context):
        layout = self.layout
        project = context.scene.daw
        transport = context.scene.daw_transport

        # Info do projeto
        box = layout.box()
        box.label(text="📁 Projeto", icon='FILE_SOUND')
        box.prop(project, "project_name", text="Nome")

        # Configurações de áudio
        box2 = layout.box()
        box2.label(text="⚙ Configurações de Áudio", icon='SETTINGS')
        box2.prop(project, "sample_rate", text="Sample Rate")
        box2.prop(project, "bit_depth", text="Bit Depth")

        # Status
        box3 = layout.box()
        box3.label(text="Status", icon='INFO')
        col = box3.column(align=True)

        status_play = "▶ Reproduzindo" if transport.is_playing else "⏹ Parado"
        col.label(text=status_play)

        if transport.is_recording:
            col.label(text="🔴 Gravando", icon='REC')

        if transport.loop_enabled:
            col.label(text="🔁 Loop ativado")

        # Ações rápidas
        layout.separator()
        layout.label(text="Ações Rápidas:")
        col = layout.column(align=True)
        col.operator("daw.transport_play", icon='PLAY')
        col.operator("daw.transport_stop", icon='QUIT')  # Ícone quadrado padrão de Stop
        col.operator("daw.transport_record", icon='REC')

        layout.separator()
        layout.operator("daw.load_audio", icon='IMPORT')


# ──────────────────────────────────────────────
#  Registro Isolado da UI
# ──────────────────────────────────────────────
classes = [
    DAW_PT_TransportBar,
    DAW_PT_ProjectInfo,
]


def register():
    for cls in classes:
        try: bpy.utils.unregister_class(cls)
        except Exception: pass
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        try: bpy.utils.unregister_class(cls)
        except Exception: pass