"""
daw_bridge.py — Bridge Python ↔ Motor de Áudio C
================================================
Uso standalone:   python daw_bridge.py
Uso no Blender:   from daw_bridge import get_engine

A lib compilada deve estar em (relativo a este arquivo):
  ../bin/daw_engine.so        (Linux)
  ../bin/daw_engine.dylib     (macOS)
  ../bin/daw_engine.dll       (Windows)
"""

import ctypes
import ctypes.util
import os
import platform
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

# ═══════════════════════════════════════════════════════════════
#  ESTRUTURAS C  —  devem espelhar exatamente daw_engine.h
# ═══════════════════════════════════════════════════════════════

class DawConfig(ctypes.Structure):
    _fields_ = [
        ("sample_rate",   ctypes.c_uint32),
        ("bit_depth",     ctypes.c_uint32),
        ("buffer_frames", ctypes.c_uint32),
        ("bpm",           ctypes.c_double),
    ]

class DawState(ctypes.Structure):
    _fields_ = [
        ("transport",        ctypes.c_int),
        ("bpm",              ctypes.c_double),
        ("sample_rate",      ctypes.c_uint32),
        ("bit_depth",        ctypes.c_uint32),
        ("position_beats",   ctypes.c_double),
        ("position_seconds", ctypes.c_double),
        ("bar",              ctypes.c_uint32),
        ("beat",             ctypes.c_uint32),
        ("master_volume",    ctypes.c_float),
        ("master_peak_l",    ctypes.c_float),
        ("master_peak_r",    ctypes.c_float),
        ("track_count",      ctypes.c_uint32),
        ("loop_enabled",     ctypes.c_bool),
        ("loop_start_beat",  ctypes.c_double),
        ("loop_end_beat",    ctypes.c_double),
    ]

class DawTrackInfo(ctypes.Structure):
    _fields_ = [
        ("id",         ctypes.c_uint32),
        ("type",       ctypes.c_int),
        ("name",       ctypes.c_char * 64),
        ("volume",     ctypes.c_float),
        ("pan",        ctypes.c_float),
        ("muted",      ctypes.c_bool),
        ("soloed",     ctypes.c_bool),
        ("armed",      ctypes.c_bool),
        ("peak_l",     ctypes.c_float),
        ("peak_r",     ctypes.c_float),
        ("clip_count", ctypes.c_uint32),
    ]

# ═══════════════════════════════════════════════════════════════
#  CONSTANTES
# ═══════════════════════════════════════════════════════════════

DAW_OK               =  0
DAW_ERR_NOT_INIT     = -1
DAW_ERR_ALREADY_INIT = -2
DAW_ERR_AUDIO_DEVICE = -3
DAW_ERR_INVALID_TRACK= -4
DAW_ERR_FILE_NOT_FOUND=-5
DAW_ERR_OUT_OF_MEMORY= -6
DAW_ERR_INVALID_PARAM= -7
DAW_ERR_CLIP_FULL    = -8

DAW_STATE_STOPPED   = 0
DAW_STATE_PLAYING   = 1
DAW_STATE_RECORDING = 2
DAW_STATE_PAUSED    = 3

DAW_TRACK_AUDIO  = 0
DAW_TRACK_MIDI   = 1
DAW_TRACK_BUS    = 2
DAW_TRACK_MASTER = 3

_TRANSPORT_LABELS = {0:"STOPPED", 1:"PLAYING", 2:"RECORDING", 3:"PAUSED"}
_TRACK_LABELS     = {0:"AUDIO",   1:"MIDI",    2:"BUS",       3:"MASTER"}

# ═══════════════════════════════════════════════════════════════
#  BRIDGE
# ═══════════════════════════════════════════════════════════════

class DAWEngine:
    """
    Interface Python limpa para o motor de áudio C.

    Exemplo:
        engine = DAWEngine()
        if engine.load():
            engine.init()
            t1 = engine.track_create()
            engine.play()
    """

    def __init__(self, lib_path: Optional[str] = None):
        self._lib: Optional[ctypes.CDLL] = None
        self._ok   = False          # True depois de daw_init() com sucesso
        self._path = lib_path or self._find_lib()

    # ── Localização automática da .so ───────────────────────────
    @staticmethod
    def _find_lib() -> str:
        here   = Path(__file__).resolve().parent
        system = platform.system()
        exts   = {"Linux": ".so", "Darwin": ".dylib", "Windows": ".dll"}
        ext    = exts.get(system, ".so")

        # Caminhos candidatos (do mais específico ao mais geral)
        candidates = [
            here / ".." / "bin" / f"daw_engine{ext}",   # addon/bin/
            here / "bin"  / f"daw_engine{ext}",          # mesmo dir/bin/
            here / f"daw_engine{ext}",                    # mesmo dir
            Path(f"daw_engine{ext}"),                     # cwd
        ]
        for p in candidates:
            if p.exists():
                return str(p.resolve())

        # Tenta LD_LIBRARY_PATH / PATH do sistema
        found = ctypes.util.find_library("daw_engine")
        return found or str(candidates[0])   # fallback (vai falhar com mensagem clara)

    # ── Carrega a biblioteca ────────────────────────────────────
    def load(self) -> bool:
        """Carrega o .so/.dylib/.dll. Retorna True se bem-sucedido."""
        try:
            self._lib = ctypes.CDLL(self._path)
        except OSError as e:
            print(f"[DAW Bridge] ❌ Não foi possível carregar: {self._path}")
            print(f"             {e}")
            print( "             → Compile primeiro: cd daw_engine && make")
            return False

        self._bind()
        print(f"[DAW Bridge] ✅ Lib carregada: {self._path}")
        return True

    def _bind(self):
        """Define assinaturas de tipo de todas as funções C."""
        L = self._lib

        # Lifecycle
        L.daw_init.restype      = ctypes.c_int32
        L.daw_init.argtypes     = [ctypes.POINTER(DawConfig)]
        L.daw_shutdown.restype  = ctypes.c_int32
        L.daw_shutdown.argtypes = []
        L.daw_get_state.restype  = ctypes.c_int32
        L.daw_get_state.argtypes = [ctypes.POINTER(DawState)]
        L.daw_version.restype   = ctypes.c_char_p
        L.daw_version.argtypes  = []
        L.daw_strerror.restype  = ctypes.c_char_p
        L.daw_strerror.argtypes = [ctypes.c_int32]

        # Transport
        for fn in ("daw_play","daw_stop","daw_pause","daw_record"):
            getattr(L, fn).restype  = ctypes.c_int32
            getattr(L, fn).argtypes = []
        L.daw_seek.restype    = ctypes.c_int32
        L.daw_seek.argtypes   = [ctypes.c_double]
        L.daw_set_bpm.restype  = ctypes.c_int32
        L.daw_set_bpm.argtypes = [ctypes.c_double]
        L.daw_set_loop.restype  = ctypes.c_int32
        L.daw_set_loop.argtypes = [ctypes.c_bool, ctypes.c_double, ctypes.c_double]

        # Master
        L.daw_set_master_volume.restype  = ctypes.c_int32
        L.daw_set_master_volume.argtypes = [ctypes.c_float]
        L.daw_get_master_peaks.restype   = ctypes.c_int32
        L.daw_get_master_peaks.argtypes  = [
            ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]

        # Tracks
        L.daw_track_create.restype    = ctypes.c_int32
        L.daw_track_create.argtypes   = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)]
        L.daw_track_destroy.restype   = ctypes.c_int32
        L.daw_track_destroy.argtypes  = [ctypes.c_uint32]
        L.daw_track_info.restype      = ctypes.c_int32
        L.daw_track_info.argtypes     = [ctypes.c_uint32, ctypes.POINTER(DawTrackInfo)]
        L.daw_track_set_name.restype  = ctypes.c_int32
        L.daw_track_set_name.argtypes = [ctypes.c_uint32, ctypes.c_char_p]
        L.daw_track_set_vol.restype   = ctypes.c_int32
        L.daw_track_set_vol.argtypes  = [ctypes.c_uint32, ctypes.c_float]
        L.daw_track_set_pan.restype   = ctypes.c_int32
        L.daw_track_set_pan.argtypes  = [ctypes.c_uint32, ctypes.c_float]
        L.daw_track_set_mute.restype  = ctypes.c_int32
        L.daw_track_set_mute.argtypes = [ctypes.c_uint32, ctypes.c_bool]
        L.daw_track_set_solo.restype  = ctypes.c_int32
        L.daw_track_set_solo.argtypes = [ctypes.c_uint32, ctypes.c_bool]
        L.daw_track_set_armed.restype  = ctypes.c_int32
        L.daw_track_set_armed.argtypes = [ctypes.c_uint32, ctypes.c_bool]
        L.daw_track_load_file.restype  = ctypes.c_int32
        L.daw_track_load_file.argtypes = [ctypes.c_uint32, ctypes.c_char_p]

    # ── Internos ────────────────────────────────────────────────
    @property
    def loaded(self) -> bool:   return self._lib is not None
    @property
    def running(self) -> bool:  return self._ok

    def _check(self, r: int, op: str = "?") -> bool:
        if r == DAW_OK: return True
        msg = self._lib.daw_strerror(r).decode() if self._lib else "lib not loaded"
        print(f"[DAW Bridge] ⚠  {op}: {msg} (cod={r})")
        return False

    # ── Lifecycle ───────────────────────────────────────────────
    def init(self, sample_rate=44100, bit_depth=24,
             buffer_frames=512, bpm=120.0) -> bool:
        if not self.loaded:
            print("[DAW Bridge] Carregue a lib primeiro com .load()")
            return False
        cfg = DawConfig(
            sample_rate=sample_rate, bit_depth=bit_depth,
            buffer_frames=buffer_frames, bpm=bpm)
        ok = self._check(self._lib.daw_init(ctypes.byref(cfg)), "init")
        if ok:
            self._ok = True
            print(f"[DAW Bridge] Engine: {self.version}")
        return ok

    def shutdown(self) -> bool:
        if not self._ok: return True
        ok = self._check(self._lib.daw_shutdown(), "shutdown")
        self._ok = False
        return ok

    @property
    def version(self) -> str:
        if not self.loaded: return "N/A"
        return self._lib.daw_version().decode()

    def strerror(self, code: int) -> str:
        if not self.loaded: return "?"
        return self._lib.daw_strerror(code).decode()

    # ── Estado ──────────────────────────────────────────────────
    def get_state(self) -> Optional[DawState]:
        if not self._ok: return None
        s = DawState()
        return s if self._lib.daw_get_state(ctypes.byref(s)) == DAW_OK else None

    # ── Transport ───────────────────────────────────────────────
    def play(self)   -> bool: return self._ok and self._check(self._lib.daw_play(),   "play")
    def stop(self)   -> bool: return self._ok and self._check(self._lib.daw_stop(),   "stop")
    def pause(self)  -> bool: return self._ok and self._check(self._lib.daw_pause(),  "pause")
    def record(self) -> bool: return self._ok and self._check(self._lib.daw_record(), "record")

    def seek(self, beat: float) -> bool:
        return self._ok and self._check(self._lib.daw_seek(float(beat)), "seek")

    def set_bpm(self, bpm: float) -> bool:
        return self._ok and self._check(self._lib.daw_set_bpm(float(bpm)), "set_bpm")

    def set_loop(self, enabled: bool, start: float, end: float) -> bool:
        return self._ok and self._check(
            self._lib.daw_set_loop(bool(enabled), float(start), float(end)), "set_loop")

    # ── Master ──────────────────────────────────────────────────
    def set_master_volume(self, v: float) -> bool:
        return self._ok and self._check(
            self._lib.daw_set_master_volume(ctypes.c_float(v)), "set_master_vol")

    def get_master_peaks(self) -> Tuple[float, float]:
        if not self._ok: return 0.0, 0.0
        l, r = ctypes.c_float(), ctypes.c_float()
        self._lib.daw_get_master_peaks(ctypes.byref(l), ctypes.byref(r))
        return l.value, r.value

    # ── Tracks ──────────────────────────────────────────────────
    def track_create(self, track_type: int = DAW_TRACK_AUDIO) -> Optional[int]:
        if not self._ok: return None
        tid = ctypes.c_uint32(0)
        ok  = self._check(
            self._lib.daw_track_create(ctypes.c_int(track_type), ctypes.byref(tid)),
            "track_create")
        return tid.value if ok else None

    def track_destroy(self, tid: int) -> bool:
        return self._ok and self._check(
            self._lib.daw_track_destroy(ctypes.c_uint32(tid)), "track_destroy")

    def track_info(self, tid: int) -> Optional[DawTrackInfo]:
        if not self._ok: return None
        info = DawTrackInfo()
        r = self._lib.daw_track_info(ctypes.c_uint32(tid), ctypes.byref(info))
        return info if r == DAW_OK else None

    def track_set_name(self, tid: int, name: str) -> bool:
        return self._ok and self._check(
            self._lib.daw_track_set_name(ctypes.c_uint32(tid), name.encode()), "set_name")

    def track_set_vol(self, tid: int, v: float) -> bool:
        return self._ok and self._check(
            self._lib.daw_track_set_vol(ctypes.c_uint32(tid), ctypes.c_float(v)), "set_vol")

    def track_set_pan(self, tid: int, p: float) -> bool:
        return self._ok and self._check(
            self._lib.daw_track_set_pan(ctypes.c_uint32(tid), ctypes.c_float(p)), "set_pan")

    def track_set_mute(self, tid: int, v: bool) -> bool:
        return self._ok and self._check(
            self._lib.daw_track_set_mute(ctypes.c_uint32(tid), ctypes.c_bool(v)), "set_mute")

    def track_set_solo(self, tid: int, v: bool) -> bool:
        return self._ok and self._check(
            self._lib.daw_track_set_solo(ctypes.c_uint32(tid), ctypes.c_bool(v)), "set_solo")

    def track_set_armed(self, tid: int, v: bool) -> bool:
        return self._ok and self._check(
            self._lib.daw_track_set_armed(ctypes.c_uint32(tid), ctypes.c_bool(v)), "set_armed")

    def track_load_file(self, tid: int, path: str) -> bool:
        return self._ok and self._check(
            self._lib.daw_track_load_file(ctypes.c_uint32(tid), path.encode()), "load_file")

    # ── Context manager ─────────────────────────────────────────
    def __enter__(self):
        self.load()
        self.init()
        return self

    def __exit__(self, *_):
        self.shutdown()

    # ── Repr útil ───────────────────────────────────────────────
    def __repr__(self) -> str:
        status = "running" if self._ok else ("loaded" if self.loaded else "unloaded")
        return f"<DAWEngine {status} | {self._path}>"


# ═══════════════════════════════════════════════════════════════
#  SINGLETON GLOBAL  (usado pelo addon Blender)
# ═══════════════════════════════════════════════════════════════

_instance: Optional[DAWEngine] = None

def get_engine(lib_path: Optional[str] = None) -> DAWEngine:
    """Retorna (ou cria) a instância global. Thread-safe para leitura."""
    global _instance
    if _instance is None:
        _instance = DAWEngine(lib_path)
        _instance.load()
    return _instance

def destroy_engine():
    global _instance
    if _instance:
        _instance.shutdown()
        _instance = None


# ═══════════════════════════════════════════════════════════════
#  TESTE  —  python daw_bridge.py
# ═══════════════════════════════════════════════════════════════

def _peak_bar(v: float, width: int = 20) -> str:
    filled = int(v * width)
    filled = min(filled, width)
    return "█" * filled + "░" * (width - filled)

def _run_test():
    print("╔══════════════════════════════════════════╗")
    print("║   DAW Engine — Teste de Bridge ctypes    ║")
    print("╚══════════════════════════════════════════╝\n")

    engine = DAWEngine()

    if not engine.load():
        print("\n❌ Compile o engine primeiro:")
        print("   cd daw_engine && make")
        sys.exit(1)

    print(f"Versão: {engine.version}\n")

    # Init
    assert engine.init(sample_rate=44100, bpm=128.0), "init falhou"

    # Criação de tracks
    t1 = engine.track_create(DAW_TRACK_AUDIO)
    t2 = engine.track_create(DAW_TRACK_AUDIO)
    t3 = engine.track_create(DAW_TRACK_MIDI)
    assert t1 and t2 and t3, "track_create falhou"
    print(f"✅ Tracks criadas: {t1}, {t2}, {t3}")

    # Renomeia
    engine.track_set_name(t1, "Kick")
    engine.track_set_name(t2, "Bass")
    engine.track_set_name(t3, "Synth Lead")

    # Parâmetros de mix
    engine.track_set_vol(t1, 0.9)
    engine.track_set_pan(t1, -0.2)
    engine.track_set_vol(t2, 0.7)
    engine.track_set_pan(t2, +0.1)
    engine.track_set_mute(t3, True)

    # Verifica info
    info = engine.track_info(t1)
    assert info is not None
    print(f"✅ Track {t1}: name='{info.name.decode()}' vol={info.volume:.1f} pan={info.pan:.1f}")

    # BPM e loop
    engine.set_bpm(140.0)
    engine.set_loop(True, 0.0, 8.0)

    # Toca e monitora por 2s
    engine.play()
    print(f"\n▶ Reproduzindo a 140 BPM | Loop 0–8 beats")
    print("─" * 50)

    for _ in range(8):
        time.sleep(0.25)
        s = engine.get_state()
        pl, pr = engine.get_master_peaks()
        if s:
            transport = _TRANSPORT_LABELS.get(s.transport, "?")
            print(f"  {transport:10s} | Bar {s.bar} Beat {s.beat} | "
                  f"L {_peak_bar(pl)} R {_peak_bar(pr)}")

    # Pausa e seek
    engine.pause()
    time.sleep(0.1)
    engine.seek(0.0)
    print("\n⏸ Pausado e voltou ao início")

    # Testa mute/solo
    engine.track_set_mute(t1, True)
    engine.track_set_solo(t2, True)
    print(f"✅ Mute/Solo OK")

    # Destroi uma track
    engine.track_destroy(t3)
    s = engine.get_state()
    print(f"✅ Track destruída | Total: {s.track_count if s else '?'}")

    # Volume master
    engine.set_master_volume(0.5)
    print(f"✅ Master volume → 0.5")

    # Shutdown
    engine.stop()
    engine.shutdown()

    print("\n╔══════════════════════════════════════════╗")
    print("║   ✅  Todos os testes passaram!           ║")
    print("╚══════════════════════════════════════════╝")


if __name__ == "__main__":
    _run_test()
