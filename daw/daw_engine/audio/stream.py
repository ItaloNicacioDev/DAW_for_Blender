"""
Audio Stream

Responsável apenas pela criação e controle do OutputStream.

`sounddevice` é uma dependência OPCIONAL (não vem com o Python do
Blender) — o import é adiado para dentro dos métodos, então importar
este módulo (ou o pacote `daw_engine` inteiro) nunca falha por causa
dela. Sem `sounddevice` instalado, `start()` levanta `RuntimeError`
com instruções; o resto da engine (clock/transport/scheduler/mixer
lógico) continua funcionando normalmente sem áudio real.
"""

from __future__ import annotations

import sys

from .config import ENGINE_CONFIG

_sd_module = None
_sd_checked = False
_sd_import_error: str | None = None


def _try_import_sounddevice():
    global _sd_module, _sd_checked, _sd_import_error
    if _sd_checked:
        return _sd_module
    _sd_checked = True
    try:
        import sounddevice as sd  # type: ignore
        _sd_module = sd
        _sd_import_error = None
    except Exception as e:
        _sd_module = None
        _sd_import_error = str(e)
    return _sd_module


def is_available() -> bool:
    """True se `sounddevice` está disponível no Python em uso."""
    return _try_import_sounddevice() is not None


def install_instructions() -> str:
    """Mensagem amigável explicando como instalar `sounddevice`."""
    py = sys.executable
    reason = f" (detalhe: {_sd_import_error})" if _sd_import_error else ""
    return (
        "sounddevice não está disponível — a síntese em Python puro do "
        "daw_engine não vai produzir áudio real até ele ser instalado.\n\n"
        f'Instalação manual (direto no Python do Blender, sem venv):\n'
        f'    "{py}" -m pip install sounddevice\n\n'
        "Ou use o botão \"Instalar sounddevice\" nas Preferências do addon."
        + reason
    )


def install_sounddevice(callback=None) -> None:
    """Instala `sounddevice` via pip no Python do Blender, em background.
    `callback(success: bool, message: str)` é chamado ao final, se dado."""
    import subprocess
    import threading

    def _run():
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "sounddevice"])
            global _sd_checked
            _sd_checked = False  # força reimport na próxima checagem
            ok, msg = is_available(), "sounddevice instalado com sucesso."
        except Exception as e:
            ok, msg = False, f"Falha ao instalar sounddevice: {e}"
        if callback:
            callback(ok, msg)

    threading.Thread(target=_run, daemon=True).start()


class OutputStream:

    def __init__(self, callback):
        self.callback = callback
        self.stream = None

    # ------------------------------------------

    def start(self):
        if self.stream is not None:
            return

        sd = _try_import_sounddevice()
        if sd is None:
            raise RuntimeError(install_instructions())

        self.stream = sd.OutputStream(
            samplerate=ENGINE_CONFIG.sample_rate,
            channels=ENGINE_CONFIG.channels,
            blocksize=ENGINE_CONFIG.buffer_size,
            dtype=ENGINE_CONFIG.sample_format.value,
            callback=self.callback,
            latency=ENGINE_CONFIG.latency,
        )
        self.stream.start()

    # ------------------------------------------

    def stop(self):
        if self.stream is None:
            return
        self.stream.stop()
        self.stream.close()
        self.stream = None

    # ------------------------------------------

    @property
    def active(self):
        return (
            self.stream is not None
            and self.stream.active
        )