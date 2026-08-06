"""
Master Output
"""

from __future__ import annotations

from .callback import AudioCallback
from .stream import OutputStream, is_available, install_instructions, install_sounddevice


class AudioOutput:

    def __init__(self):
        self.callback = AudioCallback()
        self.stream = OutputStream(self.callback)

    # -------------------------------------

    def set_generator(self, generator):
        self.callback.set_generator(generator)

    # -------------------------------------

    def start(self):
        """Inicia a saída de áudio real. Levanta RuntimeError com
        instruções se `sounddevice` não estiver instalado — ver
        `start_safe()` para uma versão que não levanta exceção."""
        self.stream.start()

    def start_safe(self):
        """Como `start()`, mas nunca levanta exceção: retorna
        (sucesso, mensagem). Use isto ao iniciar automaticamente com o
        addon, onde `sounddevice` ausente é uma situação normal/esperada
        (dependência opcional), não um erro fatal."""
        if not is_available():
            return False, install_instructions()
        try:
            self.stream.start()
            return True, "Saída de áudio (sounddevice) iniciada."
        except Exception as e:
            return False, f"Falha ao iniciar saída de áudio: {e}"

    # -------------------------------------

    def stop(self):
        self.stream.stop()

    # -------------------------------------

    @property
    def active(self):
        return self.stream.active