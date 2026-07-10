# modules/export/__init__.py
"""
Módulo de Exportação da DAW.

Responsabilidade:
    Exportar o projeto (notas do Piano Roll) para arquivos de áudio (WAV,
    MP3, OGG, FLAC) ou MIDI, em disco.

Arquitetura:
    wav.py    — sintetizador simples puro-Python (stdlib) + escrita de .wav real
    midi.py   — escritor de Standard MIDI File (.mid) puro-Python (stdlib)
    mp3.py    — transcodifica o .wav via ffmpeg (codec libmp3lame)
    ogg.py    — transcodifica o .wav via ffmpeg (codec libvorbis)
    flac.py   — transcodifica o .wav via ffmpeg (codec flac, sem perdas)
    utils.py  — checagem de ffmpeg, extração de notas da cena, helpers de path
    properties.py — PropertyGroup do Blender (configurações da UI)
    operators.py  — Operator do Blender (dispara a exportação)
    ui.py     — Painel do Blender
    register.py — register() / unregister()

Notas:
    - WAV e MIDI funcionam sem nenhuma dependência externa (apenas stdlib).
    - MP3, OGG e FLAC exigem o `ffmpeg` instalado e disponível no PATH do
      sistema, pois o Python não tem encoders desses formatos na stdlib.
      Use utils.check_ffmpeg_available() para verificar antes de exportar.

Uso fora do Blender (scripts/testes), a partir do modelo puro:
    from daw.modules.export import ExportNote, export_notes_to_wav, export_notes_to_midi

    notes = [ExportNote(pitch=60, start=0.0, length=1.0, velocity=100)]
    export_notes_to_wav(notes, bpm=120, filepath="preview.wav")
    export_notes_to_midi(notes, bpm=120, filepath="preview.mid")
"""
from __future__ import annotations

from .wav import (
    ExportNote,
    WAVE_SHAPES,
    pitch_to_freq,
    render_notes,
    write_wav_file,
    export_notes_to_wav,
)
from .midi import (
    DEFAULT_PPQ,
    notes_to_midi_bytes,
    export_notes_to_midi,
)
from .mp3 import export_wav_to_mp3, VALID_BITRATES as MP3_BITRATES
from .ogg import export_wav_to_ogg
from .flac import export_wav_to_flac
from .utils import (
    check_ffmpeg_available,
    ensure_extension,
    get_notes_from_scene,
)
from .register import register, unregister

__all__ = [
    # Modelo puro
    "ExportNote", "WAVE_SHAPES", "pitch_to_freq", "render_notes",
    "write_wav_file", "export_notes_to_wav",
    "DEFAULT_PPQ", "notes_to_midi_bytes", "export_notes_to_midi",
    "export_wav_to_mp3", "MP3_BITRATES",
    "export_wav_to_ogg",
    "export_wav_to_flac",
    # Utils
    "check_ffmpeg_available", "ensure_extension", "get_notes_from_scene",
    # Blender
    "register", "unregister",
]