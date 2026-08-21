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
    Channel Rack. Duas fontes de dado REAL, nessa ordem de prioridade:

      1. Preview manual (ver preview.py / DAW_OT_PreviewChannel): se o
         usuário clicou ▶ neste canal, `ChannelPreviewPlayer.poll_level()`
         devolve o RMS real da amostra tocando, janela a janela.
      2. `monitor_source == 'INPUT'`: lê o peak do dispositivo de entrada
         configurado globalmente (mesmo `InputDeviceManager` do módulo
         recorder). Vários tracks com INPUT ao mesmo tempo leem o MESMO
         dispositivo -- só existe um stream de captura compartilhado.

    Se nenhuma das duas fontes tiver dado novo pra este canal, o
    medidor decai suavemente até 0 -- IMPORTANTE: hoje não existe
    nenhum scheduler ligando o Channel Rack à reprodução automática da
    timeline (ver rack.py -- `core/engine.py` não referencia o Channel
    Rack), então fora do preview manual e do monitor de entrada, o
    medidor não tem de onde tirar um nível real. Não fabricamos uma
    animação falsa pra disfarçar isso.
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

    from .preview import get_preview_player
    player = get_preview_player()

    for ch in rack.channels:
        preview_level = player.poll_level(ch.name)
        if preview_level is not None:
            ch.meter_level = max(0.0, min(1.0, preview_level))
        elif ch.monitor_source == 'INPUT':
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