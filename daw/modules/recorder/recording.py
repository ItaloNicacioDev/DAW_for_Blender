# modules/recorder/recording.py
"""
Engine de gravação e sessão.

Gravação AO VIVO: em vez de acumular o áudio inteiro em memória e só
escrever o `.wav` + criar a strip quando a gravação termina, agora cada
track armada ganha um `LiveWavWriter` (ver live_strip.py) que escreve
o arquivo incrementalmente, e uma strip que é criada assim que a
gravação começa e vai "esticando" na timeline conforme o áudio chega
-- igual numa DAW de verdade, em vez de só aparecer no fim.

`live_strip.py` já existia no addon com essa lógica pronta (escrita
incremental de WAV + reload do datablock de Sound), só não estava
conectado a nada -- esta é a integração.
"""
from __future__ import annotations

import time

import bpy
import numpy as np
from bpy.app.handlers import persistent

from .input import get_input_manager
from .live_strip import LiveWavWriter, create_live_strip, refresh_live_strip, remove_live_strip
from .utils import ensure_recording_dir_for_scene, get_armed_track_indices

# A cada quantos frames de `frame_change_post` a strip ao vivo é
# esticada/redesenhada. Refazer a cada frame recarregaria o datablock
# de Sound com frequência demais (custo de I/O + possível flicker na
# waveform desenhada); a cada N frames já dá a sensação de "crescendo
# ao vivo" sem sobrecarregar. Com timeline a 24fps, 4 = ~6 refreshs/seg.
LIVE_STRIP_REFRESH_EVERY_N_FRAMES = 4


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
        self.recorded_filepaths = {}
        self._live_writers: dict[int, LiveWavWriter] = {}
        self._live_strip_names: dict[int, str] = {}
        self._frame_count = 0

    def start(self, scene, track_indices: list[int]):
        if self.is_recording:
            return False

        settings = scene.daw_recorder_settings
        self.is_recording = True
        self.is_paused = False
        self.start_frame = scene.frame_current
        self._frame_count = 0
        self.recorded_filepaths = {}
        self._live_writers = {}
        self._live_strip_names = {}

        sr = int(settings.sample_rate)
        out_dir = ensure_recording_dir_for_scene(scene)
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        for idx in track_indices:
            import os
            filepath = os.path.join(out_dir, f"track{idx}_{timestamp}.wav")
            writer = LiveWavWriter(filepath, samplerate=sr, bit_depth=settings.bit_depth, channels=1)
            strip_name = f"Rec_{idx}_{timestamp}"

            self._live_writers[idx] = writer
            self._live_strip_names[idx] = strip_name
            self.recorded_filepaths[idx] = filepath

            # Canal do VSE: track_index + 1 (canal 0 não existe no VSE).
            # Se duas tracks armadas caírem no mesmo canal por acaso do
            # esquema de índices do projeto, a strip mais recente
            # simplesmente sobrepõe -- não é um caso comum (cada track
            # armada normalmente já tem seu próprio índice/canal).
            create_live_strip(scene, filepath, channel=idx + 1, frame_start=self.start_frame, name=strip_name)

        mgr = get_input_manager()
        if not mgr.stream or not mgr.stream.active:
            # [FIX v3] device_identifier=None -> mgr.start() resolve pra
            # get_default_input_identifier(), a config global única
            # (ver modules/recorder/input.py).
            mgr.start(None, sr)

        if record_frame_handler not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(record_frame_handler)

        settings.is_recording = True
        settings.record_start_frame = self.start_frame
        return True

    def stop(self, scene) -> dict:
        """
        Encerra a gravação: fecha os writers (garante que o cabeçalho
        WAV final reflita o tamanho real) e faz um último refresh de
        cada strip ao vivo (pra cobrir os frames gravados desde o
        último refresh periódico, que só roda a cada
        LIVE_STRIP_REFRESH_EVERY_N_FRAMES frames).

        Tracks que não capturaram nenhuma amostra (ex.: usuário armou a
        track mas o dispositivo de entrada não estava entregando áudio)
        têm sua strip e arquivo removidos em vez de deixar uma strip
        fantasma de duração 0/silêncio na timeline.

        Retorna {track_index: filepath} só das tracks que de fato
        gravaram algo.
        """
        if not self.is_recording:
            return {}

        self.is_recording = False
        settings = scene.daw_recorder_settings
        settings.is_recording = False
        settings.is_paused = False
        settings.record_end_frame = scene.frame_current

        if record_frame_handler in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.remove(record_frame_handler)

        if not settings.monitor_input:
            get_input_manager().stop()

        results = {}
        for idx, writer in self._live_writers.items():
            writer.close()
            strip_name = self._live_strip_names[idx]
            filepath = self.recorded_filepaths[idx]

            if writer.total_frames == 0:
                # Nada foi capturado nessa track -- remove a strip
                # vazia e o arquivo (só cabeçalho, 0 amostras) em vez
                # de deixar lixo na timeline/disco.
                remove_live_strip(scene, strip_name)
                try:
                    import os
                    os.remove(filepath)
                except OSError:
                    pass
                continue

            refresh_live_strip(scene, strip_name, filepath, self.start_frame, writer.total_seconds)
            results[idx] = filepath

        self._live_writers = {}
        self._live_strip_names = {}
        return results

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

        for idx, writer in self._live_writers.items():
            writer.append(buf)

        if self._frame_count % LIVE_STRIP_REFRESH_EVERY_N_FRAMES == 0:
            for idx, writer in self._live_writers.items():
                refresh_live_strip(
                    scene,
                    self._live_strip_names[idx],
                    self.recorded_filepaths[idx],
                    self.start_frame,
                    writer.total_seconds,
                )

        if settings.punch_out and scene.frame_current >= settings.punch_out_frame:
            bpy.ops.daw.recorder_stop()


@persistent
def record_frame_handler(scene):
    session = RecordingSession()
    if session.is_recording:
        session.process_frame(scene)


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
    get_input_manager().stop()