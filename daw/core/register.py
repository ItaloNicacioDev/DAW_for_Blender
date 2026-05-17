"""
core/register.py

Motor de áudio da DAW — iniciado automaticamente ao ativar o addon.
Fica ativo o tempo todo sem necessidade de interação do usuário.
Reconecta automaticamente se a DLL cair.
"""

import bpy
import os
import sys
import ctypes
import traceback
from pathlib import Path
from bpy.props import FloatProperty, IntProperty, StringProperty, BoolProperty

# ═══════════════════════════════════════════════════════════════
#  SINGLETON DO ENGINE
# ═══════════════════════════════════════════════════════════════

_engine = None          # instância DAWEngine
_engine_ok = False      # True = rodando sem erros
_dll_directory_handle = None  # Guarda o handle do diretório de DLLs do Windows


def get_engine():
    return _engine if _engine_ok else None


def _find_dll() -> Path | None:
    """Procura a DLL em todos os locais possíveis."""
    addon_dir = Path(__file__).resolve().parent.parent  # raiz: addons/daw/
    print(f"[DAW Engine] Buscando DLL em: {addon_dir}")

    candidates = [
        addon_dir / "daw_engine" / "daw_engine_final" / "bin" / "daw_engine.dll",
        addon_dir / "daw_engine" / "daw_engine_final" / "bin" / "daw_engine.so",
        addon_dir / "daw_engine" / "daw_engine_final" / "bin" / "libdaw_engine.so",
        addon_dir / "daw_engine" / "daw_engine_final" / "bin" / "libdaw_engine.dylib",
        addon_dir / "bin" / "daw_engine.dll",
        addon_dir / "bin" / "libdaw_engine.so",
    ]
    for p in candidates:
        exists = p.exists()
        print(f"[DAW Engine]   {p.name}: {'✅' if exists else '✗'}")
        if exists:
            return p

    print(f"[DAW Engine] ⚠ DLL não encontrada. Conteúdo de bin/:")
    bin_dir = addon_dir / "daw_engine" / "daw_engine_final" / "bin"
    if bin_dir.exists():
        for f in bin_dir.iterdir():
            print(f"[DAW Engine]     {f.name}")
    else:
        print(f"[DAW Engine]     pasta bin/ não existe")
    return None


def _preload_deps(dll_path: Path):
    """Pré-carrega o diretório e dependências que daw_engine.dll precisa."""
    global _dll_directory_handle
    if sys.platform != 'win32':
        return

    bin_dir = str(dll_path.parent)

    # Injeta a pasta bin diretamente no buscador de DLLs do Windows para este processo
    if hasattr(os, "add_dll_directory") and _dll_directory_handle is None:
        try:
            _dll_directory_handle = os.add_dll_directory(bin_dir)
            print(f"[DAW Engine] Diretório de DLLs adicionado ao runtime: {bin_dir}")
        except Exception as e:
            print(f"[DAW Engine] Erro ao adicionar add_dll_directory: {e}")

    # Fallback clássico modificando o PATH do ambiente
    if bin_dir not in os.environ.get('PATH', ''):
        os.environ['PATH'] = bin_dir + os.pathsep + os.environ.get('PATH', '')

    # Tenta carregar explicitamente as dependências comuns do MinGW se estiverem na pasta
    deps = ['libwinpthread-1.dll', 'libgcc_s_seh-1.dll', 'libstdc++-6.dll', 'libgomp-1.dll']
    for dep in deps:
        dep_path = dll_path.parent / dep
        if dep_path.exists():
            try:
                ctypes.CDLL(str(dep_path))
                print(f"[DAW Engine] Dependência carregada com sucesso: {dep}")
            except Exception as e:
                print(f"[DAW Engine] Falha interna ao pré-carregar {dep}: {e}")


def _start_engine() -> bool:
    """Inicia o motor de áudio. Retorna True se bem-sucedido."""
    global _engine, _engine_ok

    try:
        dll = _find_dll()
        if dll is None:
            print("[DAW Engine] DLL não encontrada — motor de áudio desativado")
            _engine_ok = False
            return False

        # Configura o ambiente e pré-carrega runtime do C++/MinGW
        _preload_deps(dll)

        # Adiciona o diretório python do seu addon ao sys.path para achar o 'daw_bridge'
        py_dir = dll.parent.parent / "python"
        if str(py_dir) not in sys.path:
            sys.path.insert(0, str(py_dir))

        # Importação dinâmica da ponte python/C++
        from daw_bridge import DAWEngine
        e = DAWEngine(str(dll))

        if not e.init(sample_rate=44100, buffer_size=512):
            print("[DAW Engine] Falha na inicialização interna do motor (init retornou falso)")
            _engine_ok = False
            return False

        e.set_bpm(120.0)
        e.set_master_volume(0.85)

        _engine    = e
        _engine_ok = True
        print(f"[DAW Engine] ✅ Motor iniciado com sucesso — {dll.name}")
        return True

    except Exception as ex:
        print("[DAW Engine] ❌ ERRO CRÍTICO ao iniciar o motor:")
        traceback.print_exc()  # Exibe o erro real e a linha exata no Console do Sistema
        _engine_ok = False
        return False


def _stop_engine():
    """Para o motor com segurança."""
    global _engine, _engine_ok, _dll_directory_handle
    if _engine and _engine_ok:
        try:
            _engine.shutdown()
            print("[DAW Engine] Motor parado")
        except Exception as e:
            print(f"[DAW Engine] Aviso ao parar: {e}")

    # Fecha o handle do diretório do Windows se existir
    if _dll_directory_handle:
        try:
            _dll_directory_handle.close()
        except Exception:
            pass
        _dll_directory_handle = None

    _engine    = None
    _engine_ok = False


# ═══════════════════════════════════════════════════════════════
#  WATCHDOG — mantém o motor vivo
# ═══════════════════════════════════════════════════════════════

def _watchdog():
    """Roda a cada 5s verificando se o motor ainda está ativo."""
    global _engine_ok
    if not _engine_ok:
        print("[DAW Engine] Watchdog: detectou motor offline. Tentando reconectar...")
        _start_engine()
    return 5.0


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

    status: StringProperty(default="Iniciando...")


def _on_bpm_change(self, context):
    e = get_engine()
    if e:
        try: e.set_bpm(self.bpm)
        except Exception: pass


def _on_volume_change(self, context):
    e = get_engine()
    if e:
        try: e.set_master_volume(self.master_volume)
        except Exception: pass


# ═══════════════════════════════════════════════════════════════
#  OPERADORES DE TRANSPORT
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
            try: e.record()
            except Exception: e.play()
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
#  PANEL
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

        box = layout.box()
        row = box.row()
        if _engine_ok:
            row.label(text="Motor: Ativo", icon='CHECKMARK')
        else:
            row.label(text="Motor: Sem DLL", icon='ERROR')
            box.label(text="Verifique o Console do Sistema para detalhes", icon='INFO')

        box2 = layout.box()
        box2.label(text="Configurações", icon='PREFERENCES')
        row2 = box2.row(align=True)
        row2.prop(daw, "bpm", text="BPM")
        box2.prop(daw, "master_volume", text="Volume Master", slider=True)

        box3 = layout.box()
        box3.label(text="Transport", icon='PLAY')
        row3 = box3.row(align=True)
        row3.scale_y = 1.4
        row3.operator("daw.play",   icon='PLAY',           text="")
        row3.operator("daw.stop",   icon='SNAP_FACE_CENTER', text="")
        row3.operator("daw.record", icon='REC',            text="")

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
        try: bpy.utils.unregister_class(cls)
        except Exception: pass
        bpy.utils.register_class(cls)

    bpy.types.Scene.daw = bpy.props.PointerProperty(type=DAWProperties)

    def _auto_start():
        _start_engine()
        if not bpy.app.timers.is_registered(_watchdog):
            bpy.app.timers.register(_watchdog, first_interval=5.0, persistent=True)
        return None

    bpy.app.timers.register(_auto_start, first_interval=0.5)
    print("[DAW Engine] Addon Registrado — Auto-start agendado")


def unregister():
    if bpy.app.timers.is_registered(_watchdog):
        bpy.app.timers.unregister(_watchdog)

    _stop_engine()

    if hasattr(bpy.types.Scene, 'daw'):
        del bpy.types.Scene.daw

    for cls in reversed(classes):
        try: bpy.utils.unregister_class(cls)
        except Exception: pass