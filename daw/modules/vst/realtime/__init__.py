# modules/vst/realtime/__init__.py
"""
Playback quase-tempo-real via pré-render adiantado do playhead.

Ver arquitetura_realtime_playback.md para o desenho completo. Resumo:

    RingBuffer        -- buffer circular de áudio indexado por tempo
                          absoluto (ring_buffer.py). Sem bpy/aud/dawdreamer.
    PrefetchThread     -- mantém o RingBuffer preenchido à frente do
                          playhead, chamando live_vst.bridge.stream_*()
                          (prefetch.py). Sem bpy/aud.
    PlaybackSupervisor -- orquestra as duas coisas acima, plugadas no
                          bpy.app.timers e no aud (supervisor.py,
                          aud_source.py). PRECISA de Blender pra rodar
                          e ainda não foi validado em produção -- ver
                          "Ordem de implementação recomendada" no
                          documento de arquitetura.
"""
from .ring_buffer import RingBuffer
from .prefetch import PrefetchThread

__all__ = ["RingBuffer", "PrefetchThread"]