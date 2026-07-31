# modules/vst/live_monitor.py
"""
Monitoramento ao vivo: processa efeitos VST sobre o input do microfone
em tempo real, usando uma thread de áudio dedicada.

Por que este arquivo existe:
    O Blender não expõe callback de DSP ao vivo — o motor aud/audaspace
    toca strips pré-renderizadas. Para o usuário ouvir o próprio microfone
    passando pela cadeia de VST effects (como num canal de uma DAW real),
    precisamos de uma thread que:
        1. Abre o dispositivo de entrada (microfone)
        2. Abre o dispositivo de saída (fones/monitores)
        3. A cada bloco: captura -> passa pelos VSTs -> reproduz

    Usa `sounddevice` se disponível (binding leve sobre PortAudio).
    Se não estiver instalado, `start()` retorna (False, mensagem) e o
    botão na UI mostra a opção de instalar.

Uso:
    monitor = get_live_monitor()
    ok, msg = monitor.start(live_vsts=[vst_efeito1, vst_efeito2], sample_rate=44100)
    ...
    monitor.stop()
"""
from __future__ import annotations

import threading
from typing import List, Optional, Tuple

import numpy as np


def _try_import_sounddevice():
    try:
        import sounddevice as sd
        return sd
    except Exception:
        return None


class LiveMonitorState:
    """
    Singleton que gerencia o estado do monitor ao vivo.
    A thread de áudio roda fora da GIL tanto quanto possível (PortAudio
    chama o callback em C, numpy opera sem GIL).
    """
    _instance: Optional["LiveMonitorState"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.is_running = False
        self._stream = None          # sounddevice.Stream ativo
        self._live_vsts: List = []   # lista de VST puros (com bridge carregado)
        self._lock = threading.Lock()
        self._block_size = 512
        self._sample_rate = 44100
        self._error: Optional[str] = None

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------
    def start(
        self,
        live_vsts: List,
        sample_rate: int = 44100,
        block_size: int = 512,
    ) -> Tuple[bool, str]:
        """
        Inicia o monitor ao vivo.

        Args:
            live_vsts: Lista de objetos VST (modelo puro) já carregados,
                       em ordem de processamento (insert 0 → insert N).
            sample_rate: Taxa de amostragem (deve bater com os VSTs carregados).
            block_size: Tamanho do bloco de áudio em amostras.

        Returns:
            (True, "") em caso de sucesso.
            (False, mensagem) se sounddevice não está disponível ou falhou.
        """
        if self.is_running:
            self.stop()

        sd = _try_import_sounddevice()
        if sd is None:
            return False, (
                "sounddevice não está instalado. Instale com:\n"
                f"    <python do Blender> -m pip install sounddevice\n"
                "ou use o botão 'Instalar sounddevice' nas configurações VST."
            )

        with self._lock:
            self._live_vsts = [v for v in live_vsts if v is not None and v.loaded and v.is_effect()]
            self._sample_rate = sample_rate
            self._block_size = block_size
            self._error = None

        try:
            stream = sd.Stream(
                samplerate=sample_rate,
                blocksize=block_size,
                channels=2,
                dtype="float32",
                callback=self._audio_callback,
                latency="low",
            )
            stream.start()
            self._stream = stream
            self.is_running = True
            return True, ""
        except Exception as e:
            self._error = str(e)
            self.is_running = False
            self._stream = None
            return False, f"Falha ao abrir dispositivo de áudio: {e}"

    def stop(self):
        """Para o monitor ao vivo e fecha o dispositivo de áudio."""
        self.is_running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        with self._lock:
            self._live_vsts = []

    # ------------------------------------------------------------------
    # Callback de áudio (chamado pela thread do PortAudio)
    # ------------------------------------------------------------------
    def _audio_callback(self, indata, outdata, frames, time, status):
        """
        Chamado pelo sounddevice a cada bloco.

        indata:  (frames, 2) float32 — entrada do microfone
        outdata: (frames, 2) float32 — saída para o monitor (write-only)
        """
        # Converte para (2, N) — formato esperado pelos VSTs
        audio = indata.T.copy()  # (2, frames)

        with self._lock:
            vsts = list(self._live_vsts)

        for vst in vsts:
            if vst.bypass or not vst.loaded:
                continue
            try:
                audio = vst.process_effect(audio)
            except Exception:
                pass  # se um VST falhar, passa o áudio inalterado para o próximo

        # Reconverte para (frames, 2) para o sounddevice
        if audio.shape == (2, frames):
            outdata[:] = audio.T
        else:
            # fallback: silêncio se shape inesperado
            outdata[:] = 0.0

    # ------------------------------------------------------------------
    # Atualização da cadeia em tempo real
    # ------------------------------------------------------------------
    def update_chain(self, live_vsts: List):
        """
        Troca a cadeia de VSTs sem parar o stream (thread-safe).
        Chame quando o usuário adicionar/remover/reordenar um efeito.
        """
        with self._lock:
            self._live_vsts = [v for v in live_vsts if v is not None and v.loaded and v.is_effect()]

    @property
    def last_error(self) -> Optional[str]:
        return self._error


def get_live_monitor() -> LiveMonitorState:
    """Retorna a instância singleton do monitor ao vivo."""
    return LiveMonitorState()


def install_sounddevice(callback=None) -> None:
    """
    Instala `sounddevice` via pip no Python do Blender, em background.
    callback(success: bool, message: str) é chamado ao final.
    """
    import sys
    import subprocess
    import threading

    def _run():
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "sounddevice"],
                capture_output=True, text=True, timeout=300,
            )
            ok = proc.returncode == 0
            msg = proc.stdout[-2000:] if ok else (proc.stderr[-2000:] or proc.stdout[-2000:])
            if callback:
                callback(ok, msg)
        except Exception as e:
            if callback:
                callback(False, str(e))

    threading.Thread(target=_run, daemon=True).start()