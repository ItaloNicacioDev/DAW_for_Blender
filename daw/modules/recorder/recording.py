# modules/recorder/recording.py
"""
Engine de gravação e sessão.
"""
from __future__ import annotations

import os
import time

import bpy
import numpy as np
from bpy.app.handlers import persistent

from .input import get_input_manager
from .utils import (
    ensure_recording_dir,
    get_armed_track_indices,
    create_sound_strip,
    remove_strip_by_name,
    write_wav,
)


LIVE_STRIP_PREFIX = "REC_LIVE_"


def _live_strip_name(track_index: int, session_id: str) -> str:
    return f"{LIVE_STRIP_PREFIX}{track_index}_{session_id}"


class RecordingSession:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.is_recording = False
        self.is_paused = False
        self.start_frame = 0
        self.track_buffers = {}
        self.recorded_filepaths = {}
        self._frame_count = 0

        # --- Estado da strip "ao vivo" (waveform crescendo durante a
        # gravação, como em uma DAW convencional) ---
        self.session_id = ""
        self.live_filepaths = {}       # track_idx -> caminho do .wav
        self.live_strip_names = {}     # track_idx -> nome da strip no VSE
        self._live_last_len = {}       # track_idx -> nº de samples já vistos
        self._live_timer_active = False
        self.last_error = ""           # última mensagem de erro (pro operador reportar)

    def start(self, scene, track_indices: list[int]):
        if self.is_recording:
            return False

        settings = scene.daw_recorder_settings
        self.is_recording = True
        self.is_paused = False
        self.start_frame = scene.frame_current
        self._frame_count = 0
        self.track_buffers = {idx: [] for idx in track_indices}
        self.recorded_filepaths = {}
        self.last_error = ""

        mgr = get_input_manager()
        if not mgr.stream or not mgr.stream.active:
            sr = int(settings.sample_rate)
            # [FIX v3] device_identifier=None -> mgr.start() resolve pra
            # get_default_input_identifier(), a config global única
            # (ver modules/recorder/input.py). Antes lia de
            # settings.input_device, campo que foi removido por ser uma
            # cópia redundante da mesma configuração.
            mgr.start(None, sr)

        if record_frame_handler not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(record_frame_handler)

        # [FIX] A captura de áudio (process_frame) só roda dentro do handler
        # de frame_change_post -- ou seja, só é chamada quando o playhead
        # avança de fato. Se o usuário chamar `daw.recorder_start` sem a
        # timeline estar tocando (ex.: pelo painel Recorder isolado, sem
        # passar pelo REC da barra de transporte), nenhum frame avança e
        # process_frame nunca roda: a gravação fica "ligada" mas nenhuma
        # amostra é capturada, silenciosamente. Garantimos aqui que o
        # playback sempre esteja rodando enquanto a sessão está gravando,
        # não importa por qual botão ela foi iniciada.
        screen = bpy.context.screen
        if screen is not None and not screen.is_animation_playing:
            try:
                bpy.ops.screen.animation_play()
            except Exception as e:
                print(f"[DAW Recorder] Falha ao iniciar playback automaticamente: {e}")

        settings.is_recording = True
        settings.record_start_frame = self.start_frame

        # --- Prepara a strip "ao vivo" para cada track armada ---
        self.session_id = time.strftime("%Y%m%d_%H%M%S")
        self.live_filepaths = {}
        self.live_strip_names = {}
        self._live_last_len = {idx: 0 for idx in track_indices}

        if getattr(settings, 'live_waveform_preview', True):
            try:
                out_dir = ensure_recording_dir(bpy.context)
            except Exception as e:
                out_dir = None
                # [FIX] Antes esse erro era engolido em silêncio -- se o
                # .blend nunca foi salvo, "//recordings/" pode resolver
                # pra um caminho não gravável (ex.: a pasta de instalação
                # do Blender no Windows) e o mkdir falha com
                # PermissionError, sem strip nenhuma aparecer e sem
                # nenhum aviso pro usuário. Guardamos o erro pra o
                # operador (`daw.recorder_start`) reportar na barra de
                # status do Blender.
                self.last_error = (
                    f"Não foi possível criar a pasta de gravação "
                    f"('{settings.export_path}'): {e}. Salve o arquivo .blend "
                    f"ou ajuste o Caminho de Exportação em Recorder > Formato."
                )
                print(f"[DAW Recorder] {self.last_error}")

            if out_dir:
                samplerate = int(settings.sample_rate)
                bit_depth = settings.bit_depth
                for idx in track_indices:
                    filepath = os.path.join(out_dir, f"track{idx}_{self.session_id}.wav")
                    name = _live_strip_name(idx, self.session_id)
                    self.live_filepaths[idx] = filepath
                    self.live_strip_names[idx] = name
                    try:
                        # Placeholder mínimo (silêncio) só pra existir um
                        # arquivo válido no disco -- new_sound() exige que
                        # o arquivo já exista.
                        write_wav(filepath, np.zeros(1, dtype='float32'), samplerate, bit_depth)
                        create_sound_strip(
                            bpy.context,
                            filepath=filepath,
                            channel=idx + 1,
                            frame_start=self.start_frame,
                            name=name,
                        )
                    except Exception as e:
                        print(f"[DAW Recorder] Falha ao criar strip ao vivo (track {idx}): {e}")
                        self.last_error = self.last_error or str(e)

            interval = max(0.05, float(getattr(settings, 'live_waveform_interval', 0.25)))
            if not self._live_timer_active:
                self._live_timer_active = True
                bpy.app.timers.register(_live_update_tick, first_interval=interval)

        return True

    def stop(self, scene):
        if not self.is_recording:
            return {}

        # Marcado antes de mais nada: o timer de refresh (_live_update_tick)
        # confere is_recording a cada tick e se auto-desregistra (retornando
        # None) assim que ele virar False, então não precisamos remover o
        # timer manualmente aqui.
        self.is_recording = False
        self._live_timer_active = False

        settings = scene.daw_recorder_settings
        settings.is_recording = False
        settings.is_paused = False
        settings.record_end_frame = scene.frame_current

        if record_frame_handler in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.remove(record_frame_handler)

        # Contrapartida do auto-play em start(): se a reprodução foi
        # deixada rodando (loop), paramos aqui também, senão o playhead
        # fica correndo indefinidamente depois que a gravação já parou.
        screen = bpy.context.screen
        if screen is not None and screen.is_animation_playing:
            try:
                bpy.ops.screen.animation_cancel(restore_frame=False)
            except Exception as e:
                print(f"[DAW Recorder] Falha ao parar playback automaticamente: {e}")

        if not settings.monitor_input:
            get_input_manager().stop()

        return self.track_buffers.copy()

    def finalize_live_strip(self, context, track_index: int, filepath: str):
        """Substitui a strip 'ao vivo' pela versão final (mesmo arquivo,
        já com todo o áudio gravado), renomeando pra tirar a marcação de
        'ao vivo'. Chamado pelo operador Parar depois de escrever o .wav
        definitivo. Se não havia strip ao vivo para essa track (preview
        desabilitado, ou falhou ao criar), cria a strip do zero.
        """
        live_name = self.live_strip_names.get(track_index)
        if live_name:
            remove_strip_by_name(context, live_name)

        final_name = f"Rec_{track_index}_{self.session_id or self.start_frame}"
        strip = create_sound_strip(
            context,
            filepath=filepath,
            channel=track_index + 1,
            frame_start=self.start_frame,
            name=final_name,
        )
        return strip

    def pause(self):
        self.is_paused = not self.is_paused
        bpy.context.scene.daw_recorder_settings.is_paused = self.is_paused

    def process_frame(self, scene):
        if not self.is_recording or self.is_paused:
            return

        self._frame_count += 1
        mgr = get_input_manager()
        buf = mgr.read_buffer()

        settings = scene.daw_recorder_settings
        gain = 10 ** (settings.input_gain_db / 20.0)
        buf = buf * gain

        for idx in self.track_buffers:
            self.track_buffers[idx].append(buf.copy())

        if settings.punch_out and scene.frame_current >= settings.punch_out_frame:
            bpy.ops.daw.recorder_stop()


@persistent
def record_frame_handler(scene):
    session = RecordingSession()
    if session.is_recording:
        session.process_frame(scene)


# ---------------------------------------------------------------------------
# Refresh periódico da strip "ao vivo"
#
# Roda fora do frame_change_post (que só dispara quando o playhead avança
# durante o play/gravação) via bpy.app.timers, que é chamado pelo loop de
# eventos do Blender independente da timeline estar tocando. Isso garante
# que a waveform vá "crescendo" na VSE em tempo real, do jeito que acontece
# numa DAW normal enquanto você grava.
#
# A cada tick: para cada track sendo gravada, pega o que já foi capturado
# no buffer em memória (session.track_buffers), reescreve o .wav no disco
# e recria a strip de som apontando pro mesmo arquivo -- recriar (em vez de
# só trocar o filepath do datablock) é o jeito confiável de forçar o VSE a
# reler o áudio e redesenhar a waveform e a duração da strip.
# ---------------------------------------------------------------------------

def _refresh_live_strip(context, track_index: int) -> bool:
    session = get_session()
    settings = context.scene.daw_recorder_settings

    chunks = session.track_buffers.get(track_index)
    if not chunks:
        return False

    total_len = sum(len(c) for c in chunks)
    # Nada de novo desde o último refresh -- não vale a pena reescrever o
    # arquivo e recriar a strip à toa.
    if total_len <= session._live_last_len.get(track_index, 0):
        return False

    filepath = session.live_filepaths.get(track_index)
    name = session.live_strip_names.get(track_index)
    if not filepath or not name:
        return False

    data = np.concatenate(chunks).astype('float32')
    samplerate = int(settings.sample_rate)
    bit_depth = settings.bit_depth

    write_wav(filepath, data, samplerate, bit_depth)

    remove_strip_by_name(context, name)
    strip = create_sound_strip(
        context,
        filepath=filepath,
        channel=track_index + 1,
        frame_start=session.start_frame,
        name=name,
    )
    if strip is not None:
        strip.select = False

    session._live_last_len[track_index] = total_len
    return True


def _live_update_tick():
    session = get_session()
    if not session.is_recording:
        # Retornar None cancela o timer -- ver bpy.app.timers.register.
        return None

    context = bpy.context
    scene = getattr(context, 'scene', None)
    if scene is None:
        return None

    settings = scene.daw_recorder_settings
    interval = max(0.05, float(getattr(settings, 'live_waveform_interval', 0.25)))

    if not getattr(settings, 'live_waveform_preview', True):
        return interval

    if session.is_paused:
        return interval

    changed = False
    for idx in list(session.track_buffers.keys()):
        try:
            if _refresh_live_strip(context, idx):
                changed = True
        except Exception as e:
            print(f"[DAW Recorder] Falha ao atualizar strip ao vivo (track {idx}): {e}")

    if changed:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'SEQUENCE_EDITOR':
                    area.tag_redraw()

    return interval


def get_session() -> RecordingSession:
    return RecordingSession()


classes = []


def register():
    pass


def unregister():
    session = get_session()
    if session.is_recording:
        try:
            session.stop(bpy.context.scene)
        except:
            pass
    if record_frame_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(record_frame_handler)
    if bpy.app.timers.is_registered(_live_update_tick):
        bpy.app.timers.unregister(_live_update_tick)
    get_input_manager().stop()