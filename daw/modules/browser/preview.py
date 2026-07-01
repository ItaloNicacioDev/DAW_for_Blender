# modules/browser/preview.py
"""
Preview de áudio no browser.

Toca um arquivo de áudio em thread separada sem bloquear o Blender.
Usa sounddevice + soundfile (mesmas dependências da engine de áudio).
Sem bpy.
"""
from __future__ import annotations

import threading
from typing import Optional


class AudioPreview:
    """
    Reproduz um arquivo de áudio em preview (sem registrar na timeline).

    Ciclo:
        preview.play(path)   → inicia em thread separada
        preview.stop()       → para imediatamente
        preview.is_playing   → True enquanto estiver tocando
    """

    def __init__(self) -> None:
        self._thread:   Optional[threading.Thread] = None
        self._stop_evt: threading.Event            = threading.Event()
        self._current:  Optional[str]              = None
        self.volume:    float                      = 0.8

    def play(self, path: str) -> None:
        """Toca o arquivo. Para qualquer preview anterior antes de iniciar."""
        self.stop()
        self._current   = path
        self._stop_evt  = threading.Event()
        self._thread    = threading.Thread(
            target=self._run,
            args=(path, self._stop_evt),
            daemon=True,
            name="daw-preview",
        )
        self._thread.start()

    def stop(self) -> None:
        """Para o preview imediatamente."""
        if self._thread and self._thread.is_alive():
            self._stop_evt.set()
            self._thread.join(timeout=1.0)
        self._current = None

    @property
    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def current_file(self) -> Optional[str]:
        return self._current

    # ------------------------------------------------------------------
    # Thread de reprodução
    # ------------------------------------------------------------------

    def _run(self, path: str, stop_event: threading.Event) -> None:
        """
        Executa em thread daemon — carrega e toca o arquivo em blocos,
        verificando stop_event a cada bloco para parada imediata.
        """
        try:
            import soundfile as sf
            import sounddevice as sd
            import numpy as np

            BLOCK = 2048
            with sf.SoundFile(path) as f:
                sr = f.samplerate
                ch = f.channels

                with sd.OutputStream(
                    samplerate=sr,
                    channels=ch,
                    dtype="float32",
                ) as stream:
                    while not stop_event.is_set():
                        data = f.read(BLOCK, dtype="float32", always_2d=True)
                        if len(data) == 0:
                            break
                        stream.write(data * self.volume)

        except ImportError:
            # soundfile/sounddevice não instalado — preview silencioso
            pass
        except Exception:
            pass
        finally:
            self._current = None

    def __repr__(self) -> str:
        status = f"playing '{self._current}'" if self.is_playing else "idle"
        return f"AudioPreview({status})"


# Instância global
PREVIEW = AudioPreview()