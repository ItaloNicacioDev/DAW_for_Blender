import bpy
from bpy.props import FloatProperty, BoolProperty, IntProperty, StringProperty


# ──────────────────────────────────────────────
#  Properties globais da DAW
# ──────────────────────────────────────────────
class DAWProperties(bpy.types.PropertyGroup):
    # Transport
    bpm: FloatProperty(
        name="BPM",
        default=120.0,
        min=20.0,
        max=999.0,
        description="Batidas por minuto"
    )
    is_playing: BoolProperty(name="Tocando", default=False)
    is_recording: BoolProperty(name="Gravando", default=False)
    loop_enabled: BoolProperty(name="Loop", default=False)
    metronome: BoolProperty(name="Metrônomo", default=False)

    # Master
    master_volume: FloatProperty(
        name="Volume Master",
        default=1.0,
        min=0.0,
        max=2.0,
        subtype='FACTOR'
    )

    # Playhead
    current_bar: IntProperty(name="Compasso Atual", default=1, min=1)
    current_beat: IntProperty(name="Beat Atual", default=1, min=1)

    # Projeto
    project_name: StringProperty(name="Projeto", default="Sem Título")
    sample_rate: IntProperty(name="Sample Rate", default=44100)
    bit_depth: IntProperty(name="Bit Depth", default=24)


# ──────────────────────────────────────────────
#  Operadores de Transport
# ──────────────────────────────────────────────
class DAW_OT_Play(bpy.types.Operator):
    bl_idname = "daw.play"
    bl_label = "Play"
    bl_description = "Iniciar reprodução"

    def execute(self, context):
        props = context.scene.daw
        props.is_playing = not props.is_playing
        action = "▶ Reproduzindo" if props.is_playing else "⏸ Pausado"
        self.report({'INFO'}, action)
        return {'FINISHED'}


class DAW_OT_Stop(bpy.types.Operator):
    bl_idname = "daw.stop"
    bl_label = "Stop"
    bl_description = "Parar reprodução e voltar ao início"

    def execute(self, context):
        props = context.scene.daw
        props.is_playing = False
        props.current_bar = 1
        props.current_beat = 1
        self.report({'INFO'}, "⏹ Parado")
        return {'FINISHED'}


class DAW_OT_Record(bpy.types.Operator):
    bl_idname = "daw.record"
    bl_label = "Record"
    bl_description = "Iniciar/parar gravação"

    def execute(self, context):
        props = context.scene.daw
        props.is_recording = not props.is_recording
        action = "🔴 Gravando" if props.is_recording else "⏹ Gravação parada"
        self.report({'INFO'}, action)
        return {'FINISHED'}


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

        # Botões de transporte
        sub = row.row(align=True)
        sub.operator("daw.stop", text="", icon='REW')

        play_icon = 'PAUSE' if props.is_playing else 'PLAY'
        play_text = "Pause" if props.is_playing else "Play"
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

        # Ações rápidas
        layout.separator()
        layout.label(text="Ações Rápidas:")
        col = layout.column(align=True)
        col.operator("daw.play", icon='PLAY')
        col.operator("daw.stop", icon='SNAP_FACE')
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
#  Registro
# ──────────────────────────────────────────────
classes = [
    DAWProperties,
    DAW_OT_Play,
    DAW_OT_Stop,
    DAW_OT_Record,
    DAW_PT_TransportBar,
    DAW_PT_ProjectInfo,
    DAW_PT_MixerPanel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw = bpy.props.PointerProperty(type=DAWProperties)


def unregister():
    del bpy.types.Scene.daw
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)