"""
core/register.py
Motor de áudio — bridge com a DLL compilada.
"""

import bpy
import sys
import platform
from pathlib import Path

# ── Caminhos ──────────────────────────────────────────────────
_ADDON_DIR  = Path(__file__).resolve().parent.parent
_PY_DIR     = _ADDON_DIR / "daw_engine" / "daw_engine_final" / "python"
_BIN_DIR    = _ADDON_DIR / "daw_engine" / "daw_engine_final" / "bin"

_LIB = {
    "Windows": _BIN_DIR / "daw_engine.dll",
    "Linux":   _BIN_DIR / "daw_engine.so",
    "Darwin":  _BIN_DIR / "daw_engine.dylib",
}.get(platform.system(), _BIN_DIR / "daw_engine.dll")

# ── Estado global ─────────────────────────────────────────────
_engine = None


def _load_bridge():
    """Importa daw_bridge.py adicionando o caminho ao sys.path."""
    py = str(_PY_DIR)
    if py not in sys.path:
        sys.path.insert(0, py)
    try:
        import daw_bridge
        return daw_bridge
    except ImportError as e:
        print(f"[DAW] daw_bridge não encontrado: {e}")
        return None


def get_engine():
    return _engine


# ── Operadores ────────────────────────────────────────────────

class DAW_OT_EngineInit(bpy.types.Operator):
    bl_idname = "daw.engine_init"
    bl_label  = "Iniciar Motor de Áudio"

    def execute(self, context):
        global _engine
        bridge = _load_bridge()
        if bridge is None:
            self.report({'ERROR'}, f"daw_bridge.py não encontrado em {_PY_DIR}")
            return {'CANCELLED'}

        if not _LIB.exists():
            self.report({'ERROR'},
                f"DLL não encontrada: {_LIB.name}\n"
                "Compile com build.bat dentro de daw_engine_final\\")
            return {'CANCELLED'}

        if _engine is None:
            _engine = bridge.DAWEngine(str(_LIB))
            if not _engine.load():
                _engine = None
                self.report({'ERROR'}, "Falha ao carregar a DLL.")
                return {'CANCELLED'}

        if not _engine.running:
            props = context.scene.daw
            ok = _engine.init(
                sample_rate=props.sample_rate,
                bpm=props.bpm,
                buffer_frames=512,
            )
            if not ok:
                self.report({'ERROR'}, "Falha ao iniciar engine.")
                return {'CANCELLED'}

        self.report({'INFO'}, f"✅ {_engine.version}")
        return {'FINISHED'}


class DAW_OT_EngineShutdown(bpy.types.Operator):
    bl_idname = "daw.engine_shutdown"
    bl_label  = "Desligar Motor de Áudio"

    def execute(self, context):
        global _engine
        if _engine and _engine.running:
            _engine.shutdown()
        _engine = None
        self.report({'INFO'}, "Engine desligado.")
        return {'FINISHED'}


class DAW_OT_EngineStatus(bpy.types.Operator):
    bl_idname = "daw.engine_status"
    bl_label  = "Status do Engine"

    def execute(self, context):
        if _engine and _engine.running:
            s = _engine.get_state()
            p = _engine.get_master_peaks()
            self.report({'INFO'},
                f"✅ Rodando | BPM:{s.bpm:.1f} Tracks:{s.track_count} "
                f"Peak:{p[0]:.2f}/{p[1]:.2f}" if s else "✅ Rodando")
        elif _engine and _engine.loaded:
            self.report({'WARNING'}, "⚠ Carregado mas não iniciado")
        else:
            lib_ok = _LIB.exists()
            self.report({'WARNING'},
                f"{'⚠ DLL encontrada' if lib_ok else '❌ DLL não encontrada'} — "
                "clique 'Iniciar Motor de Áudio'")
        return {'FINISHED'}


class DAW_OT_LoadAudioFile(bpy.types.Operator):
    bl_idname   = "daw.load_audio_file"
    bl_label    = "Carregar Arquivo de Áudio"
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default="*.wav;*.flac;*.mp3;*.ogg", options={'HIDDEN'})

    def execute(self, context):
        e = get_engine()
        if not e or not e.running:
            self.report({'ERROR'}, "Inicie o engine primeiro.")
            return {'CANCELLED'}
        tid = e.track_create(0)
        if tid is None:
            self.report({'ERROR'}, "Falha ao criar track.")
            return {'CANCELLED'}
        if e.track_load_file(tid, self.filepath):
            name = Path(self.filepath).stem
            e.track_set_name(tid, name)
            self.report({'INFO'}, f"✅ '{name}' → Track {tid}")
        else:
            e.track_destroy(tid)
            self.report({'ERROR'}, "Falha ao carregar arquivo.")
            return {'CANCELLED'}
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class DAW_PT_EnginePanel(bpy.types.Panel):
    bl_label      = "Motor de Áudio"
    bl_idname     = "DAW_PT_engine"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type= 'UI'
    bl_category   = "DAW"
    bl_order      = 0

    def draw(self, context):
        layout = self.layout
        e = get_engine()
        lib_ok = _LIB.exists()

        box = layout.box()
        box.label(
            text=f"{'✅' if lib_ok else '❌'} {_LIB.name}",
            icon='CHECKMARK' if lib_ok else 'ERROR')

        if not lib_ok:
            box.label(text="Execute build.bat para compilar", icon='INFO')
            return

        if e and e.running:
            s = _engine.get_state()
            p = _engine.get_master_peaks()
            box.label(text="✅ Engine Ativo", icon='PLAY')
            if s:
                row = box.row()
                row.label(text=f"BPM: {s.bpm:.1f}")
                row.label(text=f"Tracks: {s.track_count}")
                box.label(text=f"Peak  L:{p[0]:.3f}  R:{p[1]:.3f}")
            layout.separator()
            layout.operator("daw.load_audio_file", icon='FILE_SOUND')
            layout.operator("daw.engine_shutdown", icon='X', text="Desligar Engine")
        else:
            layout.operator("daw.engine_init", icon='PLAY',
                           text="Iniciar Motor de Áudio")

        layout.separator()
        col = layout.column(align=True)
        col.scale_y = 0.6
        col.label(text=f"addon: {_ADDON_DIR.name}")
        col.label(text=f"lib: ...\\bin\\{_LIB.name}")


classes = [
    DAW_OT_EngineInit,
    DAW_OT_EngineShutdown,
    DAW_OT_EngineStatus,
    DAW_OT_LoadAudioFile,
    DAW_PT_EnginePanel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    _load_bridge()
    print(f"[DAW] lib: {_LIB} {'✅' if _LIB.exists() else '❌'}")


def unregister():
    global _engine
    if _engine and _engine.running:
        _engine.shutdown()
    _engine = None
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)