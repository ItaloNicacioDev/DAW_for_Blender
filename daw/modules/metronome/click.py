# modules/metronome/click.py
"""
Síntese dos sons de clique do metrônomo (sem dependência de bpy).

Responsabilidade:
    Gerar, em Python puro (stdlib `math`/`array`/`struct`), o PCM de cada
    som de clique disponível (CLICK, BEEP, WOODBLOCK, COWBELL), com uma
    variante "acentuada" (primeiro beat do compasso) e uma "normal". O
    módulo sounds.py carrega esse PCM em objetos `aud.Sound` e toca.
"""
from __future__ import annotations

import math
import struct

SAMPLE_RATE = 44100

SOUND_STYLES = ("CLICK", "BEEP", "WOODBLOCK", "COWBELL")

# (freq_normal, freq_acentuada, duração_seg, "formato")
_STYLE_PARAMS = {
    "CLICK":     dict(freq=1500.0, accent_freq=2200.0, duration=0.035, shape="NOISE_CLICK"),
    "BEEP":      dict(freq=880.0,  accent_freq=1320.0, duration=0.08,  shape="SINE"),
    "WOODBLOCK": dict(freq=1200.0, accent_freq=1600.0, duration=0.05,  shape="TRIANGLE_DAMPED"),
    "COWBELL":   dict(freq=560.0,  accent_freq=800.0,  duration=0.12,  shape="METALLIC"),
}


def _envelope(i: int, n: int, attack: int) -> float:
    """Envelope percussivo: ataque rápido linear + decaimento exponencial."""
    if i < attack:
        return i / max(attack, 1)
    p = (i - attack) / max(n - attack, 1)
    return math.exp(-6.0 * p)


def _seeded_noise(i: int) -> float:
    """Ruído branco determinístico (sem depender de `random`, para saída reprodutível)."""
    x = math.sin(i * 12.9898) * 43758.5453
    return 2.0 * (x - math.floor(x)) - 1.0


def _oscillator(shape: str, t: float, freq: float, i: int) -> float:
    if shape == "SINE":
        return math.sin(2.0 * math.pi * freq * t)
    if shape == "NOISE_CLICK":
        # Ruído filtrado grosseiramente por uma senoide de alta frequência — soa como "tick"
        return 0.6 * _seeded_noise(i) + 0.4 * math.sin(2.0 * math.pi * freq * t)
    if shape == "TRIANGLE_DAMPED":
        p = (t * freq) % 1.0
        return 4.0 * abs(p - 0.5) - 1.0
    if shape == "METALLIC":
        # Soma de parciais inarmônicas — aproxima um timbre de sino/cowbell
        return (
            0.5 * math.sin(2.0 * math.pi * freq * t)
            + 0.3 * math.sin(2.0 * math.pi * freq * 1.8 * t)
            + 0.2 * math.sin(2.0 * math.pi * freq * 2.6 * t)
        )
    return math.sin(2.0 * math.pi * freq * t)


def generate_click_pcm(style: str = "CLICK", accent: bool = False, sample_rate: int = SAMPLE_RATE) -> bytes:
    """
    Gera um buffer PCM (16-bit mono) para um único clique do metrônomo.
    Retorna bytes prontos para `aud.Sound.buffer` / `wave`.
    """
    params = _STYLE_PARAMS.get(style, _STYLE_PARAMS["CLICK"])
    freq = params["accent_freq"] if accent else params["freq"]
    duration = params["duration"]
    shape = params["shape"]

    n_samples = max(1, int(sample_rate * duration))
    attack = max(1, int(n_samples * 0.05))

    amp = 0.9 if accent else 0.65

    out = []
    for i in range(n_samples):
        t = i / sample_rate
        env = _envelope(i, n_samples, attack)
        s = _oscillator(shape, t, freq, i) * env * amp
        out.append(max(-32767, min(32767, int(s * 32767))))

    return struct.pack(f"<{n_samples}h", *out)


def all_variants_pcm(sample_rate: int = SAMPLE_RATE) -> dict:
    """Pré-gera o PCM de todos os estilos/variantes (acentuado e normal). Usado por sounds.py para cache."""
    result = {}
    for style in SOUND_STYLES:
        result[(style, True)] = generate_click_pcm(style, accent=True, sample_rate=sample_rate)
        result[(style, False)] = generate_click_pcm(style, accent=False, sample_rate=sample_rate)
    return result