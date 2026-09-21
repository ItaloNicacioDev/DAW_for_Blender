# modules/effects/bounce.py
"""
Bounce offline de uma SOUND strip por uma cadeia de efeitos.

Fluxo (mesmo do "Aplicar Cadeia de VST a uma Strip"):
    strip de som -> lê o áudio -> processa -> grava WAV -> nova strip
    (a strip original fica mutada, então o resultado substitui o original
    na reprodução sem apagar nada).

Usado pelo mixer (inserts da faixa) e pelo rack de efeitos (cadeia do canal).
"""
from __future__ import annotations

import os
from typing import Callable, Tuple


def _output_dir(subdir: str) -> str:
    import bpy

    # Projeto ainda não salvo: "//" não resolve, então usa a pasta temporária do Blender.
    if bpy.data.filepath:
        return bpy.path.abspath(f"//daw_renders/{subdir}/")
    return os.path.join(bpy.app.tempdir, f"daw_{subdir}")


def bounce_strip(context, strip_name: str, process: Callable, suffix: str = "fx",
                 subdir: str = "inserts") -> Tuple[bool, str]:
    """
    `process(audio, sample_rate)` recebe o áudio como numpy (2, N) float32 e
    devolve o áudio processado (pode ser mais longo, por causa de caudas).
    Retorna (sucesso, mensagem).
    """
    import bpy

    from ..vst import timeline_bridge as tlb

    scene = context.scene
    strip = tlb.find_strip_by_name(scene, strip_name)
    if strip is None or getattr(strip, "sound", None) is None:
        return False, f"Strip de som '{strip_name}' não encontrada"

    sample_rate = int(getattr(getattr(scene, "daw", None), "sample_rate", 44100) or 44100)
    source_path = bpy.path.abspath(strip.sound.filepath)

    try:
        audio = tlb.read_audio_stereo(source_path, sample_rate)
        processed = process(audio, sample_rate)
    except Exception as exc:
        return False, f"Falha ao processar o áudio: {exc}"

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in strip_name)
    out_name = f"{safe}_{suffix}"
    wav_path = os.path.join(_output_dir(subdir), f"{out_name}.wav")

    try:
        tlb.write_wav_stereo(wav_path, processed, sample_rate)
        seq = scene.sequence_editor_create()
        channel = tlb.find_free_channel(seq, min_channel=strip.channel + 1)
        tlb.upsert_sound_strip(scene, out_name, wav_path, channel, strip.frame_start)
    except Exception as exc:
        return False, f"Falha ao criar a strip processada: {exc}"

    strip.mute = True
    return True, f"'{out_name}' criada no canal {channel} — strip original mutada"