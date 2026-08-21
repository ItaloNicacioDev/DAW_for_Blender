# modules/channel_rack/preview.py
"""
Preview de áudio por canal do Channel Rack.

Toca a amostra do canal (`channel.sample_path`) via `sounddevice` e
alimenta `channel.meter_level` com o nível REAL da amostra, janela a
janela, enquanto ela toca -- não é uma animação decorativa. Não existe
hoje (ver rack.py) nenhum scheduler ligando o Channel Rack à
reprodução da timeline (`core/engine.py` não referencia o Channel
Rack), então o preview manual é a única fonte de áudio "de verdade"
disponível pra esse medidor por enquanto -- documentado explicitamente
aqui pra não passar a impressão de que o rack já tem playback
automático.

Suporta WAV nativamente (`wave`, biblioteca padrão -- sem dependência
extra). Para outros formatos, tenta via `soundfile` se estiver
instalado; se não conseguir ler de jeito nenhum, retorna erro claro em
vez de falhar silenciosamente.
"""
from __future__ import annotations

from typing import Optional

import numpy as np


def _load_audio(path: str):
    """Carrega um arquivo de áudio como (data float32 mono, samplerate).
    Lança RuntimeError com mensagem clara em caso de falha."""
    if path.lower().endswith(".wav"):
        try:
            import wave
            with wave.open(path, "rb") as wf:
                sr = wf.getframerate()
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)

            if sampwidth == 2:
                data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sampwidth == 4:
                data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
            elif sampwidth == 1:
                data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
            else:
                raise RuntimeError(f"WAV com {sampwidth * 8} bits/amostra não suportado")

            if n_channels > 1:
                data = data.reshape(-1, n_channels).mean(axis=1)
            return data, sr
        except Exception as e:
            raise RuntimeError(f"falha ao ler WAV: {e}")

    # Formatos não-WAV: tenta soundfile, se disponível.
    try:
        import soundfile as sf
        data, sr = sf.read(path, dtype='float32', always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        return data, sr
    except ImportError:
        raise RuntimeError(
            "apenas .wav é suportado sem dependências extras -- instale "
            "'soundfile' no Python do Blender pra tocar outros formatos"
        )
    except Exception as e:
        raise RuntimeError(f"falha ao ler áudio: {e}")


def compute_rms_windows(data: np.ndarray, samplerate: int, window_seconds: float = 0.05):
    """
    Divide `data` em janelas de `window_seconds` e calcula o RMS de cada
    uma -- é a mesma amostra que vai tocar, só pré-analisada uma vez
    (barato, roda antes de começar a tocar) pra depois o timer só
    consultar o índice certo, sem reprocessar áudio a cada tick.
    """
    window_size = max(1, int(window_seconds * samplerate))
    n_windows = max(1, int(np.ceil(len(data) / window_size)))
    levels = np.zeros(n_windows, dtype=np.float32)
    for i in range(n_windows):
        chunk = data[i * window_size:(i + 1) * window_size]
        if len(chunk) > 0:
            levels[i] = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
    return levels, window_seconds


class ChannelPreviewPlayer:
    """
    Um preview ativo por vez (tocar um segundo canal cancela o anterior
    -- evita medidores de dois canais brigando pelo mesmo `sounddevice.play`
    global). Ver DAW_OT_PreviewChannel em operators.py, que é quem chama isso.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._active_channel_name = None
            cls._instance._rms_windows = None
            cls._instance._window_seconds = 0.05
            cls._instance._elapsed_windows = 0
        return cls._instance

    def play(self, channel_name: str, path: str, gain: float = 1.0) -> Optional[str]:
        """Toca `path` e prepara os dados pro timer de metering ler.
        Retorna uma mensagem de erro (str) em caso de falha, ou None se ok."""
        try:
            import sounddevice as sd
        except Exception as e:
            return f"sounddevice não disponível: {e}"

        try:
            data, sr = _load_audio(path)
        except RuntimeError as e:
            return str(e)

        data = np.ascontiguousarray(data * gain, dtype=np.float32)
        levels, window_seconds = compute_rms_windows(data, sr)

        self._active_channel_name = channel_name
        self._rms_windows = levels
        self._window_seconds = window_seconds
        self._elapsed_windows = 0

        try:
            from ..recorder.input import resolve_device_index, get_default_output_identifier
        except Exception:
            resolve_device_index = None
            get_default_output_identifier = None

        device_id = None
        if resolve_device_index is not None:
            try:
                device_id = resolve_device_index(get_default_output_identifier())
            except Exception:
                pass  # cai pro dispositivo padrão do sistema

        try:
            sd.play(data, samplerate=sr, device=device_id, blocking=False)
        except Exception as e:
            return f"falha ao tocar: {e}"
        return None

    def poll_level(self, channel_name: str) -> Optional[float]:
        """
        Chamado pelo timer periódico (ver register.py) pra saber o nível
        (0.0-1.0) da janela atual do preview em andamento. Retorna None
        se este canal não é o que está tocando agora, ou se o preview já
        terminou -- nesses casos o chamador deve deixar o medidor decair
        normalmente, não travar num valor antigo.
        """
        if channel_name != self._active_channel_name or self._rms_windows is None:
            return None

        idx = self._elapsed_windows
        self._elapsed_windows += 1

        if idx >= len(self._rms_windows):
            self._active_channel_name = None
            self._rms_windows = None
            return None

        # RMS bruto não é 0-1 diretamente -- normaliza numa faixa
        # perceptualmente razoável pro medidor (RMS de 0.3 já é "bem
        # alto" pra a maioria dos samples mixados razoavelmente).
        raw = float(self._rms_windows[idx])
        return max(0.0, min(1.0, raw / 0.3))


def get_preview_player() -> ChannelPreviewPlayer:
    return ChannelPreviewPlayer()