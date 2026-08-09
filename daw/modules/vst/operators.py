# modules/vst/operators.py
"""
Operators do Blender para o módulo VST.

Melhorias implementadas em relação à versão anterior:
    - DAW_OT_MoveVstEffect: move plugins up/down na cadeia (reorder real)
    - DAW_OT_ScanVstDirectoriesAsync: scan de diretórios em background thread
      (não trava a UI — usa bpy.app.timers para atualizar o resultado)
    - DAW_OT_AutoBounceVstInstrument: bounce automático disparado por mudança
      de parâmetro VST (registrado como handler de depsgraph)
    - DAW_OT_ToggleVstLiveMonitoring: liga/desliga processamento de efeitos
      VST sobre o input do microfone em tempo real (via thread de áudio)
    - DAW_OT_DeleteVstPreset: deleta preset salvo pelo usuário
    - DAW_OT_ExportVstPresetLibrary / DAW_OT_ImportVstPresetLibrary:
      exportar/importar biblioteca de presets como .zip
"""
from __future__ import annotations

import os
import threading
import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty
from bpy.types import Operator

from . import timeline_bridge as tlb
from .vst import VSTProgramType
from .pressets import get_preset_manager
from .utils import (
    get_or_create_chain,
    get_or_create_live_vst,
    get_live_vst,
    register_live_vst,
    unregister_live_vst,
    sync_rna_from_pure,
    sync_pure_bypass,
    make_unique_vst_id,
    scan_multiple_directories,
    clamp_index,
)
from .live_monitor import get_live_monitor, LiveMonitorState


def _settings(context):
    return context.scene.daw_vst


def _sample_rate(context) -> int:
    daw_props = getattr(context.scene, "daw", None)
    return int(daw_props.sample_rate) if daw_props else 44100


def _active_channel_index(context) -> int:
    rack_props = getattr(context.scene, "daw_channel_rack", None)
    if rack_props is not None:
        return rack_props.active_channel_index
    return 0


def _add_vst_item(collection, path: str, name: str, vst_type: str, existing_ids):
    item = collection.add()
    item.vst_path = path
    item.vst_name = name
    item.vst_id = make_unique_vst_id(name, existing_ids)
    item.vst_type = vst_type
    return item


def _load_item(item, context) -> bool:
    """Carrega o plugin real para um item RNA e sincroniza o estado de volta."""
    vst = get_or_create_live_vst(item)
    ok = vst.load(sample_rate=_sample_rate(context))
    sync_rna_from_pure(item, vst)
    return ok


# ---------------------------------------------------------------------- #
# Varredura SÍNCRONA (mantida para compatibilidade)
# ---------------------------------------------------------------------- #
class DAW_OT_ScanVstDirectories(Operator):
    bl_idname = "daw.scan_vst_directories"
    bl_label = "Escanear VSTs"
    bl_description = "Varre os diretórios configurados em busca de plugins VST2/VST3"
    bl_options = {'REGISTER'}

    def execute(self, context):
        browser = context.scene.daw_vst_browser
        settings = _settings(context)

        browser.is_scanning = True
        try:
            found = scan_multiple_directories(settings.vst_directories, recursive=True)
        finally:
            browser.is_scanning = False

        browser.discovered_vsts.clear()
        existing_ids = []
        for entry in found:
            item = browser.discovered_vsts.add()
            item.vst_path = entry["path"]
            item.vst_name = entry["name"]
            item.vst_id = make_unique_vst_id(entry["name"], existing_ids)
            existing_ids.append(item.vst_id)
            item.vst_type = "EFFECT"

        self.report({'INFO'}, f"{len(found)} plugin(s) encontrado(s)")
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Varredura ASSÍNCRONA (não trava a UI)
# ---------------------------------------------------------------------- #
class DAW_OT_ScanVstDirectoriesAsync(Operator):
    """
    Scan em background thread — a UI continua responsiva.
    Usa bpy.app.timers para aplicar o resultado na thread principal
    (única thread permitida a tocar em RNA/bpy.types).
    """
    bl_idname = "daw.scan_vst_directories_async"
    bl_label = "Escanear VSTs (Assíncrono)"
    bl_description = (
        "Varre diretórios em background — a UI não trava. "
        "O resultado aparece automaticamente quando terminar."
    )
    bl_options = {'REGISTER'}

    def execute(self, context):
        settings = _settings(context)
        browser = context.scene.daw_vst_browser

        if browser.is_scanning:
            self.report({'WARNING'}, "Scan já em andamento")
            return {'CANCELLED'}

        directories = settings.vst_directories
        browser.is_scanning = True

        _result_holder: list = []  # [List[Dict]] preenchido pela thread

        def _scan_thread():
            found = scan_multiple_directories(directories, recursive=True)
            _result_holder.append(found)

        def _apply_result():
            if not _result_holder:
                return 0.1  # ainda rodando — re-agenda em 100ms

            found = _result_holder[0]
            try:
                br = bpy.context.scene.daw_vst_browser
                br.discovered_vsts.clear()
                existing_ids = []
                for entry in found:
                    item = br.discovered_vsts.add()
                    item.vst_path = entry["path"]
                    item.vst_name = entry["name"]
                    item.vst_id = make_unique_vst_id(entry["name"], existing_ids)
                    existing_ids.append(item.vst_id)
                    item.vst_type = "EFFECT"
                br.is_scanning = False
                # Força redraw do painel
                for area in bpy.context.screen.areas:
                    area.tag_redraw()
            except Exception as e:
                print(f"[DAW VST] Erro ao aplicar resultado do scan: {e}")
            return None  # cancela o timer

        threading.Thread(target=_scan_thread, daemon=True).start()
        bpy.app.timers.register(_apply_result, first_interval=0.2)

        self.report({'INFO'}, "Scan iniciado em background...")
        return {'FINISHED'}


class DAW_OT_PickVstDirectory(Operator):
    bl_idname = "daw.pick_vst_directory"
    bl_label = "Escolher Pasta de VSTs"
    bl_description = "Adiciona uma pasta à lista de diretórios de busca de VST"
    directory: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = _settings(context)
        current = [d for d in settings.vst_directories.split(";") if d.strip()]
        if self.directory not in current:
            current.append(self.directory)
        settings.vst_directories = ";".join(current)
        self.report({'INFO'}, f"Pasta adicionada: {self.directory}")
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Cadeia de efeitos VST (por canal)
# ---------------------------------------------------------------------- #
class DAW_OT_AddVstEffect(Operator):
    bl_idname = "daw.add_vst_effect"
    bl_label = "Adicionar VST (Efeito)"
    bl_description = "Adiciona um VST descoberto à cadeia de efeitos do canal ativo, como efeito"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    vst_path: StringProperty(default="")
    vst_name: StringProperty(default="")

    def execute(self, context):
        channel_index = self.channel_index if self.channel_index >= 0 else _active_channel_index(context)
        chain = get_or_create_chain(context.scene, channel_index)

        existing_ids = [v.vst_id for v in chain.vsts]
        item = _add_vst_item(chain.vsts, self.vst_path, self.vst_name, "EFFECT", existing_ids)
        chain.active_vst_index = len(chain.vsts) - 1

        ok = _load_item(item, context)
        if ok:
            self.report({'INFO'}, f"VST '{item.vst_name}' carregado como efeito")
        else:
            self.report({'WARNING'}, item.error_message or "Falha ao carregar VST")
        return {'FINISHED'}


class DAW_OT_RemoveVstEffect(Operator):
    bl_idname = "daw.remove_vst_effect"
    bl_label = "Remover VST (Efeito)"
    bl_description = "Remove o VST selecionado da cadeia de efeitos do canal"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    vst_index: IntProperty(default=-1)

    def execute(self, context):
        channel_index = self.channel_index if self.channel_index >= 0 else _active_channel_index(context)
        chain = get_or_create_chain(context.scene, channel_index)
        index = self.vst_index if self.vst_index >= 0 else chain.active_vst_index
        if not (0 <= index < len(chain.vsts)):
            return {'CANCELLED'}

        vst_id = chain.vsts[index].vst_id
        live = get_live_vst(vst_id)
        if live is not None:
            live.unload()
        unregister_live_vst(vst_id)

        chain.vsts.remove(index)
        chain.active_vst_index = clamp_index(chain.active_vst_index, len(chain.vsts))
        return {'FINISHED'}


class DAW_OT_MoveVstEffect(Operator):
    """
    Move um VST de efeito para cima ou para baixo na cadeia do canal.
    Isso define a ordem de processamento do sinal (como numa DAW real:
    o primeiro slot recebe o áudio cru, cada slot seguinte recebe a
    saída do anterior).
    """
    bl_idname = "daw.move_vst_effect"
    bl_label = "Mover VST na Cadeia"
    bl_description = "Move o VST selecionado para cima ou para baixo na ordem de processamento"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    vst_index: IntProperty(default=-1)
    direction: EnumProperty(
        name="Direção",
        items=[("UP", "Para Cima", ""), ("DOWN", "Para Baixo", "")],
        default="UP",
    )

    def execute(self, context):
        channel_index = self.channel_index if self.channel_index >= 0 else _active_channel_index(context)
        chain = get_or_create_chain(context.scene, channel_index)
        index = self.vst_index if self.vst_index >= 0 else chain.active_vst_index

        if self.direction == "UP" and index > 0:
            chain.vsts.move(index, index - 1)
            chain.active_vst_index = index - 1
        elif self.direction == "DOWN" and index < len(chain.vsts) - 1:
            chain.vsts.move(index, index + 1)
            chain.active_vst_index = index + 1
        else:
            return {'CANCELLED'}

        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Rack de instrumentos VST
# ---------------------------------------------------------------------- #
class DAW_OT_AddVstInstrument(Operator):
    bl_idname = "daw.add_vst_instrument"
    bl_label = "Adicionar VST (Instrumento)"
    bl_description = "Adiciona um VST descoberto ao rack de instrumentos, como instrumento MIDI"
    bl_options = {'REGISTER', 'UNDO'}

    vst_path: StringProperty(default="")
    vst_name: StringProperty(default="")

    def execute(self, context):
        rack = context.scene.daw_vst_instruments
        existing_ids = [v.vst_id for v in rack.instruments]
        item = _add_vst_item(rack.instruments, self.vst_path, self.vst_name, "INSTRUMENT", existing_ids)

        ok = _load_item(item, context)
        if ok:
            self.report({'INFO'}, f"VST '{item.vst_name}' carregado como instrumento")
        else:
            self.report({'WARNING'}, item.error_message or "Falha ao carregar VST")
        return {'FINISHED'}


class DAW_OT_RemoveVstInstrument(Operator):
    bl_idname = "daw.remove_vst_instrument"
    bl_label = "Remover VST (Instrumento)"
    bl_description = "Remove o instrumento VST selecionado do rack"
    bl_options = {'REGISTER', 'UNDO'}

    vst_index: IntProperty(default=-1)

    def execute(self, context):
        rack = context.scene.daw_vst_instruments
        index = self.vst_index if self.vst_index >= 0 else rack.active_channel
        if not (0 <= index < len(rack.instruments)):
            return {'CANCELLED'}

        vst_id = rack.instruments[index].vst_id
        live = get_live_vst(vst_id)
        if live is not None:
            live.unload()
        unregister_live_vst(vst_id)

        rack.instruments.remove(index)
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Ações comuns: bypass, reload, parâmetros
# ---------------------------------------------------------------------- #
class DAW_OT_ToggleVstBypass(Operator):
    bl_idname = "daw.toggle_vst_bypass"
    bl_label = "Bypass VST"
    bl_description = "Ativa/desativa o bypass deste VST"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    vst_index: IntProperty(default=-1)
    is_instrument: BoolProperty(default=False)

    def execute(self, context):
        if self.is_instrument:
            rack = context.scene.daw_vst_instruments
            if not (0 <= self.vst_index < len(rack.instruments)):
                return {'CANCELLED'}
            item = rack.instruments[self.vst_index]
        else:
            channel_index = self.channel_index if self.channel_index >= 0 else _active_channel_index(context)
            chain = get_or_create_chain(context.scene, channel_index)
            if not (0 <= self.vst_index < len(chain.vsts)):
                return {'CANCELLED'}
            item = chain.vsts[self.vst_index]

        item.bypass = not item.bypass
        sync_pure_bypass(item)
        return {'FINISHED'}


class DAW_OT_ReloadVst(Operator):
    bl_idname = "daw.reload_vst"
    bl_label = "Recarregar VST"
    bl_description = "Tenta carregar/recarregar este VST novamente (efeito ou instrumento)"
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    vst_index: IntProperty(default=-1)
    is_instrument: BoolProperty(default=False)

    def execute(self, context):
        if self.is_instrument:
            rack = context.scene.daw_vst_instruments
            if not (0 <= self.vst_index < len(rack.instruments)):
                return {'CANCELLED'}
            item = rack.instruments[self.vst_index]
        else:
            channel_index = self.channel_index if self.channel_index >= 0 else _active_channel_index(context)
            chain = get_or_create_chain(context.scene, channel_index)
            if not (0 <= self.vst_index < len(chain.vsts)):
                return {'CANCELLED'}
            item = chain.vsts[self.vst_index]

        ok = _load_item(item, context)
        if ok:
            self.report({'INFO'}, f"VST '{item.vst_name}' recarregado")
        else:
            self.report({'ERROR'}, item.error_message or "Falha ao carregar VST")
        return {'FINISHED'} if ok else {'CANCELLED'}


class DAW_OT_OpenVstEditor(Operator):
    bl_idname = "daw.open_vst_editor"
    bl_label = "Abrir Interface do Plugin"
    bl_description = (
        "Abre a janela nativa (GUI) do plugin, com os controles visuais "
        "de verdade dele -- não bloqueia o Blender"
    )
    bl_options = {'REGISTER'}

    channel_index: IntProperty(default=-1)
    vst_index: IntProperty(default=-1)
    is_instrument: BoolProperty(default=False)

    def execute(self, context):
        if self.is_instrument:
            rack = context.scene.daw_vst_instruments
            if not (0 <= self.vst_index < len(rack.instruments)):
                return {'CANCELLED'}
            item = rack.instruments[self.vst_index]
        else:
            channel_index = self.channel_index if self.channel_index >= 0 else _active_channel_index(context)
            chain = get_or_create_chain(context.scene, channel_index)
            if not (0 <= self.vst_index < len(chain.vsts)):
                return {'CANCELLED'}
            item = chain.vsts[self.vst_index]

        vst = get_live_vst(item.vst_id)
        if vst is None or not vst.loaded:
            self.report({'WARNING'}, "Carregue o VST antes de abrir a interface")
            return {'CANCELLED'}

        ok = vst.open_editor()
        if ok:
            self.report({'INFO'}, f"Abrindo interface de '{item.vst_name}'...")
        else:
            self.report({'WARNING'}, "Este plugin não tem interface nativa suportada")
        return {'FINISHED'} if ok else {'CANCELLED'}


class DAW_OT_SetVstParameter(Operator):
    bl_idname = "daw.set_vst_parameter"
    bl_label = "Definir Parâmetro do VST"
    bl_description = "Aplica o valor de um parâmetro (RNA) ao plugin real carregado"
    bl_options = {'REGISTER', 'UNDO'}

    vst_id: StringProperty(default="")
    param_id: IntProperty(default=0)
    value: bpy.props.FloatProperty(default=0.0, min=0.0, max=1.0)

    def execute(self, context):
        vst = get_live_vst(self.vst_id)
        if vst is None:
            self.report({'WARNING'}, "VST não está carregado")
            return {'CANCELLED'}
        vst.set_parameter(self.param_id, self.value)
        if vst.bridge is not None:
            try:
                vst.bridge.set_parameter(self.param_id, self.value)
            except Exception:
                pass

        # Marca o VST como "dirty" para o auto-bounce saber que precisa re-renderizar
        settings = context.scene.daw_vst
        if settings.auto_bounce_on_change and vst.is_instrument():
            _schedule_auto_bounce(context, self.vst_id)

        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Auto-bounce ao mudar parâmetro
# ---------------------------------------------------------------------- #

_auto_bounce_pending: dict = {}  # vst_id -> timer handle (bool flag)


def _schedule_auto_bounce(context, vst_id: str, delay: float = 0.8):
    """
    Agenda um bounce automático após `delay` segundos sem nova mudança
    de parâmetro (debounce). Evita bounce a cada knob girado.
    """
    _auto_bounce_pending[vst_id] = True

    def _do_bounce():
        if not _auto_bounce_pending.get(vst_id):
            return None  # cancelado por bounce mais recente

        _auto_bounce_pending.pop(vst_id, None)

        try:
            scene = bpy.context.scene
            live = get_live_vst(vst_id)
            if live is None or not live.loaded or not live.is_instrument():
                return None

            sample_rate = int(getattr(getattr(scene, "daw", None), "sample_rate", 44100))
            notes, duration, strip_name, frame_start = tlb.notes_from_legacy_piano_roll(scene, sample_rate)
            if not notes:
                notes, duration = tlb.notes_from_piano_roll(scene, sample_rate)
                strip_name = f"{live.name}_vst"
                frame_start = scene.frame_start

            if not notes:
                return None

            audio = tlb.render_instrument_notes(live, notes, duration, sample_rate)
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in strip_name) + "_vst"
            out_dir = bpy.path.abspath("//daw_renders/vst/")
            wav_path = os.path.join(out_dir, f"{safe_name}.wav")
            tlb.write_wav_stereo(wav_path, audio, sample_rate)

            seq = scene.sequence_editor_create()
            channel = tlb.find_free_channel(seq)
            tlb.upsert_sound_strip(scene, safe_name, wav_path, channel, frame_start)

            for area in bpy.context.screen.areas:
                area.tag_redraw()
        except Exception as e:
            print(f"[DAW VST] Auto-bounce falhou para '{vst_id}': {e}")

        return None

    # Cancela qualquer timer pendente (debounce) e agenda novo
    bpy.app.timers.register(_do_bounce, first_interval=delay)


class DAW_OT_AutoBounceVstInstrument(Operator):
    """
    Bounce manual com o mesmo mecanismo do auto-bounce (para o botão da UI).
    """
    bl_idname = "daw.auto_bounce_vst_instrument"
    bl_label = "Re-Bounce Agora"
    bl_description = (
        "Re-renderiza as notas do Piano Roll através deste VST instrumento "
        "e atualiza a strip na timeline. Use após mudar parâmetros ou notas."
    )
    bl_options = {'REGISTER'}

    vst_id: StringProperty(default="")

    def execute(self, context):
        live = get_live_vst(self.vst_id)
        if live is None or not live.loaded or not live.is_instrument():
            self.report({'ERROR'}, "VST instrumento não carregado")
            return {'CANCELLED'}

        _auto_bounce_pending[self.vst_id] = True
        _schedule_auto_bounce(context, self.vst_id, delay=0.0)
        self.report({'INFO'}, "Bounce agendado...")
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Monitoramento ao vivo (efeitos VST sobre o microfone)
# ---------------------------------------------------------------------- #
class DAW_OT_ToggleVstLiveMonitoring(Operator):
    """
    Liga/desliga o processamento de efeitos VST sobre a entrada do microfone
    em tempo real.

    Como funciona:
        O Blender não expõe API de DSP ao vivo — então usamos uma thread de
        áudio dedicada (via sounddevice/pyaudio, se disponível) que:
            1. Captura blocos do microfone
            2. Passa cada bloco pela cadeia de VST effects do canal ativo
            3. Reproduz o resultado no dispositivo de saída padrão

        O estado vive em `live_monitor.LiveMonitorState` (singleton).
        Ao desligar, a thread para e o dispositivo fecha.

    Limitação:
        Latência depende do block_size do dispositivo de áudio, não do
        Blender. Para low-latency real use ASIO/CoreAudio com block_size
        pequeno (128–256 amostras).
    """
    bl_idname = "daw.toggle_vst_live_monitoring"
    bl_label = "Monitor Ao Vivo (VST)"
    bl_description = (
        "Liga/desliga o processamento dos VST de efeito sobre o microfone em tempo real. "
        "Requer sounddevice instalado."
    )
    bl_options = {'REGISTER'}

    channel_index: IntProperty(default=-1)

    def execute(self, context):
        monitor = get_live_monitor()
        channel_index = self.channel_index if self.channel_index >= 0 else _active_channel_index(context)
        sample_rate = _sample_rate(context)

        if monitor.is_running:
            monitor.stop()
            self.report({'INFO'}, "Monitor ao vivo desligado")
        else:
            chain = get_or_create_chain(context.scene, channel_index)
            vst_ids = [item.vst_id for item in chain.vsts if not item.bypass and item.is_loaded]
            live_vsts = [get_live_vst(vid) for vid in vst_ids if get_live_vst(vid) is not None]

            ok, msg = monitor.start(live_vsts, sample_rate=sample_rate)
            if ok:
                self.report({'INFO'}, "Monitor ao vivo ligado")
            else:
                self.report({'ERROR'}, f"Não foi possível iniciar o monitor: {msg}")

        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Presets
# ---------------------------------------------------------------------- #
class DAW_OT_SaveVstPreset(Operator):
    bl_idname = "daw.save_vst_preset"
    bl_label = "Salvar Preset de VST"
    bl_description = "Salva os parâmetros atuais deste VST como um preset"
    bl_options = {'REGISTER', 'UNDO'}

    vst_id: StringProperty(default="")
    preset_name: StringProperty(name="Nome do Preset", default="Meu Preset")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, "preset_name")

    def execute(self, context):
        vst = get_live_vst(self.vst_id)
        if vst is None:
            self.report({'WARNING'}, "VST não está carregado")
            return {'CANCELLED'}

        manager = get_preset_manager()
        ok = manager.save_preset(vst, self.preset_name)
        if ok:
            vst.save_program(self.preset_name)
            self.report({'INFO'}, f"Preset '{self.preset_name}' salvo")
        else:
            self.report({'ERROR'}, "Não foi possível salvar o preset")
        return {'FINISHED'} if ok else {'CANCELLED'}


class DAW_OT_LoadVstPreset(Operator):
    bl_idname = "daw.load_vst_preset"
    bl_label = "Carregar Preset de VST"
    bl_description = "Carrega um preset salvo e aplica ao VST"
    bl_options = {'REGISTER', 'UNDO'}

    vst_id: StringProperty(default="")
    preset_name: StringProperty(default="default")

    def execute(self, context):
        vst = get_live_vst(self.vst_id)
        if vst is None:
            self.report({'WARNING'}, "VST não está carregado")
            return {'CANCELLED'}

        manager = get_preset_manager()
        ok = manager.load_preset(vst, self.preset_name)
        if ok:
            self.report({'INFO'}, f"Preset '{self.preset_name}' aplicado")
            # Sincroniza parâmetros do modelo puro de volta para o RNA
            _sync_item_params_from_live(context, self.vst_id)
        else:
            self.report({'ERROR'}, "Preset não encontrado")
        return {'FINISHED'} if ok else {'CANCELLED'}


def _sync_item_params_from_live(context, vst_id: str):
    """Atualiza os parâmetros RNA de todos os itens que referenciam este vst_id."""
    vst = get_live_vst(vst_id)
    if vst is None:
        return

    scene = context.scene
    # Percorre todas as cadeias e o rack para achar o item RNA
    for chain in scene.daw_vst_chains:
        for item in chain.vsts:
            if item.vst_id == vst_id:
                sync_rna_from_pure(item, vst)
    for item in scene.daw_vst_instruments.instruments:
        if item.vst_id == vst_id:
            sync_rna_from_pure(item, vst)


class DAW_OT_DeleteVstPreset(Operator):
    """
    Deleta um preset do usuário. Não afeta presets embutidos.
    """
    bl_idname = "daw.delete_vst_preset"
    bl_label = "Deletar Preset"
    bl_description = "Remove o preset selecionado do disco (apenas presets do usuário)"
    bl_options = {'REGISTER'}

    vst_id: StringProperty(default="")
    preset_name: StringProperty(default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self, event,
            message=f"Deletar preset '{self.preset_name}'? Esta ação não pode ser desfeita."
        )

    def execute(self, context):
        vst = get_live_vst(self.vst_id)
        if vst is None:
            self.report({'WARNING'}, "VST não está carregado")
            return {'CANCELLED'}

        manager = get_preset_manager()
        ok = manager.delete_preset(vst.name, self.preset_name)
        if ok:
            self.report({'INFO'}, f"Preset '{self.preset_name}' deletado")
        else:
            self.report({'WARNING'}, "Preset não encontrado")
        return {'FINISHED'} if ok else {'CANCELLED'}


class DAW_OT_ExportVstPresetLibrary(Operator):
    """Exporta todos os presets do usuário como .zip para backup ou compartilhar."""
    bl_idname = "daw.export_vst_preset_library"
    bl_label = "Exportar Presets"
    bl_description = "Exporta todos os presets VST como arquivo .zip"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH', default="vst_presets.zip")

    def invoke(self, context, event):
        if not self.filepath.endswith(".zip"):
            self.filepath += ".zip"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from pathlib import Path
        manager = get_preset_manager()
        ok = manager.export_preset_library(Path(self.filepath))
        if ok:
            self.report({'INFO'}, f"Presets exportados para '{self.filepath}'")
        else:
            self.report({'ERROR'}, "Falha ao exportar presets")
        return {'FINISHED'} if ok else {'CANCELLED'}


class DAW_OT_ImportVstPresetLibrary(Operator):
    """Importa biblioteca de presets de um .zip (criado por ExportVstPresetLibrary)."""
    bl_idname = "daw.import_vst_preset_library"
    bl_label = "Importar Presets"
    bl_description = "Importa presets VST de um arquivo .zip exportado anteriormente"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH', default="")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from pathlib import Path
        manager = get_preset_manager()
        ok = manager.import_preset_library(Path(self.filepath))
        if ok:
            self.report({'INFO'}, "Presets importados com sucesso")
        else:
            self.report({'ERROR'}, "Falha ao importar presets")
        return {'FINISHED'} if ok else {'CANCELLED'}


# ---------------------------------------------------------------------- #
# Bounce na Timeline
# ---------------------------------------------------------------------- #
class DAW_OT_RenderVstInstrumentToTimeline(Operator):
    bl_idname = "daw.render_vst_instrument_to_timeline"
    bl_label = "Renderizar Instrumento na Timeline"
    bl_description = (
        "Sintetiza as notas do Piano Roll através deste VST instrumento e "
        "insere o resultado como uma SOUND strip na timeline."
    )
    bl_options = {'REGISTER', 'UNDO'}

    vst_id: StringProperty(default="")
    strip_name: StringProperty(name="Nome da Strip", default="")
    start_beat: bpy.props.FloatProperty(name="Início (beats)", default=0.0, min=0.0)
    channel: IntProperty(name="Canal do Sequencer", default=0, min=0)

    def invoke(self, context, event):
        if not self.strip_name:
            _, _, legacy_name, legacy_frame = tlb.notes_from_legacy_piano_roll(context.scene)
            live = get_live_vst(self.vst_id)
            base_name = legacy_name or (live.name if live else self.vst_id)
            self.strip_name = f"{base_name}_vst"
            self.start_beat = tlb.frame_to_beat(context.scene, legacy_frame)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "strip_name")
        col.prop(self, "start_beat")
        col.prop(self, "channel")

    def execute(self, context):
        live = get_live_vst(self.vst_id)
        if live is None or not live.loaded:
            self.report({'ERROR'}, "VST instrumento não está carregado")
            return {'CANCELLED'}
        if not live.is_instrument():
            self.report({'ERROR'}, "Este VST não é um instrumento")
            return {'CANCELLED'}

        scene = context.scene
        sample_rate = _sample_rate(context)

        notes, duration, _, _ = tlb.notes_from_legacy_piano_roll(scene, sample_rate)
        if not notes:
            notes, duration = tlb.notes_from_piano_roll(scene, sample_rate)

        if not notes:
            self.report({'WARNING'}, "Nenhuma nota no Piano Roll para renderizar")
            return {'CANCELLED'}

        try:
            audio = tlb.render_instrument_notes(live, notes, duration, sample_rate)
        except Exception as e:
            self.report({'ERROR'}, f"Falha ao renderizar: {e}")
            return {'CANCELLED'}

        out_dir = bpy.path.abspath("//daw_renders/vst/")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.strip_name)
        wav_path = os.path.join(out_dir, f"{safe_name}.wav")
        tlb.write_wav_stereo(wav_path, audio, sample_rate)

        seq = scene.sequence_editor_create()
        channel = self.channel if self.channel > 0 else tlb.find_free_channel(seq)
        frame_start = tlb.beat_to_frame(scene, self.start_beat)

        try:
            tlb.upsert_sound_strip(scene, safe_name, wav_path, channel, frame_start)
        except Exception as e:
            self.report({'ERROR'}, f"Falha ao criar strip: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"'{safe_name}' renderizado no canal {channel} (frame {frame_start})")
        return {'FINISHED'}


class DAW_OT_ApplyVstEffectToStrip(Operator):
    bl_idname = "daw.apply_vst_effect_to_strip"
    bl_label = "Aplicar Cadeia de VST a uma Strip"
    bl_description = (
        "Processa o áudio de uma SOUND strip existente através da cadeia "
        "de efeitos VST do canal e insere o resultado como uma nova strip."
    )
    bl_options = {'REGISTER', 'UNDO'}

    channel_index: IntProperty(default=-1)
    strip_name: StringProperty(name="Strip de Origem", default="")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        scene = context.scene
        seq = scene.sequence_editor
        col = self.layout.column()
        if seq is not None and hasattr(seq, "strips"):
            col.prop_search(self, "strip_name", seq, "strips", text="Strip")
        elif seq is not None and hasattr(seq, "sequences"):
            col.prop_search(self, "strip_name", seq, "sequences", text="Strip")
        else:
            col.prop(self, "strip_name")

    def execute(self, context):
        scene = context.scene
        strip = tlb.find_strip_by_name(scene, self.strip_name)
        if strip is None:
            self.report({'ERROR'}, f"Strip '{self.strip_name}' não encontrada")
            return {'CANCELLED'}
        if getattr(strip, "sound", None) is None:
            self.report({'ERROR'}, "A strip selecionada não é uma SOUND strip")
            return {'CANCELLED'}

        channel_index = self.channel_index if self.channel_index >= 0 else _active_channel_index(context)
        chain = get_or_create_chain(scene, channel_index)
        if not len(chain.vsts):
            self.report({'WARNING'}, "Este canal não tem VSTs de efeito na cadeia")
            return {'CANCELLED'}

        sample_rate = _sample_rate(context)
        source_path = bpy.path.abspath(strip.sound.filepath)

        try:
            audio = tlb.read_audio_stereo(source_path, sample_rate)
            processed = tlb.apply_effect_chain_to_audio(chain.vsts, get_live_vst, audio, sample_rate)
        except Exception as e:
            self.report({'ERROR'}, f"Falha ao processar áudio: {e}")
            return {'CANCELLED'}

        out_dir = bpy.path.abspath("//daw_renders/vst/")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.strip_name)
        out_name = f"{safe_name}_vst"
        wav_path = os.path.join(out_dir, f"{out_name}.wav")
        tlb.write_wav_stereo(wav_path, processed, sample_rate)

        new_channel = tlb.find_free_channel(scene.sequence_editor_create(), min_channel=strip.channel + 1)
        try:
            tlb.upsert_sound_strip(scene, out_name, wav_path, new_channel, strip.frame_start)
        except Exception as e:
            self.report({'ERROR'}, f"Falha ao criar strip processada: {e}")
            return {'CANCELLED'}

        strip.mute = True
        self.report({'INFO'}, f"'{out_name}' criado no canal {new_channel} — strip original mutada")
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# (removido) Instalação via pip do dawdreamer -- não se aplica mais.
# O motor de VST agora roda via worker externo (ver modules/vst/ipc_engine.py),
# vendorizado junto com o addon, sem exigir nenhuma instalação do usuário.
# ---------------------------------------------------------------------- #

classes = [
    DAW_OT_ScanVstDirectories,
    DAW_OT_ScanVstDirectoriesAsync,
    DAW_OT_PickVstDirectory,
    DAW_OT_AddVstEffect,
    DAW_OT_RemoveVstEffect,
    DAW_OT_MoveVstEffect,
    DAW_OT_AddVstInstrument,
    DAW_OT_RemoveVstInstrument,
    DAW_OT_ToggleVstBypass,
    DAW_OT_ReloadVst,
    DAW_OT_OpenVstEditor,
    DAW_OT_SetVstParameter,
    DAW_OT_AutoBounceVstInstrument,
    DAW_OT_ToggleVstLiveMonitoring,
    DAW_OT_SaveVstPreset,
    DAW_OT_LoadVstPreset,
    DAW_OT_DeleteVstPreset,
    DAW_OT_ExportVstPresetLibrary,
    DAW_OT_ImportVstPresetLibrary,
    DAW_OT_RenderVstInstrumentToTimeline,
    DAW_OT_ApplyVstEffectToStrip,
]