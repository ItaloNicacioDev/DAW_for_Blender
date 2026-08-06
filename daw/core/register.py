"""
core/register.py

Propriedades centrais de projeto (scene.daw) e o operador nativo de
carregar áudio pra timeline via VSE (Video Sequence Editor).

Não há mais motor de áudio externo (C++/DLL): a DAW usa o player e o
mixdown nativos do Blender (bpy.ops.screen.animation_play, `aud`, e
strips de som no Sequencer), que já respeitam Blender 4.x+.

O estado de transporte (play/pause/record, bpm, loop) vive em
`scene.daw_transport` (ver modules/transport/) — este arquivo só cuida
de metadado de projeto (nome, sample rate, bit depth) e da ação de
importar um arquivo de áudio pra timeline.
"""

import bpy
from pathlib import Path
from bpy.props import IntProperty, StringProperty


_engine_started = False


def get_engine():
    """Retorna o Mixer ativo do motor Python puro (daw_engine.ENGINE.mixer),
    usado por modules/mixer/utils.py, ui/piano_roll.py etc. Retorna None
    se o motor não estiver disponível/iniciado (aí quem chamou trata
    como "modo local" e segue sem travar).

    O Mixer já expõe set_volume/set_pan/set_mute/set_solo/
    set_master_volume/get_state() — ver daw_engine/mixer/mixer.py.
    """
    if not _engine_started:
        return None
    try:
        from ..daw_engine import ENGINE
        return ENGINE.mixer
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
#  PROPRIEDADES DE PROJETO (metadado — não tem estado de transporte,
#  que vive em scene.daw_transport, ver modules/transport/properties.py)
# ═══════════════════════════════════════════════════════════════

class DAWProperties(bpy.types.PropertyGroup):
    project_name: StringProperty(
        name="Nome do Projeto",
        default="Novo Projeto"
    )

    sample_rate: IntProperty(
        name="Sample Rate",
        default=44100
    )

    bit_depth: IntProperty(
        name="Bit Depth",
        default=24
    )


# ═══════════════════════════════════════════════════════════════
#  CARREGAR ÁUDIO NA TIMELINE (nativo, via VSE)
# ═══════════════════════════════════════════════════════════════

class DAW_OT_LoadAudio(bpy.types.Operator):
    bl_idname      = "daw.load_audio"
    bl_label       = "Carregar Arquivo de Áudio"
    bl_description = "Carrega arquivo WAV/FLAC/MP3 como strip de som na timeline"
    filepath: StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        scene = context.scene
        if scene.sequence_editor is None:
            scene.sequence_editor_create()
        seq = scene.sequence_editor

        channel = 1
        frame_start = scene.frame_current
        audio_name = Path(self.filepath).stem

        try:
            # Blender 4.4+: `strips`. Versões anteriores: `sequences`.
            strips = getattr(seq, "strips", None) or seq.sequences
            strips.new_sound(
                name=audio_name,
                filepath=self.filepath,
                channel=channel,
                frame_start=frame_start,
            )
            self.report({'INFO'}, f"✅ Carregado: {Path(self.filepath).name}")
        except Exception as ex:
            self.report({'ERROR'}, str(ex))
            return {'CANCELLED'}
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  REGISTRO
# ═══════════════════════════════════════════════════════════════

classes = [
    DAWProperties,
    DAW_OT_LoadAudio,
]


def register():
    for cls in classes:
        try: bpy.utils.unregister_class(cls)
        except Exception: pass
        bpy.utils.register_class(cls)

    bpy.types.Scene.daw = bpy.props.PointerProperty(type=DAWProperties)

    # Inicia o motor de síntese em Python puro (clock/transport/mixer).
    # Nunca lança exceção: se algo der errado (ex.: daw_engine ausente
    # ou corrompido), a DAW continua funcionando em "modo local" — só
    # sem os medidores/síntese do motor próprio.
    global _engine_started
    try:
        from ..daw_engine import ENGINE
        ENGINE.start()
        _engine_started = True
    except Exception as e:
        print(f"[DAW] daw_engine indisponível, seguindo em modo local: {e}")
        _engine_started = False


def unregister():
    global _engine_started
    if _engine_started:
        try:
            from ..daw_engine import ENGINE
            ENGINE.shutdown()
        except Exception as e:
            print(f"[DAW] Erro ao encerrar daw_engine: {e}")
        _engine_started = False

    if hasattr(bpy.types.Scene, 'daw'):
        del bpy.types.Scene.daw

    for cls in reversed(classes):
        try: bpy.utils.unregister_class(cls)
        except Exception: pass