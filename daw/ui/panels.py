"""
ui/panels.py

Interface visual da DAW — Painéis e Barras de Ferramentas.
Apenas desenha os elementos na tela e chama os operadores centrais.
"""

import bpy

# ──────────────────────────────────────────────
#  Panel: Transport Bar (aparece no Header do Sequencer)
# ──────────────────────────────────────────────
class DAW_PT_TransportBar(bpy.types.Panel):
    bl_label = "Transport"
    bl_idname = "DAW_PT_transport"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'HEADER'
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.daw

        row = layout.row(align=True)

        # Projeto
        row.label(text=f"📁 {props.project_name}")
        row.separator()

        # BPM
        row.label(text="BPM:")
        row.prop(props, "bpm", text="")
        row.separator()

        # Posição
        row.label(text=f"{props.current_bar:03d} | {props.current_beat}")
        row.separator()

        # Botões de transporte (Chamam os operadores do Core)
        sub = row.row(align=True)
        sub.operator("daw.stop", text="", icon='REW')

        play_icon = 'PAUSE' if props.is_playing else 'PLAY'
        sub.operator("daw.play", text="", icon=play_icon)

        rec_icon = 'CANCEL' if props.is_recording else 'REC'
        sub.operator("daw.record", text="", icon=rec_icon)

        row.separator()

        # Loop e Metrônomo
        row.prop(props, "loop_enabled", text="", icon='FILE_REFRESH')
        row.prop(props, "metronome", text="", icon='SPEAKER')

        row.separator()

        # Volume Master
        row.label(text="Master:")
        row.prop(props, "master_volume", text="", slider=True)


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
        props = context.scene.daw

        # Info do projeto
        box = layout.box()
        box.label(text="📁 Projeto", icon='FILE_SOUND')
        box.prop(props, "project_name", text="Nome")

        # Configurações de áudio
        box2 = layout.box()
        box2.label(text="⚙ Configurações de Áudio", icon='SETTINGS')
        box2.prop(props, "sample_rate", text="Sample Rate")
        box2.prop(props, "bit_depth", text="Bit Depth")

        # Status
        box3 = layout.box()
        box3.label(text="Status", icon='INFO')
        col = box3.column(align=True)

        status_play = "▶ Reproduzindo" if props.is_playing else "⏹ Parado"
        col.label(text=status_play)

        if props.is_recording:
            col.label(text="🔴 Gravando", icon='REC')

        if props.loop_enabled:
            col.label(text="🔁 Loop ativado")

        # Ações rápidas (Chamam os operadores do Core)
        layout.separator()
        layout.label(text="Ações Rápidas:")
        col = layout.column(align=True)
        col.operator("daw.play", icon='PLAY')
        col.operator("daw.stop", icon='QUIT')  # Ícone quadrado padrão de Stop
        col.operator("daw.record", icon='REC')


# ──────────────────────────────────────────────
#  Panel: Mixer strip no Node Editor
# ──────────────────────────────────────────────
class DAW_PT_MixerPanel(bpy.types.Panel):
    bl_label = "DAW Mixer"
    bl_idname = "DAW_PT_mixer"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"

    def draw(self, context):
        layout = self.layout
        props = context.scene.daw

        layout.label(text="🎚 Mixer", icon='NLA')
        layout.label(text="(Em desenvolvimento)", icon='INFO')

        box = layout.box()
        box.label(text="Master Bus")
        box.prop(props, "master_volume", text="Volume", slider=True)

        layout.separator()
        layout.label(text="Tracks virão aqui...")


# ──────────────────────────────────────────────
#  Registro Isolado da UI
# ──────────────────────────────────────────────
classes = [
    DAW_PT_TransportBar,
    DAW_PT_ProjectInfo,
    DAW_PT_MixerPanel,
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