"""
DAW Engine - Audio Exceptions

Todas as exceções relacionadas ao sistema de áudio devem
herdar de AudioEngineError.

Isso facilita:

- Debug
- Logs
- Tratamento de erros
- Mensagens ao usuário
"""

from __future__ import annotations


# ==========================================================
# BASE
# ==========================================================

class AudioEngineError(Exception):
    """
    Exceção base da Engine de Áudio.

    Todas as exceções da pasta audio devem herdar desta classe.
    """

    default_message = "Unknown Audio Engine Error."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


# ==========================================================
# CONFIGURAÇÃO
# ==========================================================

class AudioConfigError(AudioEngineError):
    default_message = "Invalid audio configuration."


class InvalidSampleRate(AudioConfigError):
    default_message = "Invalid sample rate."


class InvalidBufferSize(AudioConfigError):
    default_message = "Invalid buffer size."


class InvalidChannelCount(AudioConfigError):
    default_message = "Invalid number of audio channels."


class InvalidSampleFormat(AudioConfigError):
    default_message = "Unsupported sample format."


# ==========================================================
# BACKEND
# ==========================================================

class AudioBackendError(AudioEngineError):
    default_message = "Audio backend error."


class BackendNotFound(AudioBackendError):
    default_message = "Requested audio backend was not found."


class BackendInitializationError(AudioBackendError):
    default_message = "Failed to initialize audio backend."


class BackendUnavailable(AudioBackendError):
    default_message = "Audio backend is unavailable."


# ==========================================================
# DEVICE
# ==========================================================

class AudioDeviceError(AudioEngineError):
    default_message = "Audio device error."


class OutputDeviceNotFound(AudioDeviceError):
    default_message = "Output audio device not found."


class InputDeviceNotFound(AudioDeviceError):
    default_message = "Input audio device not found."


class DeviceBusy(AudioDeviceError):
    default_message = "Audio device is already in use."


class DeviceDisconnected(AudioDeviceError):
    default_message = "Audio device disconnected."


class DeviceOpenError(AudioDeviceError):
    default_message = "Unable to open audio device."


# ==========================================================
# STREAM
# ==========================================================

class AudioStreamError(AudioEngineError):
    default_message = "Audio stream error."


class StreamAlreadyRunning(AudioStreamError):
    default_message = "Audio stream is already running."


class StreamNotRunning(AudioStreamError):
    default_message = "Audio stream is not running."


class StreamStartError(AudioStreamError):
    default_message = "Failed to start audio stream."


class StreamStopError(AudioStreamError):
    default_message = "Failed to stop audio stream."


class StreamCallbackError(AudioStreamError):
    default_message = "Audio callback failed."


# ==========================================================
# BUFFER
# ==========================================================

class AudioBufferError(AudioEngineError):
    default_message = "Audio buffer error."


class BufferOverflow(AudioBufferError):
    default_message = "Audio buffer overflow."


class BufferUnderflow(AudioBufferError):
    default_message = "Audio buffer underflow."


class InvalidBuffer(AudioBufferError):
    default_message = "Invalid audio buffer."


# ==========================================================
# MIDI
# ==========================================================

class MidiError(AudioEngineError):
    default_message = "MIDI error."


class MidiDeviceNotFound(MidiError):
    default_message = "MIDI device not found."


class MidiPortError(MidiError):
    default_message = "Unable to open MIDI port."


class InvalidMidiMessage(MidiError):
    default_message = "Invalid MIDI message."


# ==========================================================
# DSP
# ==========================================================

class DSPError(AudioEngineError):
    default_message = "DSP processing error."


class OscillatorError(DSPError):
    default_message = "Oscillator error."


class FilterError(DSPError):
    default_message = "Filter error."


class EffectError(DSPError):
    default_message = "DSP effect error."


# ==========================================================
# SYNTH
# ==========================================================

class SynthError(AudioEngineError):
    default_message = "Synthesizer error."


class VoiceLimitReached(SynthError):
    default_message = "Maximum number of voices reached."


class InvalidVoice(SynthError):
    default_message = "Invalid voice."


class PresetError(SynthError):
    default_message = "Preset loading failed."


# ==========================================================
# MIXER
# ==========================================================

class MixerError(AudioEngineError):
    default_message = "Mixer error."


class InvalidTrack(MixerError):
    default_message = "Invalid mixer track."


class RoutingError(MixerError):
    default_message = "Invalid mixer routing."


# ==========================================================
# TRANSPORT
# ==========================================================

class TransportError(AudioEngineError):
    default_message = "Transport error."


class PlaybackError(TransportError):
    default_message = "Playback failed."


class RecordingError(TransportError):
    default_message = "Recording failed."


# ==========================================================
# FILES
# ==========================================================

class AudioFileError(AudioEngineError):
    default_message = "Audio file error."


class UnsupportedAudioFormat(AudioFileError):
    default_message = "Unsupported audio format."


class AudioFileNotFound(AudioFileError):
    default_message = "Audio file not found."


class AudioDecodeError(AudioFileError):
    default_message = "Failed to decode audio file."