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

[LIMITAÇÃO DA API DO BLENDER -- não é bug deste código] O Pan de uma
`SoundSequence` só tem efeito em fontes de áudio MONO
(bpy.types.SoundSequence.pan: "Playback panning of the sound (only
for Mono sources)"). Se o arquivo importado for estéreo (a maioria dos
loops/samples comerciais é), girar o knob de pan no mixer escreve o
valor certinho em `strip.pan`, mas o Blender simplesmente IGNORA esse
valor na hora de tocar -- não é possível contornar isso via Python, é
uma restrição da própria engine de áudio do VSE. `DAW_LOG_VSE_SYNC`
abaixo imprime um aviso no console a primeira vez que isso acontece
por canal, pra ficar claro que não é o addon que não está funcionando.
"""
from __future__ import annotations

from typing import Iterable

# Liga prints de diagnóstico no console do Blender (Window > Toggle
# System Console, no Windows) toda vez que este módulo escreve nas
# strips -- desligue (False) depois de confirmar que está tudo ok.
DAW_LOG_VSE_SYNC = True

_warned_mono_pan: set = set()


def _all_strips(seq_editor):
    """[FIX API BLENDER 5.x] Devolve todas as strips (recursivo, inclui
    dentro de meta-strips) -- `SequenceEditor.sequences_all` foi
    renomeado pra `strips_all` no Blender 5.x (o nome antigo ainda
    existia como "Deprecated" até a 4.x, mas na 5.2 já não existe mais
    de jeito nenhum -- é isso que causava
    'SequenceEditor' object has no attribute 'sequences_all' e
    derrubava a sincronização inteira). Tenta o nome novo primeiro,
    cai pro antigo se estiver rodando numa versão mais velha do
    Blender."""
    strips_all = getattr(seq_editor, "strips_all", None)
    if strips_all is not None:
        return strips_all
    return getattr(seq_editor, "sequences_all", [])


def _sound_strips_on_channel(scene, vse_channel: int):
    seq_editor = getattr(scene, "sequence_editor", None)
    if seq_editor is None:
        return []
    return [
        s for s in _all_strips(seq_editor)
        if s.type == 'SOUND' and s.channel == vse_channel
    ]


# Público (sem `_`) -- usado pela UI pra decidir se mostra o aviso de
# "Canal VSE sem strip" e pelo operator de auto-fix abaixo. Mesma lógica
# de `_sound_strips_on_channel`, só exposta pra fora deste módulo.
def channel_has_matching_strip(scene, vse_channel: int) -> bool:
    return bool(_sound_strips_on_channel(scene, vse_channel))


def find_vse_channel_with_sound(scene, rack, exclude_index: int = -1) -> "int | None":
    """Varre todas as strips SOUND da timeline e devolve o número do
    primeiro canal do VSE que:
      1. tem pelo menos uma strip de som, e
      2. ainda não está sendo usado como `vse_channel` por NENHUM outro
         canal do rack (senão dois tracks ficariam "escutando" a mesma
         strip -- raramente é o que o usuário quer).

    Usado pelo operator "Auto-detectar Canal VSE" (`DAW_OT_AutoFixVseChannel`
    em operators.py) pra corrigir o caso mostrado no console como
    "NENHUMA strip de som encontrada nesse canal do VSE" sem o usuário
    precisar ficar contando canal por canal na timeline manualmente.
    Devolve None se não achar nenhum canal candidato (ex.: todas as
    strips de som da timeline já estão "reivindicadas" por outros
    tracks, ou não há nenhuma strip de som na cena)."""
    seq_editor = getattr(scene, "sequence_editor", None)
    if seq_editor is None:
        return None

    used = {
        c.vse_channel for i, c in enumerate(rack.channels)
        if i != exclude_index
    }

    channels_with_sound = sorted({
        s.channel for s in _all_strips(seq_editor) if s.type == 'SOUND'
    })
    for vse_channel in channels_with_sound:
        if vse_channel not in used:
            return vse_channel
    return None


def sync_channel_to_vse(channel, scene, any_solo_active: bool) -> None:
    """Escreve o estado de UM canal do Channel Rack nas strips de som
    reais do VSE que estão no `channel.vse_channel` dele."""
    strips = _sound_strips_on_channel(scene, getattr(channel, "vse_channel", 1))
    if not strips:
        if DAW_LOG_VSE_SYNC:
            print(f"[DAW][vse_sync] Canal '{channel.name}' (vse_channel="
                  f"{getattr(channel, 'vse_channel', '?')}) -- NENHUMA strip de "
                  f"som encontrada nesse canal do VSE. Confira se o número do "
                  f"'Canal VSE' do canal bate com o canal onde a strip está na "
                  f"timeline.")
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
                # [LIMITAÇÃO DA API] avisa uma vez por strip se a fonte
                # for estéreo -- o pan nunca vai soar, mesmo escrito
                # certinho (ver docstring do módulo).
                sound = getattr(strip, "sound", None)
                if (DAW_LOG_VSE_SYNC and sound is not None
                        and getattr(sound, "use_mono", None) is False
                        and strip.name not in _warned_mono_pan):
                    _warned_mono_pan.add(strip.name)
                    print(f"[DAW][vse_sync] Aviso: a strip '{strip.name}' é "
                          f"ESTÉREO -- o Pan do Blender só funciona em fontes "
                          f"MONO (limitação da própria API, não do addon). O "
                          f"volume continua funcionando normalmente.")
        except (AttributeError, ReferenceError):
            # strip pode ter sido removida entre o find e o write (raro,
            # mas evita crashar o update callback por causa disso)
            continue
        else:
            if DAW_LOG_VSE_SYNC:
                print(f"[DAW][vse_sync] '{channel.name}' -> strip '{strip.name}' "
                      f"(canal VSE {strip.channel}): volume={volume:.3f} "
                      f"pan={pan:.2f} mute={effective_mute}")


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