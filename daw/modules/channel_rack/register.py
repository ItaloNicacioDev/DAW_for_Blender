# modules/channel_rack/register.py
"""
Registro e desregistro do módulo Channel Rack no Blender.
Chamado por daw/__init__.py (ou pelo módulo pai) no register()/unregister().
"""
from __future__ import annotations

import bpy

from .properties import (
    ChannelProperties,
    ChannelGroupProperties,
    ChannelRackProperties,
)
from .operators import classes as operator_classes
from .ui import classes as ui_classes
from .icons import clear_color_icon_cache


_all_classes = [
    ChannelProperties,
    ChannelGroupProperties,
    ChannelRackProperties,
    *operator_classes,
    *ui_classes,
]

METER_TICK_INTERVAL = 0.1  # ~10x/seg -- suave o bastante pro olho, barato o bastante pra não pesar
METER_DECAY_PER_TICK = 0.3  # fração do nível anterior mantida a cada tick sem sinal novo (efeito "caindo")


def _meter_update_tick():
    """
    Roda a cada METER_TICK_INTERVAL segundos (bpy.app.timers) enquanto o
    addon está ativo, atualizando `channel.meter_level` de cada track do
    Channel Rack:

      - `monitor_source == 'INPUT'`: lê o peak atual do dispositivo de
        entrada configurado globalmente (mesmo `InputDeviceManager` que
        o módulo recorder usa -- ver modules/recorder/input.py). Vários
        tracks com monitor_source=INPUT ao mesmo tempo todos leem o
        MESMO dispositivo (só existe um stream de entrada compartilhado
        no momento) -- é uma limitação honesta: não dá pra monitorar
        entradas físicas DIFERENTES por track sem múltiplos streams de
        captura simultâneos, que não estão implementados.
      - `monitor_source == 'NONE'` (tracks de instrumento/sample sem
        fonte de entrada ao vivo): o medidor não tem de onde ler um
        nível de verdade (Blender não expõe o áudio por-canal/por-strip
        do VSE durante o playback via API pública), então só decai
        suavemente até 0 em vez de ficar travado num valor antigo.

    Retorna METER_TICK_INTERVAL pra bpy.app.timers reagendar; nunca
    retorna None (o que cancelaria o timer) a menos que o addon tenha
    sido desregistrado (ver `_meter_timer_registered`).
    """
    if not _meter_timer_registered[0]:
        return None  # addon foi desregistrado -- para o timer

    try:
        scene = bpy.context.scene
    except Exception:
        return METER_TICK_INTERVAL
    if scene is None or not hasattr(scene, "daw_channel_rack"):
        return METER_TICK_INTERVAL

    rack = scene.daw_channel_rack
    has_input_monitor = any(ch.monitor_source == 'INPUT' for ch in rack.channels)

    input_peak = 0.0
    if has_input_monitor:
        try:
            from ..recorder.input import get_input_manager
            mgr = get_input_manager()
            input_peak, _rms = mgr.get_levels()
        except Exception:
            input_peak = 0.0

    for ch in rack.channels:
        if ch.monitor_source == 'INPUT':
            ch.meter_level = max(0.0, min(1.0, float(input_peak)))
        else:
            ch.meter_level = ch.meter_level * METER_DECAY_PER_TICK

    return METER_TICK_INTERVAL


# Lista de 1 elemento em vez de bool solto -- closure em `_meter_update_tick`
# precisa de algo mutável que `unregister()` consiga desligar de fora.
_meter_timer_registered = [False]


def register():
    for cls in _all_classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)

    bpy.types.Scene.daw_channel_rack = bpy.props.PointerProperty(
        type=ChannelRackProperties
    )

    if not _meter_timer_registered[0]:
        _meter_timer_registered[0] = True
        bpy.app.timers.register(_meter_update_tick, first_interval=METER_TICK_INTERVAL)

    print("[DAW] Módulo channel_rack registrado")


def unregister():
    _meter_timer_registered[0] = False  # próximo tick do timer se auto-cancela

    clear_color_icon_cache()

    if hasattr(bpy.types.Scene, "daw_channel_rack"):
        del bpy.types.Scene.daw_channel_rack

    for cls in reversed(_all_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    print("[DAW] Módulo channel_rack desregistrado")