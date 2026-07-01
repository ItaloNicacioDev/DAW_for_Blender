# modules/browser/thumbnails.py
"""
Cache de thumbnails/waveforms para o browser.

Gera e armazena em disco uma imagem de waveform para cada arquivo de áudio,
identificada por hash do arquivo. A geração ocorre em thread background
para não travar a UI do Blender.
Sem bpy.
"""
from __future__ import annotations

import os
import threading
from typing import Callable, Dict, Optional

from .utils import file_hash, normalize_path


def _cache_dir() -> str:
    base = os.path.join(os.path.expanduser("~"), ".config", "blender_daw", "thumbs")
    os.makedirs(base, exist_ok=True)
    return base


class WaveformCache:
    """
    Cache de waveforms PNG geradas a partir de arquivos de áudio.

    Fluxo:
        1. UI pede get_or_generate(path, callback)
        2. Se já existir em cache, callback é chamado imediatamente
        3. Se não existir, gera em thread daemon e chama callback ao terminar
    """

    def __init__(self) -> None:
        # hash → caminho do PNG gerado
        self._cache:   Dict[str, str]     = {}
        self._pending: Dict[str, bool]    = {}   # hashes em geração
        self._lock:    threading.Lock     = threading.Lock()

    def get_or_generate(
        self,
        audio_path: str,
        callback:   Optional[Callable[[str], None]] = None,
        width:  int = 200,
        height: int = 40,
    ) -> Optional[str]:
        """
        Retorna o path do PNG de waveform se já estiver em cache,
        ou dispara a geração em background e retorna None enquanto gera.

        O callback(png_path) é chamado quando a geração terminar.
        """
        audio_path = normalize_path(audio_path)
        key = file_hash(audio_path)

        with self._lock:
            if key in self._cache:
                return self._cache[key]
            if key in self._pending:
                return None
            self._pending[key] = True

        thread = threading.Thread(
            target=self._generate,
            args=(audio_path, key, width, height, callback),
            daemon=True,
            name=f"daw-thumb-{key[:8]}",
        )
        thread.start()
        return None

    def has(self, audio_path: str) -> bool:
        key = file_hash(normalize_path(audio_path))
        with self._lock:
            return key in self._cache

    def get(self, audio_path: str) -> Optional[str]:
        key = file_hash(normalize_path(audio_path))
        with self._lock:
            return self._cache.get(key)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    # ------------------------------------------------------------------
    # Geração em background
    # ------------------------------------------------------------------

    def _generate(
        self,
        audio_path: str,
        key:        str,
        width:      int,
        height:     int,
        callback:   Optional[Callable[[str], None]],
    ) -> None:
        png_path = os.path.join(_cache_dir(), f"{key}_{width}x{height}.png")

        try:
            if not os.path.isfile(png_path):
                self._render_waveform(audio_path, png_path, width, height)

            with self._lock:
                self._cache[key] = png_path
                self._pending.pop(key, None)

            if callback and os.path.isfile(png_path):
                callback(png_path)

        except Exception:
            with self._lock:
                self._pending.pop(key, None)

    def _render_waveform(
        self,
        audio_path: str,
        out_png:    str,
        width:      int,
        height:     int,
    ) -> None:
        """
        Gera um PNG de waveform usando numpy + soundfile.
        Requer: pip install soundfile numpy pillow --break-system-packages
        """
        import soundfile as sf
        import numpy as np

        data, sr = sf.read(audio_path, dtype="float32", always_2d=True)
        mono = data.mean(axis=1)

        # Downsample para width pontos
        samples_per_pixel = max(1, len(mono) // width)
        pixels = []
        for i in range(width):
            chunk = mono[i * samples_per_pixel: (i + 1) * samples_per_pixel]
            amp = float(np.max(np.abs(chunk))) if len(chunk) > 0 else 0.0
            pixels.append(amp)

        # Normaliza
        max_amp = max(pixels) if pixels else 1.0
        if max_amp > 0:
            pixels = [p / max_amp for p in pixels]

        # Gera imagem usando Pillow se disponível, senão escreve PNG manual simples
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGBA", (width, height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)
            mid = height // 2
            for x, amp in enumerate(pixels):
                h = int(amp * mid)
                draw.line([(x, mid - h), (x, mid + h)], fill=(100, 200, 255, 220))
            img.save(out_png, "PNG")
        except ImportError:
            # Pillow não disponível — escreve arquivo de placeholder
            open(out_png, "wb").close()

    def __repr__(self) -> str:
        return f"WaveformCache(cached={len(self._cache)})"


# Instância global
THUMBS = WaveformCache()