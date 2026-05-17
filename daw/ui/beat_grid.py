"""
ui/beat_grid.py — Beat Grid (Step Sequencer)

Inspirado no Beat+Bassline do FL Studio:
- 16 steps por instrumento
- Linhas: Kick, Clap, Hi-Hat, Snare, Open Hat, Ride, Tom, Perc
- Sons gerados por síntese (aud nativo do Blender)
- Playback em loop com BPM sincronizado
- Botões de mute/solo por linha
- Abre como janela flutuante
"""

import bpy
import gpu
import blf
import math
import struct
import time
import threading
import aud
from gpu_extras.batch import batch_for_shader
from bpy.props import (BoolProperty, FloatProperty, IntProperty,
                       StringProperty, CollectionProperty, EnumProperty)

# ═══════════════════════════════════════════════════════════════
#  CONSTANTES DE LAYOUT
# ═══════════════════════════════════════════════════════════════

STEPS       = 16
LABEL_W     = 110
STEP_W      = 38
STEP_H      = 38
ROW_PAD     = 6
TOOLBAR_H   = 38
HEADER_H    = 28
BTN_SIDE    = 26   # mute/solo buttons

# Paleta dark FL Studio
C = {
    'bg':          (0.080, 0.082, 0.110, 1.0),
    'toolbar':     (0.060, 0.062, 0.090, 1.0),
    'header':      (0.055, 0.057, 0.082, 1.0),
    'row_even':    (0.095, 0.098, 0.132, 1.0),
    'row_odd':     (0.085, 0.088, 0.118, 1.0),
    'label_bg':    (0.070, 0.072, 0.100, 1.0),
    'label_txt':   (0.780, 0.790, 0.860, 1.0),
    'label_muted': (0.400, 0.405, 0.450, 1.0),
    'step_off':    (0.130, 0.132, 0.175, 1.0),
    'step_off2':   (0.115, 0.117, 0.158, 1.0),  # grupo alternado
    'step_on':     (0.820, 0.380, 0.120, 1.0),  # laranja FL
    'step_on2':    (0.900, 0.460, 0.160, 1.0),  # laranja claro (beat atual)
    'step_cur':    (1.000, 0.820, 0.200, 1.0),  # amarelo — step ativo
    'step_border': (0.050, 0.052, 0.075, 1.0),
    'mute_on':     (0.280, 0.580, 0.920, 1.0),
    'mute_off':    (0.120, 0.123, 0.165, 1.0),
    'solo_on':     (0.920, 0.780, 0.120, 1.0),
    'solo_off':    (0.120, 0.123, 0.165, 1.0),
    'play_on':     (0.200, 0.780, 0.380, 1.0),
    'btn':         (0.140, 0.143, 0.192, 1.0),
    'btn_active':  (0.200, 0.680, 0.380, 1.0),
    'separator':   (0.180, 0.183, 0.240, 1.0),
    'text':        (0.720, 0.730, 0.800, 1.0),
    'text_dim':    (0.380, 0.385, 0.430, 1.0),
    'beat_line':   (0.350, 0.360, 0.460, 0.6),
    'group_line':  (0.220, 0.224, 0.295, 0.8),
}

# ─── Instrumentos padrão ────────────────────────────────────────
DEFAULT_INSTRUMENTS = [
    {"name": "HIP_Kick",   "color": (0.90, 0.35, 0.10), "type": "kick"},
    {"name": "Clap",       "color": (0.85, 0.75, 0.20), "type": "clap"},
    {"name": "HIP_Hat",    "color": (0.20, 0.75, 0.90), "type": "hihat"},
    {"name": "HIP_Snare",  "color": (0.85, 0.25, 0.55), "type": "snare"},
    {"name": "Open Hat",   "color": (0.20, 0.85, 0.75), "type": "openhat"},
    {"name": "Ride",       "color": (0.55, 0.85, 0.20), "type": "ride"},
    {"name": "Tom",        "color": (0.70, 0.30, 0.90), "type": "tom"},
    {"name": "Perc",       "color": (0.90, 0.55, 0.10), "type": "perc"},
]

# ═══════════════════════════════════════════════════════════════
#  SÍNTESE DE SONS DE BATERIA
# ═══════════════════════════════════════════════════════════════

SAMPLE_RATE = 44100

def _pack(samples):
    clamped = [max(-32767, min(32767, int(s * 32767))) for s in samples]
    return struct.pack(f"<{len(clamped)}h", *clamped)

def _env(i, total, attack, decay, sustain, release):
    a = int(attack * total); d = int(decay * total)
    r = int(release * total); s = total - a - d - r
    if i < a:     return i / max(a, 1)
    if i < a+d:   return 1.0 - (i-a)/max(d,1)*(1-sustain)
    if i < a+d+s: return sustain
    return sustain * (1 - (i-a-d-s)/max(r,1))

def _make_kick(dur=0.45, vel=1.0):
    n = int(SAMPLE_RATE * dur)
    out = []
    for i in range(n):
        t   = i / SAMPLE_RATE
        env = _env(i, n, 0.001, 0.05, 0.0, 0.95)
        # Freq cai de 180 → 40Hz
        freq = 180 * math.exp(-t * 18) + 40
        s    = math.sin(2 * math.pi * freq * t)
        # Clique transiente
        click = math.exp(-t * 300) * 0.6
        out.append((s * 0.85 + click * 0.15) * env * vel)
    return _pack(out)

def _make_snare(dur=0.20, vel=1.0):
    n = int(SAMPLE_RATE * dur)
    import random; rng = random.Random(42)
    out = []
    for i in range(n):
        t   = i / SAMPLE_RATE
        env = _env(i, n, 0.001, 0.02, 0.3, 0.7)
        # Tom + noise
        tone  = math.sin(2 * math.pi * 200 * t) * 0.4
        noise = (rng.random() * 2 - 1) * 0.6
        out.append((tone + noise) * env * vel)
    return _pack(out)

def _make_hihat(dur=0.08, vel=1.0):
    n = int(SAMPLE_RATE * dur)
    import random; rng = random.Random(7)
    out = []
    for i in range(n):
        env = _env(i, n, 0.001, 0.01, 0.0, 0.99)
        noise = (rng.random() * 2 - 1)
        # Passa-alta simulado: subtrai versão suavizada
        out.append(noise * env * 0.65 * vel)
    return _pack(out)

def _make_clap(dur=0.15, vel=1.0):
    n = int(SAMPLE_RATE * dur)
    import random; rng = random.Random(13)
    out = []
    for i in range(n):
        t   = i / SAMPLE_RATE
        # Três bursts rápidos
        b1  = math.exp(-t * 120) * (rng.random() * 2 - 1)
        b2  = math.exp(-(t - 0.012) * 100) * (rng.random() * 2 - 1) if t > 0.012 else 0
        b3  = math.exp(-(t - 0.024) * 80)  * (rng.random() * 2 - 1) if t > 0.024 else 0
        env = _env(i, n, 0.001, 0.03, 0.1, 0.8)
        out.append((b1 + b2 * 0.8 + b3 * 0.6) * env * 0.7 * vel)
    return _pack(out)

def _make_openhat(dur=0.35, vel=1.0):
    return _make_hihat(dur, vel * 0.85)

def _make_ride(dur=0.40, vel=1.0):
    n = int(SAMPLE_RATE * dur)
    import random; rng = random.Random(99)
    out = []
    for i in range(n):
        t   = i / SAMPLE_RATE
        env = _env(i, n, 0.001, 0.1, 0.2, 0.7)
        tone = (math.sin(2*math.pi*1200*t) * 0.5 +
                math.sin(2*math.pi*1800*t) * 0.3 +
                (rng.random()*2-1) * 0.2)
        out.append(tone * env * 0.6 * vel)
    return _pack(out)

def _make_tom(dur=0.30, vel=1.0):
    n = int(SAMPLE_RATE * dur)
    out = []
    for i in range(n):
        t   = i / SAMPLE_RATE
        env = _env(i, n, 0.002, 0.05, 0.2, 0.75)
        freq = 120 * math.exp(-t * 8) + 60
        out.append(math.sin(2*math.pi*freq*t) * env * vel)
    return _pack(out)

def _make_perc(dur=0.12, vel=1.0):
    n = int(SAMPLE_RATE * dur)
    import random; rng = random.Random(55)
    out = []
    for i in range(n):
        t   = i / SAMPLE_RATE
        env = _env(i, n, 0.001, 0.02, 0.1, 0.87)
        s   = (math.sin(2*math.pi*800*t) * 0.6 +
               (rng.random()*2-1) * 0.4)
        out.append(s * env * vel)
    return _pack(out)

_SYNTH_MAP = {
    "kick":    _make_kick,
    "snare":   _make_snare,
    "hihat":   _make_hihat,
    "clap":    _make_clap,
    "openhat": _make_openhat,
    "ride":    _make_ride,
    "tom":     _make_tom,
    "perc":    _make_perc,
}

# Cache de sons compilados
_sound_cache = {}

def _get_sound(stype: str, vel: float = 1.0):
    key = (stype, round(vel, 2))
    if key not in _sound_cache:
        fn  = _SYNTH_MAP.get(stype, _make_perc)
        pcm = fn(vel=vel)
        try:
            snd = aud.Sound.data(pcm, SAMPLE_RATE, 1, aud.FORMAT_S16)
        except AttributeError:
            try:
                snd = aud.Sound.buffer(pcm, SAMPLE_RATE, 1, aud.FORMAT_S16)
            except Exception:
                import tempfile, wave, os
                tmp = tempfile.mktemp(suffix='.wav')
                with wave.open(tmp, 'w') as wf:
                    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(pcm)
                snd = aud.Sound(tmp)
        _sound_cache[key] = snd
    return _sound_cache[key]

_aud_device = None

def _device():
    global _aud_device
    if _aud_device is None:
        try:
            _aud_device = aud.Device()
        except Exception as e:
            print(f"[BeatGrid] aud.Device falhou: {e}")
    return _aud_device

def play_drum(stype: str, vel: float = 1.0):
    try:
        dev = _device()
        if dev:
            snd = _get_sound(stype, vel)
            dev.play(snd)
    except Exception as e:
        print(f"[BeatGrid] play_drum erro: {e}")


# ═══════════════════════════════════════════════════════════════
#  DADOS — PropertyGroups
# ═══════════════════════════════════════════════════════════════

class BeatRow(bpy.types.PropertyGroup):
    name:      StringProperty(default="Inst")
    drum_type: StringProperty(default="kick")
    muted:     BoolProperty(default=False)
    solo:      BoolProperty(default=False)
    volume:    FloatProperty(default=1.0, min=0.0, max=1.0)
    # 16 steps como booleans individuais
    s00: BoolProperty(default=False); s01: BoolProperty(default=False)
    s02: BoolProperty(default=False); s03: BoolProperty(default=False)
    s04: BoolProperty(default=False); s05: BoolProperty(default=False)
    s06: BoolProperty(default=False); s07: BoolProperty(default=False)
    s08: BoolProperty(default=False); s09: BoolProperty(default=False)
    s10: BoolProperty(default=False); s11: BoolProperty(default=False)
    s12: BoolProperty(default=False); s13: BoolProperty(default=False)
    s14: BoolProperty(default=False); s15: BoolProperty(default=False)

    def get_step(self, i: int) -> bool:
        return getattr(self, f"s{i:02d}", False)

    def set_step(self, i: int, val: bool):
        setattr(self, f"s{i:02d}", val)

    def toggle_step(self, i: int):
        self.set_step(i, not self.get_step(i))


class BeatGridState(bpy.types.PropertyGroup):
    rows:        CollectionProperty(type=BeatRow)
    bpm:         FloatProperty(default=120.0, min=40.0, max=300.0, name="BPM")
    current_step: IntProperty(default=-1)
    playing:     BoolProperty(default=False)
    steps:       IntProperty(default=16, min=4, max=32, name="Steps")
    swing:       FloatProperty(default=0.0, min=0.0, max=0.5, name="Swing")


def _init_rows(state):
    """Popula com os instrumentos padrão se ainda estiver vazio."""
    if len(state.rows) > 0:
        return
    for inst in DEFAULT_INSTRUMENTS:
        row           = state.rows.add()
        row.name      = inst["name"]
        row.drum_type = inst["type"]


# ═══════════════════════════════════════════════════════════════
#  SEQUENCER THREAD — playback em tempo real
# ═══════════════════════════════════════════════════════════════

_seq_thread  = None
_seq_running = False


def _seq_loop(state_ref):
    """Thread de sequenciamento — dispara sons nos steps ativos."""
    global _seq_running
    step = 0

    while _seq_running:
        try:
            scene   = bpy.context.scene
            bg      = scene.beat_grid
            bpm     = bg.bpm
            n_steps = bg.steps
            swing   = bg.swing

            # Duração de um step (semínima = 1 beat, step = 1/4 beat)
            step_dur = 60.0 / bpm / 4.0

            # Swing: steps ímpares atrasam ligeiramente
            if step % 2 == 1:
                swing_delay = step_dur * swing
            else:
                swing_delay = 0.0

            # Atualiza step atual para o redraw
            bg.current_step = step % n_steps

            # Verifica se há solo ativo
            has_solo = any(r.solo for r in bg.rows)

            # Dispara sons das linhas ativas neste step
            for row in bg.rows:
                if row.muted:
                    continue
                if has_solo and not row.solo:
                    continue
                if row.get_step(step % n_steps):
                    play_drum(row.drum_type, row.volume)

            # Aguarda duração do step (com swing)
            time.sleep(step_dur + swing_delay)
            step = (step + 1) % n_steps

        except Exception as e:
            print(f"[BeatGrid] Seq error: {e}")
            time.sleep(0.1)

    # Reset ao parar
    try:
        bpy.context.scene.beat_grid.current_step = -1
    except Exception:
        pass


def start_sequencer():
    global _seq_thread, _seq_running
    if _seq_running:
        return
    _seq_running = True
    scene_ref    = None  # acessado via bpy.context na thread
    _seq_thread  = threading.Thread(target=_seq_loop,
                                    args=(scene_ref,), daemon=True)
    _seq_thread.start()
    print("[BeatGrid] Sequenciador iniciado")


def stop_sequencer():
    global _seq_running, _seq_thread
    _seq_running = False
    if _seq_thread:
        _seq_thread.join(timeout=1.0)
        _seq_thread = None
    print("[BeatGrid] Sequenciador parado")


# ═══════════════════════════════════════════════════════════════
#  HELPERS DE DESENHO
# ═══════════════════════════════════════════════════════════════

_shader = None

def _sh():
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader

def _rect(x, y, w, h, col):
    if w <= 0 or h <= 0: return
    s = _sh()
    b = batch_for_shader(s, 'TRIS', {"pos": [
        (x,y),(x+w,y),(x+w,y+h),(x,y),(x+w,y+h),(x,y+h)]})
    s.uniform_float("color", col); b.draw(s)

def _line(x1, y1, x2, y2, col):
    s = _sh()
    b = batch_for_shader(s, 'LINES', {"pos": [(x1,y1),(x2,y2)]})
    s.uniform_float("color", col); b.draw(s)

def _txt(text, x, y, size, col):
    blf.size(0, size); blf.color(0, *col)
    blf.position(0, x, y, 0); blf.draw(0, text)


# ═══════════════════════════════════════════════════════════════
#  DRAW HANDLER — renderiza o Beat Grid
# ═══════════════════════════════════════════════════════════════

def _draw_beat_grid(context):
    bg     = context.scene.beat_grid
    region = context.region
    W, H   = region.width, region.height

    n_rows    = len(bg.rows)
    row_h     = STEP_H + ROW_PAD
    grid_top  = H - TOOLBAR_H - HEADER_H
    grid_bot  = grid_top - n_rows * row_h
    n_steps   = bg.steps
    cur_step  = bg.current_step
    step_w    = (W - LABEL_W - BTN_SIDE * 2 - 8) / n_steps

    gpu.state.blend_set('ALPHA')

    # ── Fundo ────────────────────────────────────────────────
    _rect(0, 0, W, H, C['bg'])

    # ── Toolbar ──────────────────────────────────────────────
    ty = H - TOOLBAR_H
    _rect(0, ty, W, TOOLBAR_H, C['toolbar'])
    _line(0, ty, W, ty, C['separator'])

    # BPM
    _txt(f"BPM: {bg.bpm:.0f}", 10, ty + 12, 13, C['text'])

    # Steps
    _txt(f"Steps: {n_steps}", 120, ty + 12, 12, C['text_dim'])

    # Play/Stop button
    pb_x, pb_y = W // 2 - 30, ty + 6
    pb_col = C['play_on'] if bg.playing else C['btn']
    _rect(pb_x, pb_y, 58, 26, pb_col)
    label = "■ STOP" if bg.playing else "▶ PLAY"
    _txt(label, pb_x + 8, pb_y + 7, 11, C['text'])

    # Swing
    _txt(f"Swing: {bg.swing:.0%}", W - 120, ty + 12, 11, C['text_dim'])

    # ── Header (numeração dos steps) ─────────────────────────
    hy = H - TOOLBAR_H - HEADER_H
    _rect(0, hy, W, HEADER_H, C['header'])
    _line(0, hy, W, hy, C['separator'])

    for i in range(n_steps):
        sx = LABEL_W + BTN_SIDE * 2 + i * step_w + step_w / 2 - 4
        is_beat = (i % 4 == 0)
        col = C['text'] if is_beat else C['text_dim']
        _txt(str(i + 1), sx, hy + 8, 10 if is_beat else 9, col)

    # ── Linhas de instrumento ─────────────────────────────────
    for ri, row in enumerate(bg.rows):
        ry = grid_top - (ri + 1) * row_h + ROW_PAD // 2
        bg_col = C['row_even'] if ri % 2 == 0 else C['row_odd']
        _rect(0, ry, W, STEP_H + 1, bg_col)

        # ── Label ────────────────────────────────────────────
        name_col = C['label_muted'] if row.muted else C['label_txt']
        _rect(0, ry, LABEL_W, STEP_H, C['label_bg'])
        _txt(row.name[:12], 6, ry + 11, 11, name_col)

        # ── Mute button ──────────────────────────────────────
        mx = LABEL_W + 2
        my = ry + (STEP_H - BTN_SIDE) // 2
        _rect(mx, my, BTN_SIDE, BTN_SIDE,
              C['mute_on'] if not row.muted else C['mute_off'])
        _txt("M", mx + 8, my + 6, 9, C['text'])

        # ── Solo button ───────────────────────────────────────
        sx_btn = LABEL_W + BTN_SIDE + 4
        _rect(sx_btn, my, BTN_SIDE, BTN_SIDE,
              C['solo_on'] if row.solo else C['solo_off'])
        _txt("S", sx_btn + 8, my + 6, 9, C['text'])

        # ── Steps ─────────────────────────────────────────────
        for si in range(n_steps):
            sx = LABEL_W + BTN_SIDE * 2 + si * step_w + 2
            sw = step_w - 3

            active   = row.get_step(si)
            is_cur   = (si == cur_step) and bg.playing
            is_beat  = (si % 4 == 0)
            is_group = (si % 2 == 0)

            if is_cur:
                col = C['step_cur']
            elif active:
                col = C['step_on2'] if is_group else C['step_on']
            else:
                col = C['step_off'] if is_group else C['step_off2']

            _rect(sx, ry + 3, sw, STEP_H - 6, col)

            # Borda superior nos ativos
            if active:
                _rect(sx, ry + STEP_H - 7, sw, 3, C['step_on2'])

            # Separador de beat (a cada 4 steps)
            if si % 4 == 0 and si > 0:
                _line(sx - 1, ry, sx - 1, ry + STEP_H, C['beat_line'])
            elif si % 2 == 0 and si > 0:
                _line(sx - 1, ry + 4, sx - 1, ry + STEP_H - 4, C['group_line'])

        # Linha separadora inferior
        _line(0, ry, W, ry, C['separator'])

    gpu.state.blend_set('NONE')


# ═══════════════════════════════════════════════════════════════
#  HIT TESTING
# ═══════════════════════════════════════════════════════════════

def _hit_test(mx, my, region, bg):
    """Retorna (tipo, row_idx, step_idx) do clique."""
    W, H = region.width, region.height
    n_rows   = len(bg.rows)
    n_steps  = bg.steps
    row_h    = STEP_H + ROW_PAD
    grid_top = H - TOOLBAR_H - HEADER_H
    step_w   = (W - LABEL_W - BTN_SIDE * 2 - 8) / n_steps

    # Toolbar
    ty = H - TOOLBAR_H
    if my >= ty:
        # Play/Stop
        pb_x = W // 2 - 30
        if pb_x <= mx <= pb_x + 58 and ty + 6 <= my <= ty + 32:
            return ('PLAYSTOP', -1, -1)
        # BPM scroll será tratado no modal
        if 10 <= mx <= 100 and ty + 6 <= my <= ty + 26:
            return ('BPM', -1, -1)
        return ('TOOLBAR', -1, -1)

    # Linhas
    for ri in range(n_rows):
        ry = grid_top - (ri + 1) * row_h + ROW_PAD // 2
        if not (ry <= my <= ry + STEP_H):
            continue

        btn_y = ry + (STEP_H - BTN_SIDE) // 2
        # Mute
        if LABEL_W + 2 <= mx <= LABEL_W + 2 + BTN_SIDE and btn_y <= my <= btn_y + BTN_SIDE:
            return ('MUTE', ri, -1)
        # Solo
        if LABEL_W + BTN_SIDE + 4 <= mx <= LABEL_W + BTN_SIDE * 2 + 4 and btn_y <= my <= btn_y + BTN_SIDE:
            return ('SOLO', ri, -1)

        # Steps
        step_start = LABEL_W + BTN_SIDE * 2
        if mx >= step_start:
            si = int((mx - step_start) / step_w)
            if 0 <= si < n_steps:
                return ('STEP', ri, si)

    return (None, -1, -1)


# ═══════════════════════════════════════════════════════════════
#  TIMER — redraw a 30fps
# ═══════════════════════════════════════════════════════════════

def _beat_grid_redraw():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass
    return 1 / 30


def _add_beat_strip(context):
    """Cria ou atualiza um strip COLOR no Sequencer representando o padrão de bateria."""
    try:
        scene = context.scene
        seq   = scene.sequence_editor_create()
        bg    = scene.beat_grid
        name  = "BeatGrid"
        fps   = scene.render.fps
        bpm   = bg.bpm
        n_steps = bg.steps
        # Duração total: n_steps * (1 beat / 4) em frames
        beat_frames = int((60.0 / bpm) * fps)
        total_frames = int(beat_frames * n_steps / 4)

        # Remove strip antigo se existir
        try:
            strips = getattr(seq, 'strips', None) or getattr(seq, 'sequences_all', [])
            for s in list(strips):
                if s.name == name:
                    try: seq.strips.remove(s)
                    except: pass
        except Exception:
            pass

        start = scene.frame_current
        # Blender 5.1 API
        try:
            strip = seq.strips.new_effect(
                name=name, type='COLOR', channel=1,
                frame_start=start, length=total_frames)
        except TypeError:
            try:
                strip = seq.strips.new_effect(
                    name=name, type='COLOR', channel=1,
                    frame_start=start, frame_end=start + total_frames)
            except Exception as e:
                print(f"[BeatGrid] Strip: {e}")
                return
        strip.color = (0.82, 0.38, 0.12)
        print(f"[BeatGrid] Strip '{name}' criado ({total_frames} frames)")
    except Exception as e:
        print(f"[BeatGrid] Erro ao criar strip: {e}")


# ═══════════════════════════════════════════════════════════════
#  MODAL OPERATOR
# ═══════════════════════════════════════════════════════════════

class DAW_OT_BeatGridModal(bpy.types.Operator):
    bl_idname  = "daw.beat_grid_modal"
    bl_label   = "Beat Grid"
    bl_options = {'REGISTER'}

    _handle  = None
    _drag    = False
    _drag_val = None   # True/False: valor que estamos pintando

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Precisa de VIEW_3D")
            return {'CANCELLED'}

        bg = context.scene.beat_grid
        _init_rows(bg)

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_beat_grid, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        bg     = context.scene.beat_grid
        region = context.region
        mx, my = event.mouse_region_x, event.mouse_region_y

        # ESC — fecha
        if event.type == 'ESC':
            self._cleanup(context)
            return {'FINISHED'}

        # Scroll BPM com roda do mouse
        if event.type == 'WHEELUPMOUSE':
            bg.bpm = min(300, bg.bpm + 1)
            return {'RUNNING_MODAL'}
        if event.type == 'WHEELDOWNMOUSE':
            bg.bpm = max(40, bg.bpm - 1)
            return {'RUNNING_MODAL'}

        # LMB
        if event.type == 'LEFTMOUSE':
            typ, ri, si = _hit_test(mx, my, region, bg)

            if event.value == 'PRESS':
                if typ == 'PLAYSTOP':
                    if bg.playing:
                        bg.playing = False
                        stop_sequencer()
                    else:
                        bg.playing = True
                        start_sequencer()
                        _add_beat_strip(context)

                elif typ == 'MUTE' and ri >= 0:
                    bg.rows[ri].muted = not bg.rows[ri].muted

                elif typ == 'SOLO' and ri >= 0:
                    bg.rows[ri].solo = not bg.rows[ri].solo

                elif typ == 'STEP' and ri >= 0 and si >= 0:
                    # Define direção do arrasto baseado no estado atual
                    cur = bg.rows[ri].get_step(si)
                    self._drag_val = not cur
                    bg.rows[ri].toggle_step(si)
                    # Preview do som
                    if self._drag_val:
                        play_drum(bg.rows[ri].drum_type, bg.rows[ri].volume)
                    self._drag = True

            elif event.value == 'RELEASE':
                self._drag = False
                self._drag_val = None
            return {'RUNNING_MODAL'}

        # Arrasto — pinta steps
        if event.type == 'MOUSEMOVE' and self._drag and self._drag_val is not None:
            typ, ri, si = _hit_test(mx, my, region, bg)
            if typ == 'STEP' and ri >= 0 and si >= 0:
                if bg.rows[ri].get_step(si) != self._drag_val:
                    bg.rows[ri].set_step(si, self._drag_val)
                    if self._drag_val:
                        play_drum(bg.rows[ri].drum_type, bg.rows[ri].volume)
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}

    def _cleanup(self, context):
        stop_sequencer()
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        context.scene.beat_grid.playing = False
        context.area.tag_redraw()


# ═══════════════════════════════════════════════════════════════
#  OPERADOR — Abre o Beat Grid em janela flutuante
# ═══════════════════════════════════════════════════════════════

class DAW_OT_OpenBeatGrid(bpy.types.Operator):
    bl_idname      = "daw.open_beat_grid"
    bl_label       = "Abrir Beat Grid"
    bl_description = "Abre o Beat Grid (step sequencer) em janela flutuante"

    def execute(self, context):
        _init_rows(context.scene.beat_grid)
        bpy.ops.wm.window_new()

        def _setup():
            try:
                new_win = bpy.context.window_manager.windows[-1]
                for area in new_win.screen.areas:
                    area.type = 'VIEW_3D'
                    for sp in area.spaces:
                        if sp.type == 'VIEW_3D':
                            sp.overlay.show_overlays = False
                            sp.show_gizmo            = False
                            sp.shading.type          = 'SOLID'
                    win_reg = next((r for r in area.regions
                                    if r.type == 'WINDOW'), None)
                    if win_reg:
                        with bpy.context.temp_override(
                                window=new_win, area=area, region=win_reg):
                            bpy.ops.daw.beat_grid_modal('INVOKE_DEFAULT')
                    break
            except Exception as e:
                print(f"[BeatGrid] Erro ao abrir: {e}")
            return None

        bpy.app.timers.register(_setup, first_interval=0.25)
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  PANEL — botão no N-Panel do Sequencer
# ═══════════════════════════════════════════════════════════════

class DAW_PT_BeatGrid(bpy.types.Panel):
    bl_label       = "Beat Grid"
    bl_idname      = "DAW_PT_beat_grid"
    bl_space_type  = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category    = "DAW"
    bl_order       = 2

    def draw(self, context):
        layout = self.layout
        bg     = context.scene.beat_grid

        layout.operator("daw.open_beat_grid", icon='SEQ_CHROMA_SCOPE',
                        text="Abrir Beat Grid ↗")
        layout.separator()

        box = layout.box()
        box.label(text="Configurações", icon='SETTINGS')
        box.prop(bg, "bpm",   text="BPM")
        box.prop(bg, "steps", text="Steps")
        box.prop(bg, "swing", text="Swing", slider=True)

        # Status
        row = layout.row()
        if bg.playing:
            row.label(text=f"● Tocando  Step: {bg.current_step + 1}",
                      icon='PLAY')
        else:
            row.label(text="■ Parado", icon='SNAP_FACE_CENTER')


# ═══════════════════════════════════════════════════════════════
#  REGISTRO
# ═══════════════════════════════════════════════════════════════

classes = [
    BeatRow, BeatGridState,
    DAW_OT_BeatGridModal, DAW_OT_OpenBeatGrid,
    DAW_PT_BeatGrid,
]


def register():
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)
    bpy.types.Scene.beat_grid = bpy.props.PointerProperty(type=BeatGridState)
    if not bpy.app.timers.is_registered(_beat_grid_redraw):
        bpy.app.timers.register(_beat_grid_redraw, persistent=True)


def unregister():
    stop_sequencer()
    if bpy.app.timers.is_registered(_beat_grid_redraw):
        bpy.app.timers.unregister(_beat_grid_redraw)
    try:
        del bpy.types.Scene.beat_grid
    except Exception:
        pass
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)