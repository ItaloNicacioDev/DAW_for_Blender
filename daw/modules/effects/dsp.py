# modules/effects/dsp.py
"""
DSP offline dos efeitos internos da DAW — numpy puro (sem bpy, sem scipy).

Por que numpy puro: o Python do Blender vem com numpy, mas NÃO com scipy.
Os efeitos aqui são processados de forma offline ("bounce"): pega o áudio
inteiro de uma strip, passa pela cadeia de inserts e gera um novo áudio.
Por isso podemos usar FFT sobre o sinal inteiro e algoritmos em blocos,
que são rápidos em numpy, em vez de laços amostra a amostra em Python.

Efeitos: EQ, COMPRESSOR, LIMITER, REVERB, DELAY, CHORUS, FLANGER, PHASER,
DISTORTION.  Ponto de entrada: `process_effect()` (um efeito) e
`apply_chain()` (cadeia de inserts, com suporte a "cauda" de delay/reverb).

Formato do áudio: aceita (N,), (N, canais) ou (canais, N) float; devolve no
mesmo formato, float32.

Parâmetros: aceita os nomes do Mixer (`threshold`, `attack` em segundos...)
e os nomes do rack de efeitos (`threshold_db`, `attack_ms`...) — ver
`normalize_params()`.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Mapping, Optional

import numpy as np

EFFECT_TYPES = (
    "EQ", "COMPRESSOR", "LIMITER", "REVERB", "DELAY",
    "CHORUS", "FLANGER", "PHASER", "DISTORTION",
)

_EPS = 1e-12
MAX_TAIL_SECONDS = 8.0


# ═══════════════════════════════════════════════════════════════
#  Utilitários
# ═══════════════════════════════════════════════════════════════

def _to_frames(audio) -> tuple[np.ndarray, str]:
    """Converte para (N, canais) float64 e devolve também o layout original."""
    a = np.asarray(audio, dtype=np.float64)
    if a.ndim == 1:
        return a[:, None], "mono"
    if a.ndim != 2:
        raise ValueError(f"Áudio com formato inesperado: shape={a.shape}")
    if a.shape[0] <= 8 and a.shape[1] > a.shape[0]:
        return a.T, "cn"          # (canais, N)
    return a, "nc"                # (N, canais)


def _from_frames(x: np.ndarray, layout: str) -> np.ndarray:
    y = x.astype(np.float32)
    if layout == "mono":
        return np.ascontiguousarray(y[:, 0])
    if layout == "cn":
        return np.ascontiguousarray(y.T)
    return np.ascontiguousarray(y)


def _clamp(v: float, lo: float, hi: float) -> float:
    return float(min(max(float(v), lo), hi))


def _mix(dry: np.ndarray, wet: np.ndarray, mix: float) -> np.ndarray:
    mix = _clamp(mix, 0.0, 1.0)
    if mix >= 0.9999:
        return wet
    if mix <= 0.0001:
        return dry
    return dry * (1.0 - mix) + wet * mix


def _db_to_lin(db):
    return 10.0 ** (np.asarray(db, dtype=np.float64) / 20.0)


def _next_pow2(n: int) -> int:
    return 1 << max(int(n) - 1, 1).bit_length()


def _fft_apply(x: np.ndarray, sr: int, gain_fn: Callable[[np.ndarray], np.ndarray]) -> np.ndarray:
    """Filtro de fase zero: multiplica o espectro pela resposta `gain_fn(freq_hz)`."""
    n = x.shape[0]
    size = _next_pow2(n + 4096)
    spec = np.fft.rfft(x, n=size, axis=0)
    freqs = np.fft.rfftfreq(size, 1.0 / sr)
    gain = np.asarray(gain_fn(np.maximum(freqs, 1e-3)), dtype=np.float64)
    out = np.fft.irfft(spec * gain[:, None], n=size, axis=0)
    return out[:n]


def _fft_convolve(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """Convolução (N, ch) * (M, ch) via FFT; devolve N amostras (cauda cortada)."""
    n, m = x.shape[0], ir.shape[0]
    size = _next_pow2(n + m - 1)
    spec = np.fft.rfft(x, n=size, axis=0) * np.fft.rfft(ir, n=size, axis=0)
    return np.fft.irfft(spec, n=size, axis=0)[:n]


def _frac_delay(x: np.ndarray, delay_samples: np.ndarray) -> np.ndarray:
    """Atraso fracionário variável no tempo (interpolação linear)."""
    n = x.shape[0]
    pos = np.arange(n, dtype=np.float64) - delay_samples
    valid = (pos >= 0.0)[:, None]
    pos = np.clip(pos, 0.0, n - 1.0)
    i0 = np.floor(pos).astype(np.int64)
    frac = (pos - i0)[:, None]
    i1 = np.minimum(i0 + 1, n - 1)
    return (x[i0] * (1.0 - frac) + x[i1] * frac) * valid


def _mod_delay(x, sr, base_s, depth_s, rate, phase, feedback, iters) -> np.ndarray:
    """Linha de atraso modulada por LFO senoidal, com feedback aproximado por iteração."""
    n = x.shape[0]
    t = np.arange(n, dtype=np.float64) / sr
    lfo = 0.5 * (1.0 + np.sin(2.0 * np.pi * rate * t + phase))
    d = (base_s + depth_s * lfo) * sr
    wet = _frac_delay(x, d)
    if abs(feedback) > 0.01:
        for _ in range(iters):
            wet = _frac_delay(x + feedback * wet, d)
    return wet


# ═══════════════════════════════════════════════════════════════
#  Normalização de parâmetros (Mixer x rack de efeitos)
# ═══════════════════════════════════════════════════════════════

def _pick(params: Mapping[str, Any], names: Iterable[str], default: float) -> float:
    for name in names:
        if name in params and params[name] is not None:
            try:
                return float(params[name])
            except (TypeError, ValueError):
                continue
    return float(default)


def _seconds(params: Mapping[str, Any], sec_names: Iterable[str], ms_names: Iterable[str], default_s: float) -> float:
    for name in sec_names:
        if name in params and params[name] is not None:
            return float(params[name])
    for name in ms_names:
        if name in params and params[name] is not None:
            return float(params[name]) / 1000.0
    return float(default_s)


def normalize_params(effect_type: str, params: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Devolve os parâmetros num vocabulário único, com valores padrão."""
    p: Mapping[str, Any] = params or {}
    t = (effect_type or "").upper()

    if t == "EQ":
        if "bands" in p and p["bands"]:
            bands = [dict(b) for b in p["bands"]]
        else:
            bands = [
                {"band_type": "LOWSHELF", "freq": 200.0, "gain_db": _pick(p, ["low_gain"], 0.0), "q": 0.71},
                {"band_type": "PEAK", "freq": _pick(p, ["mid_freq"], 1000.0),
                 "gain_db": _pick(p, ["mid_gain"], 0.0), "q": _pick(p, ["mid_q"], 1.0)},
                {"band_type": "HIGHSHELF", "freq": 4000.0, "gain_db": _pick(p, ["high_gain"], 0.0), "q": 0.71},
            ]
        return {"bands": bands}

    if t == "COMPRESSOR":
        return {
            "threshold_db": _pick(p, ["threshold_db", "threshold"], -18.0),
            "ratio": _pick(p, ["ratio"], 4.0),
            "attack_s": _seconds(p, ["attack_s", "attack"], ["attack_ms"], 0.01),
            "release_s": _seconds(p, ["release_s", "release"], ["release_ms"], 0.15),
            "knee_db": _pick(p, ["knee_db", "knee"], 0.0),
            "makeup_db": _pick(p, ["makeup_gain_db", "makeup_db", "makeup"], 0.0),
            "mix": _pick(p, ["mix"], 1.0),
        }

    if t == "LIMITER":
        return {
            "ceiling_db": _pick(p, ["ceiling_db", "ceiling"], -0.3),
            "release_s": _seconds(p, ["release_s", "release"], ["release_ms"], 0.05),
            "input_gain_db": _pick(p, ["input_gain_db"], 0.0),
        }

    if t == "REVERB":
        return {
            "size": _pick(p, ["size", "room_size"], 0.5),
            "damping": _pick(p, ["damping"], 0.5),
            "width": _pick(p, ["width"], 1.0),
            "pre_delay_s": _seconds(p, ["pre_delay_s"], ["pre_delay_ms"], 0.0),
            "mix": _pick(p, ["mix"], 0.3),
        }

    if t == "DELAY":
        return {
            "time_s": _seconds(p, ["time_s", "time"], ["time_ms"], 0.25),
            "feedback": _pick(p, ["feedback"], 0.35),
            "mix": _pick(p, ["mix"], 0.3),
        }

    if t == "CHORUS":
        return {
            "rate": _pick(p, ["rate"], 0.8),
            "depth": _pick(p, ["depth"], 0.3),
            "voices": int(_pick(p, ["voices"], 2)),
            "feedback": _pick(p, ["feedback"], 0.0),
            "mix": _pick(p, ["mix"], 0.5),
        }

    if t == "FLANGER":
        return {
            "rate": _pick(p, ["rate"], 0.25),
            "depth": _pick(p, ["depth"], 0.5),
            "feedback": _pick(p, ["feedback"], 0.3),
            "manual_s": _seconds(p, ["manual_s"], ["manual_ms"], 0.001),
            "mix": _pick(p, ["mix"], 0.5),
        }

    if t == "PHASER":
        return {
            "rate": _pick(p, ["rate"], 0.3),
            "depth": _pick(p, ["depth"], 0.6),
            "stages": int(_pick(p, ["stages"], 4)),
            "mix": _pick(p, ["mix"], 0.5),
        }

    if t == "DISTORTION":
        return {
            "drive": _pick(p, ["drive"], 0.3),
            "tone": _pick(p, ["tone"], 0.5),
            "output_gain_db": _pick(p, ["output_gain_db"], 0.0),
            "mix": _pick(p, ["mix"], 1.0),
        }

    raise ValueError(f"Tipo de efeito desconhecido: {effect_type!r}")


# ═══════════════════════════════════════════════════════════════
#  EQ  (bandas somadas em dB, aplicadas por FFT — fase zero)
# ═══════════════════════════════════════════════════════════════

def _band_gain_db(band: Mapping[str, Any], f: np.ndarray) -> np.ndarray:
    kind = str(band.get("band_type", "PEAK")).upper()
    fc = _clamp(band.get("freq", 1000.0), 20.0, 20000.0)
    gain = float(band.get("gain_db", 0.0))
    q = max(float(band.get("q", 1.0)), 0.1)

    if kind == "PEAK":
        sigma_oct = 0.6 / q
        return gain * np.exp(-0.5 * (np.log2(f / fc) / sigma_oct) ** 2)
    if kind == "LOWSHELF":
        return gain / (1.0 + (f / fc) ** 2)
    if kind == "HIGHSHELF":
        return gain / (1.0 + (fc / f) ** 2)
    if kind == "LOWCUT":       # passa-altas, 12 dB/oitava
        return -10.0 * np.log10(1.0 + (fc / f) ** 4)
    if kind == "HIGHCUT":      # passa-baixas, 12 dB/oitava
        return -10.0 * np.log10(1.0 + (f / fc) ** 4)
    return np.zeros_like(f)


def eq(x: np.ndarray, sr: int, bands: list) -> np.ndarray:
    active = [b for b in bands if b.get("enabled", True)]
    useful = [
        b for b in active
        if abs(float(b.get("gain_db", 0.0))) > 1e-3
        or str(b.get("band_type", "")).upper() in ("LOWCUT", "HIGHCUT")
    ]
    if not useful:
        return x

    def response(f):
        total_db = np.zeros_like(f)
        for b in useful:
            total_db = total_db + _band_gain_db(b, f)
        return _db_to_lin(total_db)

    return _fft_apply(x, sr, response)


# ═══════════════════════════════════════════════════════════════
#  Compressor (ganho calculado por blocos, suavizado attack/release)
# ═══════════════════════════════════════════════════════════════

_BLOCK = 64


def _block_peaks(x: np.ndarray, hop: int) -> tuple[np.ndarray, int]:
    n = x.shape[0]
    nb = -(-n // hop)
    peak = np.abs(x).max(axis=1)
    if nb * hop != n:
        peak = np.concatenate([peak, np.zeros(nb * hop - n)])
    return peak.reshape(nb, hop).max(axis=1), nb


def compressor(x, sr, threshold_db=-18.0, ratio=4.0, attack_s=0.01, release_s=0.15,
               knee_db=0.0, makeup_db=0.0, mix=1.0) -> np.ndarray:
    n = x.shape[0]
    if n == 0:
        return x
    hop = _BLOCK
    level, nb = _block_peaks(x, hop)
    level_db = 20.0 * np.log10(np.maximum(level, 1e-9))
    over = level_db - threshold_db
    slope = 1.0 - 1.0 / max(float(ratio), 1.0)

    if knee_db > 0.0:
        half = knee_db / 2.0
        reduction = np.where(
            over <= -half, 0.0,
            np.where(over >= half, over * slope, slope * (over + half) ** 2 / (2.0 * knee_db)),
        )
    else:
        reduction = np.maximum(over, 0.0) * slope

    a_att = float(np.exp(-hop / (sr * max(attack_s, 1e-4))))
    a_rel = float(np.exp(-hop / (sr * max(release_s, 1e-3))))
    smooth = np.empty(nb)
    prev = 0.0
    for i in range(nb):
        r = reduction[i]
        c = a_att if r > prev else a_rel
        prev = c * prev + (1.0 - c) * r
        smooth[i] = prev

    centers = (np.arange(nb) + 0.5) * hop
    gain_db = np.interp(np.arange(n), centers, -smooth) + makeup_db
    wet = x * _db_to_lin(gain_db)[:, None]
    return _mix(x, wet, mix)


# ═══════════════════════════════════════════════════════════════
#  Limiter (lookahead por blocos; garante pico <= teto)
# ═══════════════════════════════════════════════════════════════

def limiter(x, sr, ceiling_db=-0.3, release_s=0.05, input_gain_db=0.0) -> np.ndarray:
    n = x.shape[0]
    if n == 0:
        return x
    ceil = float(_db_to_lin(min(ceiling_db, 0.0)))
    if input_gain_db:
        x = x * float(_db_to_lin(input_gain_db))

    hop = 32
    peak, nb = _block_peaks(x, hop)
    required = np.minimum(1.0, ceil / np.maximum(peak, 1e-9))

    # olha um bloco pra frente e um pra trás: o ganho já começa a descer antes do pico
    m3 = required.copy()
    m3[1:] = np.minimum(m3[1:], required[:-1])
    m3[:-1] = np.minimum(m3[:-1], required[1:])

    rel = float(np.exp(-hop / (sr * max(release_s, 1e-3))))
    gain = np.empty(nb)
    prev = 1.0
    for i in range(nb):
        prev = min(m3[i], 1.0 - (1.0 - prev) * rel)
        gain[i] = prev

    step = np.repeat(gain, hop)
    padded = np.concatenate([np.full(hop // 2, step[0]), step, np.full(hop // 2, step[-1])])
    smooth = np.convolve(padded, np.ones(hop) / hop, mode="valid")[:n]

    y = x * smooth[:, None]
    return np.clip(y, -ceil, ceil)      # rede de segurança final


# ═══════════════════════════════════════════════════════════════
#  Delay
# ═══════════════════════════════════════════════════════════════

def _delay_taps(time_s: float, feedback: float) -> int:
    fb = _clamp(feedback, 0.0, 0.95)
    if fb < 0.01:
        return 1
    taps = int(np.ceil(np.log(1e-3) / np.log(fb))) + 1
    max_by_tail = int(MAX_TAIL_SECONDS / max(time_s, 0.01))
    return max(1, min(taps, 80, max_by_tail))


def delay(x, sr, time_s=0.25, feedback=0.35, mix=0.3) -> np.ndarray:
    """Eco com feedback. O som seco é mantido; `mix` controla o volume das repetições."""
    n = x.shape[0]
    mix = _clamp(mix, 0.0, 1.0)
    if mix <= 0.0001:
        return x
    d = int(round(_clamp(time_s, 0.001, 4.0) * sr))
    fb = _clamp(feedback, 0.0, 0.95)
    echoes = np.zeros_like(x)
    for k in range(1, _delay_taps(time_s, fb) + 1):
        shift = k * d
        if shift >= n:
            break
        echoes[shift:] += (fb ** (k - 1)) * x[: n - shift]
    return x + mix * echoes


# ═══════════════════════════════════════════════════════════════
#  Reverb (convolução com resposta ao impulso sintética)
# ═══════════════════════════════════════════════════════════════

def _reverb_ir(sr: int, channels: int, size: float, damping: float, width: float, pre_delay_s: float) -> np.ndarray:
    size = _clamp(size, 0.0, 1.0)
    damping = _clamp(damping, 0.0, 1.0)
    width = _clamp(width, 0.0, 1.0)
    rt60 = 0.3 + 3.2 * size
    length = int(sr * rt60)
    t = np.arange(length) / sr
    env = 10.0 ** (-3.0 * t / rt60)               # -60 dB em rt60 segundos

    rng = np.random.default_rng(20260921)          # determinístico: mesmo resultado a cada render
    noise = rng.standard_normal((length, channels))
    if channels == 2:
        common = rng.standard_normal(length)
        noise = width * noise + (1.0 - width) * common[:, None]
    ir = noise * env[:, None]

    # damping: com o tempo, as altas frequências somem primeiro
    if damping > 0.0:
        cutoff = 800.0 + 11000.0 * (1.0 - damping)
        dark = _fft_apply(ir, sr, lambda f: 1.0 / np.sqrt(1.0 + (f / cutoff) ** 4))
        blend = np.clip(t / (0.35 * rt60), 0.0, 1.0) * damping
        ir = ir * (1.0 - blend)[:, None] + dark * blend[:, None]

    attack = max(int(0.004 * sr), 1)
    ir[:attack] *= np.linspace(0.0, 1.0, attack)[:, None]

    pre = int(_clamp(pre_delay_s, 0.0, 0.5) * sr)
    if pre:
        ir = np.concatenate([np.zeros((pre, channels)), ir], axis=0)

    energy = np.sqrt(np.sum(ir ** 2, axis=0, keepdims=True)) + _EPS
    return ir / energy


def reverb(x, sr, size=0.5, damping=0.5, width=1.0, pre_delay_s=0.0, mix=0.3) -> np.ndarray:
    if mix <= 0.0001:
        return x
    ir = _reverb_ir(sr, x.shape[1], size, damping, width, pre_delay_s)
    wet = _fft_convolve(x, ir)
    return _mix(x, wet, mix)


# ═══════════════════════════════════════════════════════════════
#  Chorus / Flanger
# ═══════════════════════════════════════════════════════════════

def chorus(x, sr, rate=0.8, depth=0.3, voices=2, feedback=0.0, mix=0.5) -> np.ndarray:
    voices = int(_clamp(voices, 1, 4))
    depth = _clamp(depth, 0.0, 1.0)
    feedback = _clamp(feedback, 0.0, 0.7)
    wet = np.zeros_like(x)
    for k in range(voices):
        wet += _mod_delay(
            x, sr,
            base_s=0.014 + 0.004 * k,
            depth_s=0.008 * depth,
            rate=_clamp(rate, 0.01, 20.0) * (1.0 + 0.07 * k),
            phase=2.0 * np.pi * k / voices,
            feedback=feedback, iters=3,
        )
    return _mix(x, wet / voices, mix)


def flanger(x, sr, rate=0.25, depth=0.5, feedback=0.3, manual_s=0.001, mix=0.5) -> np.ndarray:
    depth = _clamp(depth, 0.0, 1.0)
    feedback = _clamp(feedback, -0.95, 0.95)
    wet = _mod_delay(
        x, sr,
        base_s=_clamp(manual_s, 0.0002, 0.01),
        depth_s=0.003 * depth,
        rate=_clamp(rate, 0.01, 20.0),
        phase=0.0, feedback=feedback, iters=8,
    )
    wet = wet * (1.0 - 0.5 * abs(feedback))         # compensa o ganho da ressonância
    return _mix(x, wet, mix)


# ═══════════════════════════════════════════════════════════════
#  Phaser (all-pass em cascata, modulado — via STFT, sem laço por amostra)
# ═══════════════════════════════════════════════════════════════

def phaser(x, sr, rate=0.3, depth=0.6, stages=4, mix=0.5) -> np.ndarray:
    n, ch = x.shape
    if n == 0 or mix <= 0.0001:
        return x
    stages = int(_clamp(stages, 2, 12))
    depth = _clamp(depth, 0.0, 1.0)
    rate = _clamp(rate, 0.01, 20.0)

    size, hop = 1024, 256                             # 75% de sobreposição
    window = np.hanning(size + 1)[:-1]
    frames_total = -(-(n + size) // hop) + 1
    length = (frames_total - 1) * hop + size
    padded = np.zeros((length + size, ch))
    padded[size:size + n] = x
    windows = np.lib.stride_tricks.sliding_window_view(padded, size, axis=0)   # (L-size+1, ch, size)

    omega = 2.0 * np.pi * np.arange(size // 2 + 1) / size
    z = np.exp(-1j * omega)
    out = np.zeros((length + size, ch))

    chunk = 512
    for k0 in range(0, frames_total, chunk):
        k1 = min(k0 + chunk, frames_total)
        starts = np.arange(k0, k1) * hop
        frames = windows[starts] * window                    # (m, ch, size)
        spec = np.fft.rfft(frames, axis=-1)

        centers_t = (starts + size / 2.0 - size) / sr
        fc = 950.0 * 2.0 ** (depth * 1.66 * np.sin(2.0 * np.pi * rate * centers_t))
        fc = np.clip(fc, 60.0, 0.45 * sr)
        tan_w = np.tan(np.pi * fc / sr)
        a = (tan_w - 1.0) / (tan_w + 1.0)
        h_stage = (a[:, None] + z[None, :]) / (1.0 + a[:, None] * z[None, :])
        h_total = h_stage ** stages

        frames_out = np.fft.irfft(spec * h_total[:, None, :], n=size, axis=-1)   # (m, ch, size)
        for j in range(size // hop):
            seg = frames_out[:, :, j * hop:(j + 1) * hop].transpose(0, 2, 1).reshape(-1, ch)
            begin = k0 * hop + j * hop
            out[begin:begin + seg.shape[0]] += seg

    wet = out[size:size + n] / 2.0                          # Hann com hop N/4 soma 2
    return _mix(x, wet, mix)


# ═══════════════════════════════════════════════════════════════
#  Distorção
# ═══════════════════════════════════════════════════════════════

def distortion(x, sr, drive=0.3, tone=0.5, output_gain_db=0.0, mix=1.0) -> np.ndarray:
    drive = _clamp(drive, 0.0, 1.0)
    tone = _clamp(tone, 0.0, 1.0)
    gain = 1.0 + 39.0 * drive
    wet = np.tanh(x * gain) / np.tanh(gain)
    cutoff = 800.0 * (15.0 ** tone)                         # 800 Hz .. 12 kHz
    wet = _fft_apply(wet, sr, lambda f: 1.0 / np.sqrt(1.0 + (f / cutoff) ** 4))
    wet = wet * float(_db_to_lin(output_gain_db))
    return _mix(x, wet, mix)


# ═══════════════════════════════════════════════════════════════
#  API pública
# ═══════════════════════════════════════════════════════════════

def tail_seconds(effect_type: str, params: Optional[Mapping[str, Any]] = None) -> float:
    """Quanto tempo de 'cauda' o efeito gera depois do fim do áudio de entrada."""
    t = (effect_type or "").upper()
    try:
        p = normalize_params(t, params)
    except ValueError:
        return 0.0
    if t == "DELAY" and p["mix"] > 0.0001:
        return min(MAX_TAIL_SECONDS, _delay_taps(p["time_s"], p["feedback"]) * p["time_s"])
    if t == "REVERB" and p["mix"] > 0.0001:
        return min(MAX_TAIL_SECONDS, 0.3 + 3.2 * _clamp(p["size"], 0, 1) + p["pre_delay_s"])
    return 0.0


def _process_frames(effect_type: str, x: np.ndarray, sr: int, params: Optional[Mapping[str, Any]]) -> np.ndarray:
    t = effect_type.upper()
    p = normalize_params(t, params)
    if t == "EQ":
        return eq(x, sr, p["bands"])
    if t == "COMPRESSOR":
        return compressor(x, sr, **p)
    if t == "LIMITER":
        return limiter(x, sr, **p)
    if t == "REVERB":
        return reverb(x, sr, **p)
    if t == "DELAY":
        return delay(x, sr, **p)
    if t == "CHORUS":
        return chorus(x, sr, **p)
    if t == "FLANGER":
        return flanger(x, sr, **p)
    if t == "PHASER":
        return phaser(x, sr, **p)
    if t == "DISTORTION":
        return distortion(x, sr, **p)
    raise ValueError(f"Tipo de efeito desconhecido: {effect_type!r}")


def process_effect(effect_type: str, audio, sample_rate: int = 44100,
                   params: Optional[Mapping[str, Any]] = None) -> np.ndarray:
    """Aplica UM efeito. Mantém o formato e o tamanho do áudio de entrada."""
    x, layout = _to_frames(audio)
    y = _process_frames(effect_type, x, int(sample_rate), params)
    return _from_frames(y, layout)


def _slot_get(slot: Any, name: str, default: Any = None) -> Any:
    if isinstance(slot, Mapping):
        return slot.get(name, default)
    return getattr(slot, name, default)


def apply_chain(slots: Iterable[Any], audio, sample_rate: int = 44100,
                external: Optional[Dict[str, Callable[[Any, np.ndarray, int], np.ndarray]]] = None,
                with_tail: bool = True) -> np.ndarray:
    """
    Aplica uma cadeia de inserts, na ordem. Cada slot tem `effect_type`,
    `enabled`, `bypass` e `params` (dict). Slots inativos são ignorados.

    `external`: {"VST": fn(slot, x_nc, sr) -> x_nc} para tipos processados por
    outro motor (o host VST). `x_nc` tem shape (N, canais).

    Com `with_tail=True`, o áudio ganha silêncio no fim (até MAX_TAIL_SECONDS)
    para o delay/reverb terminarem de soar.
    """
    external = external or {}
    active = [
        s for s in slots
        if _slot_get(s, "enabled", True) and not _slot_get(s, "bypass", False)
    ]
    x, layout = _to_frames(audio)
    if not active:
        return _from_frames(x, layout)

    sr = int(sample_rate)
    if with_tail:
        tail = max(
            (tail_seconds(str(_slot_get(s, "effect_type", "")), _slot_get(s, "params", {})) for s in active),
            default=0.0,
        )
        if tail > 0.0:
            x = np.concatenate([x, np.zeros((int(tail * sr), x.shape[1]))], axis=0)

    for slot in active:
        etype = str(_slot_get(slot, "effect_type", "")).upper()
        if etype in external:
            x = np.asarray(external[etype](slot, x, sr), dtype=np.float64)
        elif etype in EFFECT_TYPES:
            x = _process_frames(etype, x, sr, _slot_get(slot, "params", {}))
        # tipos desconhecidos: passthrough

    return _from_frames(x, layout)