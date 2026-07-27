# modules/metronome/sounds.py
"""
Reprodução dos sons do metrônomo via módulo `aud` do Blender (Audaspace).

Responsabilidade:
    Carregar (com cache) os PCM gerados por click.py em objetos
    `aud.Sound` e tocá-los pelo dispositivo de áudio do Blender — mesmo
    padrão usado por instruments/synth.py.
"""
from __future__ import annotations

import tempfile
import wave
from typing import Dict, Optional, Tuple

import aud

from .click import generate_click_pcm, SOUND_STYLES, SAMPLE_RATE

_device: Optional["aud.Device"] = None
_sound_cache: Dict[Tuple[str, bool], "aud.Sound"] = {}
# Mantém referência aos Handles em reprodução (ver play_click) — sem isso
# o Handle retornado por dev.play() é coletado pelo Python assim que a
# função termina e o clique é cortado antes de ser ouvido.
_active_handles: list = []


def _get_device() -> Optional["aud.Device"]:
    global _device
    if _device is None:
        try:
            _device = aud.Device()
        except Exception as e:
            print(f"[DAW Metronome] Erro ao abrir dispositivo de áudio: {e}")
    return _device


def _pcm_to_sound(pcm: bytes) -> "aud.Sound":
    """Converte um buffer PCM em aud.Sound, com fallback para arquivo .wav temporário."""
    try:
        return aud.Sound.buffer(pcm, SAMPLE_RATE, 1, aud.FORMAT_S16)
    except AttributeError:
        try:
            return aud.Sound.data(pcm, SAMPLE_RATE, 1, aud.FORMAT_S16)
        except Exception:
            tmp = tempfile.mktemp(suffix=".wav")
            with wave.open(tmp, "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(pcm)
            return aud.Sound(tmp)


def _get_cached_sound(style: str, accent: bool) -> "aud.Sound":
    key = (style, accent)
    if key not in _sound_cache:
        pcm = generate_click_pcm(style, accent)
        _sound_cache[key] = _pcm_to_sound(pcm)
    return _sound_cache[key]


def preload_all() -> None:
    """Pré-carrega todos os estilos/variantes no cache (evita latência no primeiro clique)."""
    for style in SOUND_STYLES:
        _get_cached_sound(style, True)
        _get_cached_sound(style, False)


def play_click(style: str = "CLICK", accent: bool = False, volume: float = 0.8) -> None:
    """Toca um clique do metrônomo imediatamente pelo dispositivo de áudio do Blender."""
    try:
        dev = _get_device()
        if dev is None:
            return

        sound = _get_cached_sound(style, accent)
        handle = dev.play(sound)
        try:
            handle.volume = max(0.0, min(1.0, volume))
        except Exception:
            pass

        _active_handles.append(handle)
        if len(_active_handles) > 64:
            del _active_handles[:len(_active_handles) - 64]

    except Exception as e:
        print(f"[DAW Metronome] Erro ao tocar clique ({style}, accent={accent}): {e}")


def clear_cache() -> None:
    """Limpa o cache de sons (ex: se quisermos forçar regeneração)."""
    _sound_cache.clear()