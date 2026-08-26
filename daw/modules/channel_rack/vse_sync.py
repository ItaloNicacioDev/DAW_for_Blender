# modules/channel_rack/vse_sync.py
"""
Ponte DIRETA entre os controles do canal do Channel Rack
(volume/pan/mute/solo) e as strips de som de verdade no VSE.

Por que isso precisava existir: os controles do card do mixer (ver
mixer_strip_*.py) sempre mexeram em `ChannelProperties.volume/pan/
mute/solo` -- e isso alimenta o medidor e o `daw_engine` (canais
SYNTH). Só que canais SAMPLER/AUDIO/DRUM tocam pela engine NATIVA de
áudio do VSE do Blender, que só liga pra `strip.volume`/`strip.pan`/
`strip.mute` de cada strip de som -- nada nessas propriedades do
Channel Rack chegava até lá. Resultado: os botões respondiam
visualmente, mas o som que saía continuava exatamente o mesmo, porque
a strip nunca sabia que o fader tinha mexido.

Chamado a partir de `update=` callbacks nas próprias propriedades (ver
properties.py) -- ou seja, roda IMEDIATAMENTE a cada arraste do
fader/knob ou clique em M/S, mesmo com o Blender parado/pausado (não
depende de play nem de nenhum timer).
"""
from __future__ import annotations

from typing import Iterable


def _sound_strips_on_channel(scene, vse_channel: int):
    seq_editor = getattr(scene, "sequence_editor", None)
    if seq_editor is None:
        return []
    return [
        s for s in seq_editor.sequences_all
        if s.type == 'SOUND' and s.channel == vse_channel
    ]


def sync_channel_to_vse(channel, scene, any_solo_active: bool) -> None:
    """Escreve o estado de UM canal do Channel Rack nas strips de som
    reais do VSE que estão no `channel.vse_channel` dele."""
    strips = _sound_strips_on_channel(scene, getattr(channel, "vse_channel", 1))
    if not strips:
        return

    # Solo: se QUALQUER canal do rack está em solo, todo canal que não
    # está em solo fica efetivamente mudo -- é assim que solo funciona
    # em qualquer mixer de DAW (ver descrição do campo em
    # properties.py: "isola o canal, silencia os demais").
    effective_mute = bool(channel.mute) or (any_solo_active and not channel.solo)

    volume = max(0.0, min(1.0, getattr(channel, "volume", 1.0)))
    pan = max(-1.0, min(1.0, getattr(channel, "pan", 0.0)))

    for strip in strips:
        try:
            strip.volume = volume
            strip.mute = effective_mute
            if hasattr(strip, "pan"):
                strip.pan = pan
        except (AttributeError, ReferenceError):
            # strip pode ter sido removida entre o find e o write (raro,
            # mas evita crashar o update callback por causa disso)
            continue


def sync_all_channels_to_vse(rack, scene) -> None:
    """Ressincroniza TODOS os canais -- necessário quando o estado de
    solo muda, já que isso afeta o mute efetivo de canais que nem
    foram tocados (ver `sync_channel_to_vse`)."""
    any_solo_active = any(bool(ch.solo) for ch in rack.channels)
    for ch in rack.channels:
        sync_channel_to_vse(ch, scene, any_solo_active)


def sync_from_channel_update(channel, context) -> None:
    """Callback de conveniência pra usar direto em `update=` de
    volume/pan/mute -- só precisa ressincronizar ESTE canal (não afeta
    o mute efetivo de nenhum outro)."""
    scene = context.scene
    rack = getattr(scene, "daw_channel_rack", None)
    if rack is None:
        return
    any_solo_active = any(bool(ch.solo) for ch in rack.channels)
    sync_channel_to_vse(channel, scene, any_solo_active)


def sync_from_solo_update(channel, context) -> None:
    """Callback de conveniência pra usar em `update=` de `solo` --
    precisa ressincronizar TODOS os canais (mudar o solo de um afeta o
    mute efetivo dos outros)."""
    scene = context.scene
    rack = getattr(scene, "daw_channel_rack", None)
    if rack is None:
        return
    sync_all_channels_to_vse(rack, scene)