# modules/mixer/vst_bridge.py
"""
Ponte entre a cadeia de inserts de uma faixa do mixer (tracks.py /
properties.py) e o motor real de VST (modules/vst).

Um insert do mixer só carrega um plugin de verdade quando seu
`effect_type == 'VST'` (ver effects.py, inserts.py, properties.py --
`MixerInsertSlotProperties.vst`). Inserts dos tipos embutidos (EQ,
Compressor etc.) ainda não têm processamento de áudio implementado em
lugar nenhum do addon -- isso é responsabilidade de um módulo de DSP
que ainda não existe, não deste arquivo.

Quem for renderizar/bounce uma faixa do mixer no futuro chama
`apply_vst_inserts_to_audio(track, audio, sample_rate)` depois de
somar as fontes de áudio da faixa.
"""
from __future__ import annotations

from typing import Any


def apply_vst_inserts_to_audio(track, audio, sample_rate: int = 44100):
    """
    Processa `audio` (numpy estéreo, shape (canais, amostras) ou
    (amostras, canais) -- ver VST.process_effect) através de todos os
    inserts do tipo VST, não-bypassed e carregados, de `track`, na
    ordem em que aparecem na cadeia. Inserts de outros tipos são
    ignorados (passthrough) até terem processamento próprio.
    """
    from ..vst.timeline_bridge import apply_effect_chain_to_audio
    from ..vst.utils import get_live_vst

    vst_items = [slot.vst for slot in track.inserts if slot.effect_type == 'VST' and slot.enabled]
    if not vst_items:
        return audio

    return apply_effect_chain_to_audio(vst_items, get_live_vst, audio, sample_rate=sample_rate)