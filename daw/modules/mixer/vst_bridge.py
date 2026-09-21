# modules/mixer/vst_bridge.py
"""
Ponte entre a cadeia de inserts de uma faixa do mixer (tracks.py /
properties.py) e o motor real de VST (modules/vst).

Um insert do mixer só carrega um plugin de verdade quando seu
`effect_type == 'VST'` (ver effects.py, inserts.py, properties.py --
`MixerInsertSlotProperties.vst`). Os inserts dos tipos embutidos (EQ,
Compressor etc.) são processados por `modules/effects/dsp.py` (numpy).

`apply_inserts_to_audio(track, audio, sample_rate)` aplica a cadeia
COMPLETA (embutidos + VST) na ordem em que aparece na faixa. É o que o
operador `daw.mixer_apply_inserts_to_strip` usa. A versão antiga,
`apply_vst_inserts_to_audio`, aplica só os VSTs e continua disponível.
"""
from __future__ import annotations

from typing import Any


def _slot_to_dict(slot) -> dict:
    """Converte um insert RNA para o dict que `effects.dsp.apply_chain` entende."""
    return {
        "effect_type": slot.effect_type,
        "enabled": bool(slot.enabled),
        "bypass": bool(slot.bypass),
        "params": {p.name: p.value for p in slot.params},
        "_slot": slot,      # referência ao insert RNA (o handler de VST precisa dela)
    }


def _process_vst_slot(slot_dict, frames, sample_rate):
    """Handler de VST para `apply_chain`. `frames` tem shape (N, canais)."""
    import numpy as np

    from ..vst.timeline_bridge import apply_effect_chain_to_audio
    from ..vst.utils import get_live_vst

    stereo = np.ascontiguousarray(frames[:, :2].T, dtype=np.float32)     # (2, N)
    out = apply_effect_chain_to_audio([slot_dict["_slot"].vst], get_live_vst, stereo, sample_rate=sample_rate)
    out = np.asarray(out, dtype=np.float64)
    if out.ndim == 2 and out.shape[0] <= 2 < out.shape[1]:
        out = out.T
    if out.shape[0] != frames.shape[0]:                                   # garante o mesmo tamanho
        fixed = np.zeros_like(frames)
        n = min(out.shape[0], frames.shape[0])
        fixed[:n, :out.shape[1]] = out[:n]
        out = fixed
    if out.shape[1] != frames.shape[1]:
        out = np.repeat(out[:, :1], frames.shape[1], axis=1)
    return out


def apply_inserts_to_audio(track, audio, sample_rate: int = 44100, with_tail: bool = True):
    """
    Processa `audio` pela cadeia completa de inserts de `track` (efeitos
    embutidos + VST), respeitando ordem, `enabled` e `bypass`.

    Com `with_tail=True` o áudio devolvido pode ser mais longo que o de
    entrada (cauda de delay/reverb).
    """
    from ..effects import dsp

    slots = [_slot_to_dict(s) for s in track.inserts]
    return dsp.apply_chain(
        slots, audio, sample_rate,
        external={"VST": _process_vst_slot},
        with_tail=with_tail,
    )


def has_active_inserts(track) -> bool:
    return any(s.enabled and not s.bypass for s in track.inserts)


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