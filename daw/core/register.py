"""
core/register.py

Motor de áudio da DAW — iniciado automaticamente ao ativar o addon.
Fica ativo o tempo todo sem necessidade de interação do usuário.
Reconecta automaticamente se a DLL cair.
"""

import bpy
import os
import sys
from pathlib import Path
from bpy.props import FloatProperty, IntProperty, StringProperty, BoolProperty

# ═══════════════════════════════════════════════════════════════
#  SINGLETON DO ENGINE
# ═══════════════════════════════════════════════════════════════

_engine = None          # instância DAWEngine
_engine_ok = False      # True = rodando sem erros


def get_engine():
    return _engine if _engine_ok else None


def _find_dll() -> Path | None:
    """Procura a DLL em todos os locais possíveis."""
    addon_dir = Path(__file__).parent.parent  # raiz do addon daw/

    candidates = [
        addon_dir / "daw_engine" / "daw_engine_final" / "bin" / "daw_engine.dll",
        addon_dir / "daw_engine" / "daw_engine_final" / "bin" / "libdaw_engine.so",
        addon_dir / "daw_engine" / "daw_engine_final" / "bin" / "libdaw_engine.dylib",
        addon_dir / "bin" / "daw_engine.dll",
        addon_dir / "bin" / "libdaw_engine.so",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _start_engine() -> bool:
    """Inicia o motor de áudio. Retorna True se bem-sucedido."""
    global _engine, _engine_ok

    try:
        dll = _find_dll()
        if dll is None:
            print("[DAW Engine] DLL não encontrada — motor de áudio desativado")
            print(f"[DAW Engine] Procurado em: {Path(__file__).parent.parent}")
            _engine_ok = False
            return False

        # Adiciona o diretório python ao sys.path
        py_dir = dll.parent.parent / "python"
        if str(py_dir) not in sys.path:
            sys.path.insert(0, str(py_dir))

        from daw_bridge import DAWEngine
        e = DAWEngine(str(dll))

        if not e.init(sample_rate=44100, buffer_size=512):
            print("[DAW Engine] Falha na inicialização do motor")
            _engine_ok = False
            return False

        e.set_bpm(120.0)
        e.set_master_volume(0.85)

        _engine    = e
        _engine_ok = True
        print(f"[DAW Engine] ✅ Motor iniciado — {dll.name}")
        return True

    except Exception as ex:
        print(f"[DAW Engine] Erro ao iniciar: {ex}")
        _engine_ok = False
        return False


def _stop_engine():
    """Para o motor com segurança."""
    global _engine, _engine_ok
    if _engine and _engine_ok:
        try:
            _engine.shutdown()
            print("[DAW Engine] Motor parado")
        except Exception as e:
            print(f"[DAW Engine] Aviso ao parar: {e}")
    _engine    = None
    _engine_ok = False


# ═══════════════════════════════════════════════════════════════
#  WATCHDOG — mantém o motor vivo
# ═══════════════════════════════════════════════════════════════

def _watchdog():
    """
    Roda a cada 5s verificando se o motor ainda está ativo.
    Se caiu, tenta reiniciar automaticamente.
    """
    global _engine_ok
    if not _engine_ok:
        print("[DAW Engine] Watchdog: tentando reconectar...")
        _start_engine()
    return 5.0  # re-agenda para daqui 5s


# ═══════════════════════════════════════════════════════════════
#  PROPRIEDADES DA CENA
# ═══════════════════════════════════════════════════════════════

class DAWProperties(bpy.types.PropertyGroup):
    bpm: FloatProperty(
        name="BPM", default=120.0, min=20.0, max=300.0,
        update=lambda self, ctx: _on_bpm_change(self, ctx))

    master_volume: FloatProperty(
        name="Volume", default=0.85, min=0.0, max=1.0,
        update=lambda self, ctx: _on_volume_change(self, ctx))

    def _transport_update(self, ctx): pass

    status: StringProperty(default="Iniciando...")


def _on_bpm_change(self, context):
    e = get_engine()
    if e:
        try:
            e.set_bpm(self.bpm)
        except Exception:
            pass


def _on_volume_change(self, context):
    e = get_engine()
    if e:
        try:
            e.set_master_volume(self.master_volume)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  OPERADORES DE TRANSPORT  (play/pause/stop sem botão de init)
# ═══════════════════════════════════════════════════════════════

class DAW_OT_Play(bpy.types.Operator):
    bl_idname = "daw.play"
    bl_label  = "Play"
    bl_description = "Iniciar reprodução"

    def execute(self, context):
        e = get_engine()
        if e:
            e.play()
            self.report({'INFO'}, "▶ Play")
        else:
            self.report({'WARNING'}, "Motor de áudio não disponível")
        return {'FINISHED'}


class DAW_OT_Stop(bpy.types.Operator):
    bl_idname = "daw.stop"
    bl_label  = "Stop"
    bl_description = "Parar reprodução"

    def execute(self, context):
        e = get_engine()
        if e:
            e.stop()
            self.report({'INFO'}, "■ Stop")
        return {'FINISHED'}


class DAW_OT_Record(bpy.types.Operator):
    bl_idname = "daw.record"
    bl_label  = "Record"
    bl_description = "Iniciar gravação"

    def execute(self, context):
        e = get_engine()
        if e:
            try:
                e.record()
            except Exception:
                e.play()
            self.report({'INFO'}, "● Record")
        else:
            self.report({'WARNING'}, "Motor de áudio não disponível")
        return {'FINISHED'}


class DAW_OT_LoadAudio(bpy.types.Operator):
    bl_idname      = "daw.load_audio"
    bl_label       = "Carregar Arquivo de Áudio"
    bl_description = "Carrega arquivo WAV/FLAC/MP3"
    filepath: StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        e = get_engine()
        if not e:
            self.report({'ERROR'}, "Motor não disponível")
            return {'CANCELLED'}
        try:
            track_id = e.add_track("Audio", 0)
            e.load_audio(track_id, self.filepath)
            self.report({'INFO'}, f"✅ Carregado: {Path(self.filepath).name}")
        except Exception as ex:
            self.report({'ERROR'}, str(ex))
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  PANEL  (status do motor + transport)
# ═══════════════════════════════════════════════════════════════

class DAW_PT_Engine(bpy.types.Panel):
    bl_label       = "Projeto DAW"
    bl_idname      = "DAW_PT_engine"
    bl_space_type  = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category    = "DAW"
    bl_order       = 0

    def draw(self, context):
        layout = self.layout
        daw    = context.scene.daw

        # ── Status do motor ───────────────────────────────────
        box = layout.box()
        row = box.row()
        if _engine_ok:
            row.label(text="Motor: Ativo", icon='CHECKMARK')
        else:
            row.label(text="Motor: Sem DLL", icon='ERROR')
            box.label(text="Compile daw_engine.dll", icon='INFO')

        # ── BPM e Volume ──────────────────────────────────────
        box2 = layout.box()
        box2.label(text="Configurações", icon='PREFERENCES')
        row2 = box2.row(align=True)
        row2.prop(daw, "bpm", text="BPM")
        box2.prop(daw, "master_volume", text="Volume Master", slider=True)

        # ── Transport ─────────────────────────────────────────
        box3 = layout.box()
        box3.label(text="Transport", icon='PLAY')
        row3 = box3.row(align=True)
        row3.scale_y = 1.4
        row3.operator("daw.play",   icon='PLAY',           text="")
        row3.operator("daw.stop",   icon='SNAP_FACE_CENTER', text="")
        row3.operator("daw.record", icon='REC',            text="")

        # ── VU Meter ──────────────────────────────────────────
        if _engine_ok and _engine:
            try:
                s = _engine.get_state()
                if s:
                    box4 = layout.box()
                    box4.label(text=f"Peak  L:{s.peak_left:.3f}  R:{s.peak_right:.3f}")
                    box4.label(text=f"BPM: {s.bpm:.1f}  Tracks: {s.track_count}")
            except Exception:
                pass

        layout.separator()
        layout.operator("daw.load_audio", icon='FILE_SOUND')


# ═══════════════════════════════════════════════════════════════
#  REGISTRO
# ═══════════════════════════════════════════════════════════════

classes = [
    DAWProperties,
    DAW_OT_Play, DAW_OT_Stop, DAW_OT_Record, DAW_OT_LoadAudio,
    DAW_PT_Engine,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.daw = bpy.props.PointerProperty(type=DAWProperties)

    # Inicia o motor automaticamente com delay de 0.5s
    # (garante que o Blender terminou de carregar)
    def _auto_start():
        _start_engine()
        # Ativa o watchdog após o primeiro start
        if not bpy.app.timers.is_registered(_watchdog):
            bpy.app.timers.register(_watchdog, first_interval=5.0, persistent=True)
        return None

    bpy.app.timers.register(_auto_start, first_interval=0.5)
    print("[DAW Engine] Auto-start agendado")


def unregister():
    # Para watchdog
    if bpy.app.timers.is_registered(_watchdog):
        bpy.app.timers.unregister(_watchdog)

    # Para o motor
    _stop_engine()

    if hasattr(bpy.types.Scene, 'daw'):
        del bpy.types.Scene.daw

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)