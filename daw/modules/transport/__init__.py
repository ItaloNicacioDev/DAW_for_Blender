"""transport/__init__.py

Pacote de transporte da DAW: play, pause, stop, record, loop e
controle de tempo (BPM). Expõe `register()`/`unregister()` para serem
chamados pelo addon principal, ex.:

    from . import transport

    def register():
        transport.register()

    def unregister():
        transport.unregister()
"""

from .register import register, unregister

__all__ = ("register", "unregister")