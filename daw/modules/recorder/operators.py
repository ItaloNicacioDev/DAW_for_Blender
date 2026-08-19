# modules/recorder/operators.py
"""
Operadores do módulo Recorder.
"""
from __future__ import annotations

import os
import time

import bpy
import numpy as np
from bpy.types import Operator
from bpy.props import IntProperty, StringProperty

from .input import get_input_manager
from .recording import get_session
from .monitoring import start_monitoring, stop_monitoring
from .utils import (
    ensure_recording_dir,
    get_armed_track_indices,
    arm_track,
    disarm_track,
    disarm_all_tracks,
    create_sound_strip,
    frames_to_timecode,
    write_wav,
)


# ---------------------------------------------------------------------------
# Operadores de transporte
# ---------------------------------------------------------------------------

class DAW_OT_recorder_start(Operator):
    bl_idname = "daw.recorder_start"
    bl_label = "Gravar"
    bl_description = "Inicia a gravação nas tracks armadas"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.daw_recorder_settings
        return not settings.is_recording

    def execute(self, context):
        scene = context.scene
        settings = scene.daw_recorder_settings

        track_indices = get_armed_track_indices(context)
        if not track_indices:
            self.report({'WARNING'}, "Nenhuma track armada para gravação")
            return {'CANCELLED'}

        if settings.count_in_enabled:
            # A contagem regressiva sonora (metrônomo) deve ser tratada por
            # um modal timer dedicado na UI de transporte; aqui apenas
            # sinalizamos que ela está habilitada.
            self.report({'INFO'}, "Contagem regressiva ativada")

        session = get_session()
        ok = session.start(scene, track_indices)
        if not ok:
            self.report({'ERROR'}, "Não foi possível iniciar a gravação")
            return {'CANCELLED'}

        if session.last_error:
            # [FIX] session.start() agora guarda erros que antes eram
            # engolidos em silêncio (ex.: falha ao criar a pasta de
            # gravação) -- reporta pro usuário em vez de deixar a
            # gravação "ligada" sem strip e sem áudio, sem explicação.
            self.report({'WARNING'}, session.last_error)
        else:
            self.report({'INFO'}, "Gravação iniciada")

        mgr = get_input_manager()
        if not mgr.has_sounddevice:
            self.report(
                {'WARNING'},
                "sounddevice não está instalado no Python do Blender — "
                "a gravação está 'ligada', mas nenhum áudio real será "
                "capturado. Instale sounddevice no Python interno do "
                "Blender para gravar de verdade.",
            )

        return {'FINISHED'}


class DAW_OT_recorder_stop(Operator):
    bl_idname = "daw.recorder_stop"
    bl_label = "Parar"
    bl_description = "Para a gravação e exporta os arquivos de áudio capturados"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.daw_recorder_settings
        return settings.is_recording

    def execute(self, context):
        scene = context.scene
        settings = scene.daw_recorder_settings
        session = get_session()

        track_buffers = session.stop(scene)
        if not track_buffers:
            self.report({'WARNING'}, "Nenhum áudio capturado")
            return {'CANCELLED'}

        out_dir = ensure_recording_dir(context)
        samplerate = int(settings.sample_rate)
        bit_depth = settings.bit_depth
        # Reaproveita o session_id do início da gravação (usado nos nomes
        # dos arquivos "ao vivo") pra que o .wav final caia exatamente no
        # mesmo caminho que a strip ao vivo já estava usando -- sem isso
        # sobrariam dois arquivos por track (o parcial e o final).
        timestamp = session.session_id or time.strftime("%Y%m%d_%H%M%S")

        exported = 0
        for track_idx, chunks in track_buffers.items():
            if not chunks:
                continue

            data = np.concatenate(chunks).astype('float32')
            filepath = session.live_filepaths.get(track_idx)
            if not filepath:
                filename = f"track{track_idx}_{timestamp}.wav"
                filepath = os.path.join(out_dir, filename)

            try:
                write_wav(filepath, data, samplerate, bit_depth)
            except Exception as e:
                self.report({'ERROR'}, f"Falha ao exportar track {track_idx}: {e}")
                continue

            session.recorded_filepaths[track_idx] = filepath
            exported += 1

            try:
                if track_idx in session.live_strip_names:
                    # Já existia uma strip "ao vivo" pra essa track: troca
                    # ela pela versão final (mesmo arquivo, já completo),
                    # em vez de criar uma segunda strip por cima.
                    session.finalize_live_strip(context, track_idx, filepath)
                else:
                    create_sound_strip(
                        context,
                        filepath=filepath,
                        channel=track_idx + 1,
                        frame_start=session.start_frame,
                        name=f"Rec_{track_idx}_{timestamp}",
                    )
            except Exception as e:
                self.report({'WARNING'}, f"Falha ao criar strip para track {track_idx}: {e}")

        if exported:
            self.report({'INFO'}, f"{exported} arquivo(s) exportado(s) para {out_dir}")
        else:
            self.report({'WARNING'}, "Nenhum arquivo foi exportado")

        return {'FINISHED'}


class DAW_OT_recorder_pause(Operator):
    bl_idname = "daw.recorder_pause"
    bl_label = "Pausar"
    bl_description = "Pausa ou retoma a gravação em andamento"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.daw_recorder_settings.is_recording

    def execute(self, context):
        session = get_session()
        session.pause()
        state = "pausada" if session.is_paused else "retomada"
        self.report({'INFO'}, f"Gravação {state}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operadores de entrada / monitoramento
# ---------------------------------------------------------------------------

class DAW_OT_recorder_toggle_monitor(Operator):
    bl_idname = "daw.recorder_toggle_monitor"
    bl_label = "Monitorar Entrada"
    bl_description = "Ativa/desativa o monitoramento em tempo real da entrada de áudio"
    bl_options = {'REGISTER'}

    def execute(self, context):
        settings = context.scene.daw_recorder_settings
        settings.monitor_input = not settings.monitor_input

        mgr = get_input_manager()
        if settings.monitor_input or settings.is_recording:
            if not mgr.stream:
                # [FIX v3] device_identifier=None -> resolve pra config
                # global (única fonte de verdade agora).
                mgr.start(None, int(settings.sample_rate))
            start_monitoring()
        else:
            stop_monitoring()
            if not settings.is_recording:
                mgr.stop()

        return {'FINISHED'}


class DAW_OT_recorder_refresh_devices(Operator):
    bl_idname = "daw.recorder_refresh_devices"
    bl_label = "Atualizar Dispositivos"
    bl_description = "Lista os dispositivos de entrada de áudio disponíveis"
    bl_options = {'REGISTER'}

    def execute(self, context):
        mgr = get_input_manager()
        devices = mgr.get_devices()
        names = ", ".join(d[1] for d in devices)
        self.report({'INFO'}, f"Dispositivos: {names}")
        return {'FINISHED'}


class DAW_OT_test_output_device(Operator):
    """Toca um beep curto (~0.3s, 440Hz) no dispositivo de saída
    configurado globalmente, pra confirmar que ele está ativo e sendo
    reconhecido corretamente -- sem precisar abrir um VST ou clicar
    play na timeline só pra testar."""
    bl_idname = "daw.test_output_device"
    bl_label = "Testar Saída"
    bl_description = "Toca um beep curto no dispositivo de saída configurado"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            import sounddevice as sd
            import numpy as np
        except Exception as e:
            self.report({'ERROR'}, f"sounddevice não disponível: {e}")
            return {'CANCELLED'}

        from .input import resolve_device_index, get_default_output_identifier

        identifier = get_default_output_identifier()
        device_id = resolve_device_index(identifier)

        sr = 44100
        duration = 0.3
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        tone = 0.2 * np.sin(2 * np.pi * 440.0 * t).astype('float32')
        stereo = np.column_stack([tone, tone])

        try:
            sd.play(stereo, samplerate=sr, device=device_id, blocking=False)
        except Exception as e:
            self.report({'ERROR'}, f"Falha ao tocar no dispositivo de saída: {e}")
            return {'CANCELLED'}

        label = f"índice {device_id}" if device_id is not None else "padrão do sistema"
        self.report({'INFO'}, f"Tocando beep de teste no dispositivo {label}")
        return {'FINISHED'}


class DAW_OT_recorder_select_device(Operator):
    bl_idname = "daw.recorder_select_device"
    bl_label = "Selecionar Dispositivo"
    bl_description = "Define o dispositivo de entrada ativo (config. global do addon)"
    bl_options = {'REGISTER', 'UNDO'}

    device_name: StringProperty(name="Dispositivo", default="Default")

    def execute(self, context):
        # [FIX v3] Escreve na config global (Preferências do addon), não
        # mais num campo de Scene -- é a única fonte de verdade agora,
        # compartilhada com o painel "Recorder" e qualquer outro lugar
        # do addon que precise do dispositivo de entrada configurado.
        from ..settings.preferences import get_preferences
        prefs = get_preferences()
        prefs.audio.input_device = self.device_name

        mgr = get_input_manager()
        settings = context.scene.daw_recorder_settings
        if mgr.stream:
            mgr.stop()
            mgr.start(self.device_name, int(settings.sample_rate))

        self.report({'INFO'}, f"Dispositivo definido: {self.device_name}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operadores de armamento de tracks
# ---------------------------------------------------------------------------

class DAW_OT_recorder_arm_track(Operator):
    bl_idname = "daw.recorder_arm_track"
    bl_label = "Armar Track"
    bl_description = "Arma a track (ou a strip/canal ativo do sequencer) para gravação"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(name="Índice da Track", default=0, min=0)
    track_name: StringProperty(name="Nome", default="")

    def invoke(self, context, event):
        # Se disparado pela UI sem argumentos explícitos, tenta usar o
        # canal/strip ativo do sequencer como alvo do armamento.
        seq = context.scene.sequence_editor
        if seq is not None and seq.active_strip is not None:
            self.track_index = seq.active_strip.channel
            self.track_name = seq.active_strip.name
        return self.execute(context)

    def execute(self, context):
        arm_track(context, self.track_index, self.track_name)
        self.report({'INFO'}, f"Track {self.track_index} armada")
        return {'FINISHED'}


class DAW_OT_recorder_disarm_track(Operator):
    bl_idname = "daw.recorder_disarm_track"
    bl_label = "Desarmar Track"
    bl_description = "Remove o armamento de gravação da track"
    bl_options = {'REGISTER', 'UNDO'}

    track_index: IntProperty(name="Índice da Track", default=0, min=0)

    def execute(self, context):
        disarm_track(context, self.track_index)
        return {'FINISHED'}


class DAW_OT_recorder_disarm_all(Operator):
    bl_idname = "daw.recorder_disarm_all"
    bl_label = "Desarmar Todas"
    bl_description = "Remove o armamento de todas as tracks"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.scene.daw_recorder_settings.armed_tracks) > 0

    def execute(self, context):
        disarm_all_tracks(context)
        return {'FINISHED'}


classes = [
    DAW_OT_recorder_start,
    DAW_OT_recorder_stop,
    DAW_OT_recorder_pause,
    DAW_OT_recorder_toggle_monitor,
    DAW_OT_recorder_refresh_devices,
    DAW_OT_test_output_device,
    DAW_OT_recorder_select_device,
    DAW_OT_recorder_arm_track,
    DAW_OT_recorder_disarm_track,
    DAW_OT_recorder_disarm_all,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)