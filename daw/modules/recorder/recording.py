# modules/recorder/recording.py
"""
Engine de gravação e sessão.
"""
from __future__ import annotations

import bpy
import numpy as np
from bpy.app.handlers import persistent

from .input import get_input_manager
from .utils import ensure_recording_dir, get_armed_track_indices


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

        mgr = get_input_manager()
        if not mgr.stream or not mgr.stream.active:
            sr = int(settings.sample_rate)
            mgr.start(settings.input_device, sr)

        if record_frame_handler not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(record_frame_handler)

        settings.is_recording = True
        settings.record_start_frame = self.start_frame
        return True

    def stop(self, scene):
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

        return self.track_buffers.copy()

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