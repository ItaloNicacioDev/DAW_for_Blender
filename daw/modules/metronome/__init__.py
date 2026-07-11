# modules/metronome/__init__.py
"""
Módulo Metrônomo da DAW.

Responsabilidade:
    Metrônomo funcional com timer real (wall-clock), 4 timbres de clique
    sintetizados em Python puro, acento no primeiro beat, fórmula de
    compasso configurável, modo prática (independente da reprodução) e
    tap tempo.

    Reaproveita context.scene.daw.metronome (já existente em
    core/register.py) como liga/desliga principal, e adiciona
    configurações finas em context.scene.daw_metronome.

Arquitetura:
    click.py       — síntese pura-Python dos cliques (sem bpy)
    sounds.py      — carrega o PCM em aud.Sound e toca (usa `aud`, como synth.py)
    utils.py       — cálculos de tempo/beat e acesso às propriedades da cena
    properties.py  — PropertyGroup do Blender (configurações finas)
    operators.py   — operator modal (o "coração" do metrônomo) + toggle + tap tempo
    ui.py          — Painel do Blender
    register.py    — register() / unregister()

Uso fora do Blender (testes), a partir do modelo puro:
    from daw.modules.metronome.click import generate_click_pcm
    pcm = generate_click_pcm("CLICK", accent=True)

Uso a partir do Blender:
    bpy.ops.daw.metronome_toggle()  # liga/desliga e inicia o timer
"""
from __future__ import annotations

from .click import generate_click_pcm, all_variants_pcm, SOUND_STYLES
from .utils import (
    seconds_per_beat,
    beat_index_to_bar_beat,
    is_accent_beat,
    should_click_now,
    clamp_bpm,
    get_daw_props,
    get_metronome_props,
)
from .register import register, unregister

__all__ = [
    # Síntese pura
    "generate_click_pcm", "all_variants_pcm", "SOUND_STYLES",
    # Utils
    "seconds_per_beat", "beat_index_to_bar_beat", "is_accent_beat",
    "should_click_now", "clamp_bpm", "get_daw_props", "get_metronome_props",
    # Blender
    "register", "unregister",
]
