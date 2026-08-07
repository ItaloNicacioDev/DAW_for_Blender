# modules/metronome/utils.py
"""
Utilitários do metrônomo.

Responsabilidade:
    Cálculos de tempo (segundos por beat, posição de beat/compasso) e
    acesso conveniente às propriedades da cena, usados pelo modal
    operator em operators.py.
"""
from __future__ import annotations

from typing import Tuple


def get_daw_props(context):
    """Retorna context.scene.daw_transport (BPM, is_playing, current_bar/current_beat, metronome on/off).

    Nota: o estado de transporte NÃO vive em `scene.daw` (que só guarda
    metadado de projeto — nome, sample rate, bit depth). Ele vive em
    `scene.daw_transport` (ver modules/transport/properties.py).
    """
    return context.scene.daw_transport


def get_metronome_props(context):
    """Retorna context.scene.daw_metronome (configurações finas do metrônomo)."""
    return context.scene.daw_metronome


def seconds_per_beat(bpm: float) -> float:
    """Duração de um beat (semínima) em segundos, dado o BPM."""
    return 60.0 / max(1.0, bpm)


def beat_index_to_bar_beat(beat_index: int, beats_per_bar: int) -> Tuple[int, int]:
    """
    Converte um índice de beat absoluto (0-based, desde o início) em
    (compasso, beat_dentro_do_compasso), ambos 1-based — para exibir na UI.
    """
    beats_per_bar = max(1, beats_per_bar)
    bar = (beat_index // beats_per_bar) + 1
    beat_in_bar = (beat_index % beats_per_bar) + 1
    return bar, beat_in_bar


def is_accent_beat(beat_index: int, beats_per_bar: int, accent_enabled: bool) -> bool:
    """Determina se o beat atual deve soar acentuado (primeiro beat do compasso)."""
    if not accent_enabled:
        return False
    return (beat_index % max(1, beats_per_bar)) == 0


def should_click_now(context) -> bool:
    """
    Decide se o metrônomo deve efetivamente soar neste instante, considerando
    o liga/desliga (scene.daw.metronome) e a opção de sincronizar com a
    reprodução (scene.daw_metronome.sync_with_playback).
    """
    daw = get_daw_props(context)
    metro = get_metronome_props(context)

    if not daw.metronome_enabled:
        return False
    if metro.sync_with_playback and not daw.is_playing:
        return False
    return True


def clamp_bpm(bpm: float, min_bpm: float = 20.0, max_bpm: float = 999.0) -> float:
    return max(min_bpm, min(max_bpm, bpm))