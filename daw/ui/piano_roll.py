"""
ui/piano_roll.py — v7

Piano Roll com som real e integração completa com o Sequencer:

[FIX v7 — dois schedulers independentes]

Problema raiz do v6:
  frame_change_post só dispara quando o Blender muda de frame.
  A 24fps e 120 BPM temos exatamente 1 frame por beat — notas de
  1/8 ou 1/16 que caem entre frames são simplesmente puladas.
  A 60 BPM e 24fps um beat dura 0.5s = 12 frames, então uma nota de
  1/16 dura 0.125s = 3 frames, e o scheduler detecta corretamente.
  Mas a 180 BPM e 24fps um beat dura 0.33s = 8 frames e uma nota de
  1/16 dura 2 frames — ainda ok. Porém qualquer BPM > 24*60/frames_per_beat
  começa a perder notas.

Solução v7:
  Dois schedulers paralelos e complementares:
  1. bpy.app.timers (_pr_note_timer): timer de alta frequência (5ms) que
     roda independente de frames. Usa time.time() para calcular a posição
     exata em beats. Dispara sons com precisão de milissegundos.
  2. bpy.app.handlers.frame_change_post (_piano_roll_frame_handler): mantido
     como backup para redraw do playhead visual, mas NÃO mais responsável
     por disparar sons.

  O timer guarda a posição de início (time.time() quando play começou) e o
  beat de início, e calcula current_beat = start_beat + (now - start_time) * bpm/60.
  Reset automático no rewind/loop.

[FIX v7 — renderização de notas como strip de áudio]
  Operador DAW_OT_RenderNotesToStrip: sintetiza todas as notas do strip
  ativo para um arquivo .wav e insere como SOUND strip no Sequencer.
  Isso faz as notas virarem áudio real, mixável e exportável junto com
  o resto do projeto.
"""

import bpy
import gpu
import blf
import math
import numpy as np
import struct
import tempfile
import time
import wave
import os

from gpu_extras.batch import batch_for_shader
from bpy.props import (FloatProperty, IntProperty, BoolProperty,
                       EnumProperty, CollectionProperty, StringProperty)

# ─── Layout ───────────────────────────────────────────────────
PIANO_W     = 56
TOOLBAR_H   = 34
HEADER_H    = 22
VELOCITY_H  = 72
SCROLLBAR   = 11
NOTE_H_BASE = 14
BEAT_W_BASE = 80
TOTAL_NOTES = 128

C = {
    'toolbar':      (0.085, 0.090, 0.130, 1.0),
    'btn':          (0.160, 0.170, 0.230, 1.0),
    'btn_active':   (0.130, 0.520, 0.330, 1.0),
    'btn_active2':  (0.100, 0.400, 0.250, 1.0),
    'bg':           (0.095, 0.105, 0.145, 1.0),
    'bg_black':     (0.062, 0.068, 0.100, 1.0),
    'bg_c':         (0.115, 0.125, 0.172, 1.0),
    'grid':         (0.125, 0.135, 0.180, 1.0),
    'grid_beat':    (0.180, 0.192, 0.250, 1.0),
    'grid_bar':     (0.280, 0.295, 0.380, 1.0),
    'octave':       (0.220, 0.235, 0.310, 0.5),
    'header':       (0.065, 0.070, 0.105, 1.0),
    'header_txt':   (0.520, 0.540, 0.640, 1.0),
    'header_bar':   (0.720, 0.740, 0.860, 1.0),
    'white_key':    (0.195, 0.205, 0.275, 1.0),
    'black_key':    (0.065, 0.068, 0.098, 1.0),
    'key_c':        (0.240, 0.255, 0.335, 1.0),
    'key_sep':      (0.140, 0.150, 0.200, 1.0),
    'note':         (0.120, 0.700, 0.400, 1.0),
    'note_top':     (0.200, 0.900, 0.540, 1.0),
    'note_dark':    (0.060, 0.340, 0.190, 1.0),
    'note_sel':     (0.380, 0.960, 0.640, 1.0),
    'note_sel_d':   (0.180, 0.580, 0.360, 1.0),
    'note_txt':     (0.020, 0.120, 0.060, 1.0),
    'playhead':     (1.000, 0.800, 0.080, 1.0),
    'playhead_tri': (1.000, 0.870, 0.200, 1.0),
    'vel_bg':       (0.055, 0.060, 0.090, 1.0),
    'vel_bar':      (0.120, 0.580, 0.340, 1.0),
    'vel_sel':      (0.360, 0.920, 0.580, 1.0),
    'vel_line':     (0.200, 0.210, 0.280, 1.0),
    'sb_bg':        (0.090, 0.095, 0.135, 1.0),
    'sb_th':        (0.230, 0.245, 0.320, 1.0),
    'separator':    (0.220, 0.235, 0.310, 1.0),
    'text':         (0.720, 0.740, 0.840, 1.0),
    'text_dim':     (0.400, 0.415, 0.510, 1.0),
    'white':        (1.000, 1.000, 1.000, 1.0),
    'render_btn':   (0.180, 0.380, 0.720, 1.0),
}

BLACK_NOTES = {1, 3, 6, 8, 10}
NOTE_NAMES  = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
TOOLS       = [('DRAW','D','Desenhar'),('SELECT','S','Selecionar'),
               ('ERASE','E','Apagar'),('PAN','P','Pan')]

SAMPLE_RATE = 44100


# ═══════════════════════════════════════════════════════════════
#  DADOS
# ═══════════════════════════════════════════════════════════════

class MidiNote(bpy.types.PropertyGroup):
    pitch:    IntProperty(min=0, max=127)
    start:    FloatProperty()
    length:   FloatProperty()
    velocity: IntProperty(min=1, max=127, default=100)
    selected: BoolProperty(default=False)


class MidiStripData(bpy.types.PropertyGroup):
    strip_name: StringProperty()
    notes:      CollectionProperty(type=MidiNote)


def _instrument_enum_items(self, context):
    """
    Itens do seletor de instrumento do Piano Roll: sintetizadores
    internos (builtin:N) + todos os VST instrumentos já carregados no
    rack (vst:<vst_id>) -- ex.: Vital, BBC Symphony, Serum.

    IMPORTANTE (limite de tempo real): tocar uma nota de um VST exige
    uma chamada IPC pro worker (ver ipc_engine.py), que é bloqueante.
    Isso é seguro para uma audição manual pontual, mas NÃO é seguro
    disparar durante o playback do scheduler de 5ms -- travaria a UI de
    novo (era exatamente o bug corrigido para os sintetizadores
    internos). Por isso o scheduler de playback (`_pr_note_timer`) pula
    silenciosamente notas de instrumentos VST e sugere usar
    "Renderizar Notas → Áudio" para ouvir com o VST de verdade.
    """
    items = [
        ('builtin:0', 'Acoustic Piano', '(interno)'),
        ('builtin:1', 'Electric Piano', '(interno)'),
        ('builtin:2', 'Strings', '(interno)'),
        ('builtin:3', 'Organ', '(interno)'),
        ('builtin:4', 'Bass', '(interno)'),
        ('builtin:5', 'Synth Lead', '(interno)'),
        ('builtin:6', 'Vibraphone', '(interno)'),
        ('builtin:7', 'Choir', '(interno)'),
    ]

    rack = getattr(context.scene, "daw_vst_instruments", None)
    if rack is not None:
        for item in rack.instruments:
            if not item.vst_id:
                continue
            label = item.vst_name or item.vst_id
            status = "" if item.is_loaded else " (não carregado)"
            items.append((f"vst:{item.vst_id}", f"{label}{status}", "Instrumento VST"))

    return items


class PianoRollState(bpy.types.PropertyGroup):
    notes:         CollectionProperty(type=MidiNote)
    zoom_x:        FloatProperty(default=1.0, min=0.1, max=8.0)
    zoom_y:        FloatProperty(default=1.0, min=0.3, max=4.0)
    scroll_x:      FloatProperty(default=0.0, min=0.0)
    scroll_y:      FloatProperty(default=48.0, min=0.0, max=127.0)
    snap_mode:     EnumProperty(
        items=[('1','1/1',''),('0.5','1/2',''),('0.25','1/4',''),
               ('0.125','1/8',''),('0.0625','1/16','')],
        default='0.25', name="Snap")
    active_track:  IntProperty(default=0)
    total_beats:   FloatProperty(default=32.0)
    active_strip:  StringProperty(default="")
    midi_strips:   CollectionProperty(type=MidiStripData)
    tool:          EnumProperty(
        items=[('DRAW','Desenhar',''),('SELECT','Selecionar',''),
               ('ERASE','Apagar',''),('PAN','Pan','')],
        default='DRAW', name="Ferramenta")
    show_velocity: BoolProperty(default=True, name="Velocity")
    instrument:    EnumProperty(
        items=_instrument_enum_items,
        name="Instrumento")
    progression:   StringProperty(default="", name="Progressão")


def _get_active_notes(state):
    if state.active_strip:
        for ms in state.midi_strips:
            if ms.strip_name == state.active_strip:
                return ms.notes
    return state.notes


# ═══════════════════════════════════════════════════════════════
#  SOM — síntese interna
# ═══════════════════════════════════════════════════════════════

_aud_device   = None
_note_cache:    dict = {}
_active_handles: list = []

_INSTRUMENTS = {
    0: {"harmonics":[(1,1.0,0),(2,0.5,0.3),(3,0.25,0),(4,0.12,-0.2),(5,0.06,0.1),(6,0.03,0),(7,0.015,0.2)],
        "attack":0.003,"decay":0.25,"sustain":0.45,"release":0.40},
    1: {"harmonics":[(1,1.0,0),(2,0.3,0.5),(3,0.6,0),(4,0.1,-0.5),(5,0.2,0.3)],
        "attack":0.005,"decay":0.30,"sustain":0.55,"release":0.35},
    2: {"harmonics":[(1,1.0,0),(2,0.6,1.5),(3,0.35,-1.5),(4,0.2,0.8),(5,0.1,-0.8)],
        "attack":0.08,"decay":0.50,"sustain":0.80,"release":0.60},
    3: {"harmonics":[(1,1.0,0),(2,1.0,0),(3,0.8,0),(4,0.7,0),(6,0.5,0),(8,0.3,0)],
        "attack":0.01,"decay":0.01,"sustain":0.95,"release":0.05},
    4: {"harmonics":[(1,1.0,0),(2,0.8,0.2),(3,0.4,0),(4,0.15,-0.2)],
        "attack":0.004,"decay":0.12,"sustain":0.60,"release":0.15},
    5: {"harmonics":[(1,1.0,0),(2,0.7,2.0),(3,0.5,-2.0),(4,0.3,1.0),(5,0.2,-1.0)],
        "attack":0.01,"decay":0.20,"sustain":0.70,"release":0.25},
    6: {"harmonics":[(1,1.0,0),(3,0.3,0)],
        "attack":0.005,"decay":0.80,"sustain":0.20,"release":0.70},
    7: {"harmonics":[(1,1.0,0),(2,0.5,2.0),(3,0.7,0),(4,0.3,-2.0),(5,0.4,1.0)],
        "attack":0.12,"decay":0.40,"sustain":0.75,"release":0.50},
}

_SAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "samples", "instruments",
)
_SAMPLE_FILENAMES = {
    0:"0_acoustic_piano.wav", 1:"1_electric_piano.wav", 2:"2_strings.wav",
    3:"3_organ.wav", 4:"4_bass.wav", 5:"5_synth_lead.wav",
    6:"6_vibraphone.wav", 7:"7_choir.wav",
}
_SAMPLE_ROOT_NOTE = {i: 60 for i in _SAMPLE_FILENAMES}
_sample_cache: dict = {}


def _load_instrument_sample(inst_id: int):
    if inst_id in _sample_cache:
        cached = _sample_cache[inst_id]
        return cached if cached is not False else None
    filename = _SAMPLE_FILENAMES.get(inst_id)
    path = os.path.join(_SAMPLES_DIR, filename) if filename else None
    if not path or not os.path.isfile(path):
        _sample_cache[inst_id] = False
        return None
    try:
        import aud
        snd = aud.Sound(path)
        _sample_cache[inst_id] = snd
        return snd
    except Exception as e:
        print(f"[Piano] Falha sample '{path}': {e}")
        _sample_cache[inst_id] = False
        return None


def _midi_to_freq(n): return 440.0 * (2.0 ** ((n - 69) / 12.0))
def _cents(c): return 2.0 ** (c / 1200.0)


def _parse_instrument_id(raw) -> tuple:
    """
    Interpreta o valor de `state.instrument` (ex.: "builtin:2", "vst:my_synth").

    Retorna ("builtin", int_id) ou ("vst", vst_id_str).
    Aceita também o formato antigo (só um número como string, ex. "0"),
    por compatibilidade com arquivos .blend salvos antes desta mudança.
    """
    raw = str(raw)
    if raw.startswith("vst:"):
        return ("vst", raw[len("vst:"):])
    if raw.startswith("builtin:"):
        try:
            return ("builtin", int(raw[len("builtin:"):]))
        except ValueError:
            return ("builtin", 0)
    try:
        return ("builtin", int(raw))
    except ValueError:
        return ("builtin", 0)


def _synth_note_samples(midi: int, inst_id: int, dur: float, vel: float) -> "np.ndarray":
    """
    Sintetiza nota e retorna array numpy de floats em [-1, 1].

    Vetorizado com numpy (era um loop Python puro amostra-a-amostra com
    math.sin() por harmônico -- ~22 mil iterações Python + várias
    chamadas trigonométricas cada, para uma nota de 0.5s a 44100Hz.
    Isso rodava DENTRO do timer de 5ms na thread principal do Blender
    toda vez que uma nota nova (fora do cache) precisava tocar, travando
    a UI por dezenas/centenas de ms -- essa era a causa real do "trava
    quando toca as notas do piano roll" / "player geral trava".
    A versão vetorizada faz a mesma matemática em arrays numpy inteiros
    de uma vez (sem loop Python por amostra), ordens de magnitude mais
    rápido -- na prática imperceptível mesmo pra notas fora do cache.
    """
    inst = _INSTRUMENTS.get(inst_id, _INSTRUMENTS[0])
    freq = _midi_to_freq(midi)
    n = int(SAMPLE_RATE * dur)
    if n <= 0:
        return np.zeros(0, dtype=np.float64)
    vol = (vel / 127.0) ** 0.8

    a_s = int(inst["attack"] * n)
    d_s = int(inst["decay"] * n)
    r_s = int(inst["release"] * n)
    sus = inst["sustain"]
    s_s = max(0, n - a_s - d_s - r_s)

    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE

    # Envelope ADSR vetorizado (mesmos limiares/fórmulas do original,
    # só calculados em bloco em vez de amostra por amostra).
    idx = np.arange(n)
    env = np.empty(n, dtype=np.float64)

    attack_mask = idx < a_s
    decay_mask = (idx >= a_s) & (idx < a_s + d_s)
    sustain_mask = (idx >= a_s + d_s) & (idx < a_s + d_s + s_s)
    release_mask = idx >= a_s + d_s + s_s

    if a_s > 0:
        env[attack_mask] = idx[attack_mask] / max(a_s, 1)
    if d_s > 0:
        env[decay_mask] = 1.0 - (idx[decay_mask] - a_s) / max(d_s, 1) * (1 - sus)
    env[sustain_mask] = sus
    if r_s > 0:
        env[release_mask] = sus * (1 - (idx[release_mask] - a_s - d_s - s_s) / max(r_s, 1))
    else:
        env[release_mask] = sus

    # Soma dos harmônicos, vetorizada (era um sum() com math.sin() por
    # amostra dentro do loop -- aqui vira soma de arrays numpy).
    out = np.zeros(n, dtype=np.float64)
    for h, amp, det in inst["harmonics"]:
        out += amp * np.sin(2 * np.pi * freq * h * _cents(det) * t)
    out /= len(inst["harmonics"])
    out *= env * vol * 0.7

    return out


def _synth_note_pcm(midi, inst_id, dur, vel):
    floats = _synth_note_samples(midi, inst_id, dur, vel)
    pcm = np.clip(floats * 32767.0, -32767, 32767).astype(np.int16)
    return pcm.tobytes()


def _get_aud_device():
    global _aud_device
    if _aud_device is None:
        try:
            import aud
            _aud_device = aud.Device()
        except Exception as e:
            print(f"[Piano] aud.Device: {e}")
    return _aud_device


_vst_preview_cache: dict = {}  # (vst_id, midi, dur_arredondado, vel) -> audio numpy (channels, samples)


def _play_rendered_audio(audio):
    """
    Toca um buffer já renderizado (numpy, shape (channels, n_samples) ou
    (n_samples,), float32 em [-1,1]) através do `aud` do Blender.
    Usado tanto pra preview de nota via VST quanto, futuramente, por
    qualquer outra fonte de áudio já pronta.
    """
    try:
        import aud
        dev = _get_aud_device()
        if not dev:
            return
        mono = audio[0] if getattr(audio, "ndim", 1) == 2 else audio
        pcm = np.clip(np.asarray(mono, dtype=np.float64) * 32767.0, -32767, 32767).astype(np.int16)
        try:
            snd = aud.Sound.data(pcm.tobytes(), SAMPLE_RATE, 1, aud.FORMAT_S16)
        except AttributeError:
            snd = aud.Sound.buffer(pcm.tobytes(), SAMPLE_RATE, 1, aud.FORMAT_S16)
        handle = dev.play(snd)
        _active_handles.append(handle)
        if len(_active_handles) > 64:
            del _active_handles[:len(_active_handles) - 64]
    except Exception as e:
        print(f"[Piano] _play_rendered_audio: {e}")


def _play_vst_note_preview(vst_id: str, midi: int, dur: float, vel: int):
    """
    Audição pontual de uma nota através de um VST de verdade (via worker
    IPC). BLOQUEANTE -- só deve ser chamada a partir de um clique manual
    do usuário (ver `from_scheduler` em `_play_note_sound`), nunca do
    scheduler de playback de 5ms, senão trava a UI de novo.
    """
    try:
        from ..modules.vst.utils import get_live_vst
    except ImportError:
        return

    vst = get_live_vst(vst_id)
    if vst is None or not vst.loaded:
        print(f"[Piano] VST '{vst_id}' não está carregado -- carregue-o no rack de instrumentos primeiro")
        return

    key = (vst_id, midi, round(dur, 2), vel)
    cached = _vst_preview_cache.get(key)
    if cached is None:
        try:
            cached = vst.render_instrument([(midi, 0.0, dur, vel)], dur + 0.3)
        except Exception as e:
            print(f"[Piano] preview VST '{vst_id}': {e}")
            return
        _vst_preview_cache[key] = cached
        if len(_vst_preview_cache) > 128:
            _vst_preview_cache.pop(next(iter(_vst_preview_cache)))

    _play_rendered_audio(cached)


def _play_note_sound(midi: int, raw_instrument_id, dur: float = 0.6, vel: int = 100, from_scheduler: bool = False):
    """
    Toca uma nota com o instrumento selecionado no Piano Roll -- pode ser
    um sintetizador interno (`builtin:N`) ou um VST carregado (`vst:id`).

    `from_scheduler=True` é usado pelo timer de playback de 5ms
    (`_pr_note_timer`): notas de VST são IGNORADAS nesse caso (silenciosas),
    porque tocar via VST exige uma chamada IPC bloqueante pro worker --
    fazer isso a cada nota durante o playback travaria a UI de novo (era
    exatamente o bug já corrigido pros sintetizadores internos). Pra
    ouvir notas com o VST de verdade durante a reprodução, use
    "Renderizar Notas → Áudio" (bounce offline, depois toca como áudio
    normal do Sequencer). Cliques manuais de audição (não vindos do
    scheduler) continuam tocando o VST normalmente, já que são ações
    pontuais do usuário, não um loop de tempo real.
    """
    kind, inst_ref = _parse_instrument_id(raw_instrument_id)

    if kind == "vst":
        if from_scheduler:
            return
        _play_vst_note_preview(inst_ref, midi, dur, vel)
        return

    inst_id = inst_ref
    try:
        import aud
        dev = _get_aud_device()
        if not dev: return

        sample = _load_instrument_sample(inst_id)
        if sample is not None:
            handle = dev.play(sample)
            root   = _SAMPLE_ROOT_NOTE.get(inst_id, 60)
            handle.pitch  = 2.0 ** ((midi - root) / 12.0)
            handle.volume = max(0.0, min(1.0, vel / 127.0))
            _active_handles.append(handle)
            if len(_active_handles) > 64:
                del _active_handles[:len(_active_handles)-64]
            return

        key = (midi, inst_id, round(dur, 2))
        if key not in _note_cache:
            pcm = _synth_note_pcm(midi, inst_id, dur, vel)
            try:
                snd = aud.Sound.data(pcm, SAMPLE_RATE, 1, aud.FORMAT_S16)
            except AttributeError:
                try:
                    snd = aud.Sound.buffer(pcm, SAMPLE_RATE, 1, aud.FORMAT_S16)
                except Exception:
                    tmp = tempfile.mktemp(suffix='.wav')
                    _write_wav(tmp, [s/32767 for s in struct.unpack(f"<{len(pcm)//2}h", pcm)])
                    snd = aud.Sound(tmp)
            _note_cache[key] = snd
        handle = dev.play(_note_cache[key])
        _active_handles.append(handle)
        if len(_active_handles) > 64:
            del _active_handles[:len(_active_handles)-64]
    except Exception as e:
        print(f"[Piano] _play_note_sound: {e}")


def _write_wav(path, samples):
    pcm  = [max(-32767, min(32767, int(s*32767))) for s in samples]
    data = struct.pack(f"<{len(pcm)}h", *pcm)
    ds   = len(data)
    hdr  = struct.pack('<4sI4s4sIHHIIHH4sI',
                       b'RIFF',36+ds,b'WAVE',b'fmt ',16,
                       1,1,SAMPLE_RATE,SAMPLE_RATE*2,2,16,b'data',ds)
    with open(path,'wb') as f:
        f.write(hdr); f.write(data)


# ═══════════════════════════════════════════════════════════════
#  STRIP NO SEQUENCER
# ═══════════════════════════════════════════════════════════════

def _upsert_midi_strip(context, strip_name: str, n_notes: int):
    scene = context.scene
    seq   = scene.sequence_editor_create()
    try:
        all_strips = getattr(seq,'strips',None) or getattr(seq,'sequences_all',[])
        for s in all_strips:
            if s.name == strip_name: return
    except Exception: pass
    try:
        used = {s.channel for s in (getattr(seq,'strips',None) or [])}
    except Exception:
        used = set()
    ch = 1
    while ch in used: ch += 1
    fps   = scene.render.fps
    start = scene.frame_current
    dur   = fps * 4
    for attempt in [
        lambda: seq.strips.new_effect(name=strip_name, type='COLOR', channel=ch, frame_start=start, length=dur),
        lambda: seq.strips.new_effect(name=strip_name, type='COLOR', channel=ch, frame_start=start, frame_end=start+dur),
        lambda: seq.sequences.new_effect(name=strip_name, type='COLOR', channel=ch, frame_start=start, frame_end=start+dur),
    ]:
        try:
            strip = attempt()
            strip.color = (0.08, 0.45, 0.26)
            print(f"[Piano] Strip '{strip_name}' criado ✅")
            return
        except Exception: continue
    print(f"[Piano] Falha ao criar strip '{strip_name}'")


# ═══════════════════════════════════════════════════════════════
#  TIMER DE ALTA FREQUÊNCIA — scheduler de notas  [FIX v7]
#
#  Problema do v6: frame_change_post só dispara 1x por frame.
#  A 120 BPM e 24fps = 1 beat/frame → notas de 1/8 (0.5 beat)
#  eram completamente puladas porque o handler não rodava entre
#  frames.
#
#  Solução: bpy.app.timers com intervalo de 5ms (~200Hz).
#  O timer usa time.time() para calcular a posição exata em beats,
#  independente de FPS. Qualquer nota que começar dentro de uma
#  janela de ±10ms é disparada.
# ═══════════════════════════════════════════════════════════════

# Estado do scheduler de alta frequência
_sched_active    = False
_sched_start_time = 0.0    # time.time() quando o play começou
_sched_start_beat = 0.0    # beat em que o play começou
_sched_triggered: set = set()  # (strip_name_or_"", note_idx) já disparados

TIMER_INTERVAL = 0.005     # 5ms = 200Hz


def _get_bpm():
    try:
        return bpy.context.scene.beat_grid.bpm
    except Exception:
        return 120.0


def _pr_note_timer():
    """
    Timer de alta frequência (5ms): calcula beat atual via time.time()
    e dispara sons das notas do Piano Roll.
    Retorna None para parar quando não está em play.
    """
    global _sched_active, _sched_triggered

    try:
        ctx = bpy.context
        if not ctx or not ctx.screen:
            return None if not _sched_active else TIMER_INTERVAL

        is_playing = ctx.screen.is_animation_playing
        if not is_playing:
            if _sched_active:
                # Timeline parou — reseta estado para próximo play
                _sched_active = False
                _sched_triggered.clear()
            return TIMER_INTERVAL

        # Calcula beat atual via tempo real (independente de FPS)
        now  = time.time()
        bpm  = _get_bpm()
        elapsed_beats = (now - _sched_start_time) * (bpm / 60.0)
        current_beat  = _sched_start_beat + elapsed_beats

        # Janela de lookahead: 15ms pra frente para compensar latência de áudio
        lookahead_beats = (0.015) * (bpm / 60.0)

        state    = ctx.scene.piano_roll
        raw_inst = state.instrument

        # Itera todos os strips MIDI
        for ms in state.midi_strips:
            for i, note in enumerate(ms.notes):
                key = (ms.strip_name, i)
                if key in _sched_triggered:
                    continue
                if note.start <= current_beat + lookahead_beats:
                    if note.start >= current_beat - 0.02:  # não retoca nota já passada há mais de 20ms
                        dur_sec = max(note.length * (60.0 / bpm), 0.05)
                        _play_note_sound(note.pitch, raw_inst, dur_sec, note.velocity, from_scheduler=True)
                    _sched_triggered.add(key)

        # Notas soltas (sem strip)
        for i, note in enumerate(state.notes):
            key = ("__global__", i)
            if key in _sched_triggered:
                continue
            if note.start <= current_beat + lookahead_beats:
                if note.start >= current_beat - 0.02:
                    dur_sec = max(note.length * (60.0 / bpm), 0.05)
                    _play_note_sound(note.pitch, raw_inst, dur_sec, note.velocity, from_scheduler=True)
                _sched_triggered.add(key)

    except Exception as e:
        print(f"[Piano] Timer: {e}")

    return TIMER_INTERVAL


# Handler que detecta INÍCIO do play e sincroniza o timer
_pr_last_playing = False


def _piano_roll_frame_handler(scene):
    """
    frame_change_post: detecta início/fim do play e sincroniza o timer.
    NÃO mais responsável por disparar sons (isso é do timer de 5ms).
    """
    global _sched_active, _sched_start_time, _sched_start_beat
    global _pr_last_playing, _sched_triggered

    try:
        is_playing = bpy.context.screen and bpy.context.screen.is_animation_playing

        if is_playing and not _pr_last_playing:
            # Play acabou de começar — registra ponto de referência
            bpm  = _get_bpm()
            fps  = scene.render.fps
            _sched_start_beat = scene.frame_current / fps * (bpm / 60.0)
            _sched_start_time = time.time()
            _sched_active     = True
            _sched_triggered.clear()

        elif not is_playing and _pr_last_playing:
            # Play parou
            _sched_active = False
            _sched_triggered.clear()

        _pr_last_playing = bool(is_playing)

    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
#  RENDERIZAÇÃO DE NOTAS COMO STRIP DE ÁUDIO  [FIX v7]
#
#  O piano roll toca sons em tempo real, mas eles não entram na
#  timeline como áudio mixável. Este operador resolve isso:
#  1. Pega todas as notas do strip ativo (ou notas globais)
#  2. Sintetiza um arquivo .wav com todas as notas mixadas offline
#  3. Insere o .wav como SOUND strip no Sequencer, no canal correto,
#     alinhado com o frame onde o strip MIDI começa
#  4. O strip de áudio fica disponível para mixdown normal
# ═══════════════════════════════════════════════════════════════

class DAW_OT_RenderNotesToStrip(bpy.types.Operator):
    bl_idname      = "daw.render_notes_to_strip"
    bl_label       = "Renderizar Notas → Áudio"
    bl_description = ("Sintetiza as notas MIDI do strip ativo e insere como "
                      "strip de áudio na timeline. Após isso, o áudio é "
                      "exportável e mixável normalmente.")
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene   = context.scene
        state   = scene.piano_roll
        notes   = _get_active_notes(state)

        if len(notes) == 0:
            self.report({'WARNING'}, "Nenhuma nota para renderizar")
            return {'CANCELLED'}

        bpm     = _get_bpm()
        kind, inst_ref = _parse_instrument_id(state.instrument)
        fps     = scene.render.fps

        # ── Calcula duração total necessária ──────────────────
        max_end_beat = max(n.start + n.length for n in notes)
        total_sec    = max_end_beat * (60.0 / bpm) + 1.0  # +1s de cauda
        total_samples = int(total_sec * SAMPLE_RATE)

        self.report({'INFO'}, f"Sintetizando {len(notes)} notas…")

        if kind == "vst":
            # ── Caminho VST: manda todas as notas de uma vez pro worker,
            # que já cuida de polifonia/sobreposição de verdade através
            # do próprio plugin -- não precisa somar buffer manualmente
            # nota a nota como no caminho dos sintetizadores internos. ──
            from ..modules.vst.utils import get_live_vst

            vst = get_live_vst(inst_ref)
            if vst is None or not vst.loaded:
                self.report({'ERROR'}, f"VST '{inst_ref}' não está carregado")
                return {'CANCELLED'}

            midi_notes = [
                (n.pitch, n.start * (60.0 / bpm), max(n.length * (60.0 / bpm), 0.03), n.velocity)
                for n in notes
            ]
            try:
                audio = vst.render_instrument(midi_notes, total_sec)
            except Exception as e:
                self.report({'ERROR'}, f"Falha ao renderizar via VST: {e}")
                return {'CANCELLED'}

            # audio: numpy (channels, n_samples) -- usa canal 0 (mono) pro
            # pipeline de escrita de WAV existente, que espera uma lista
            # de floats em [-1, 1].
            mono = audio[0] if getattr(audio, "ndim", 1) == 2 else audio
            buffer = mono.tolist()
        else:
            inst_id = inst_ref

            # ── Mixdown offline: soma todas as notas num buffer float ──
            buffer = [0.0] * total_samples

            for note in notes:
                start_sec    = note.start * (60.0 / bpm)
                dur_sec      = max(note.length * (60.0 / bpm), 0.03)
                start_sample = int(start_sec * SAMPLE_RATE)

                # Tenta usar sample real primeiro
                note_floats = None
                sample = _load_instrument_sample(inst_id)
                if sample is None:
                    note_floats = _synth_note_samples(note.pitch, inst_id, dur_sec, note.velocity)

                if note_floats is not None:
                    for i, v in enumerate(note_floats):
                        idx = start_sample + i
                        if idx < total_samples:
                            buffer[idx] += v
                # Se sample real foi carregado via aud, não conseguimos os floats
                # diretamente — recaímos na síntese como fallback seguro
                if sample is not None and note_floats is None:
                    note_floats = _synth_note_samples(note.pitch, inst_id, dur_sec, note.velocity)
                    for i, v in enumerate(note_floats):
                        idx = start_sample + i
                        if idx < total_samples:
                            buffer[idx] += v

        # ── Normaliza pico para -3dB ──────────────────────────
        peak = max(abs(v) for v in buffer) if buffer else 0.0
        if peak > 0.001:
            target = 10 ** (-3.0 / 20.0)
            gain   = target / peak
            buffer = [v * gain for v in buffer]

        # ── Escreve WAV ───────────────────────────────────────
        strip_name = state.active_strip or "PianoRoll"
        safe_name  = "".join(c if c.isalnum() or c in "-_" else "_" for c in strip_name)
        out_dir    = bpy.path.abspath("//daw_renders/")
        os.makedirs(out_dir, exist_ok=True)
        wav_path   = os.path.join(out_dir, f"{safe_name}.wav")

        _write_wav(wav_path, buffer)

        if not os.path.isfile(wav_path):
            self.report({'ERROR'}, f"Falha ao escrever WAV: {wav_path}")
            return {'CANCELLED'}

        # ── Insere como SOUND strip no Sequencer ─────────────
        seq = scene.sequence_editor_create()

        # Determina frame de início: pega do strip COLOR correspondente, se existir
        frame_start = scene.frame_start
        try:
            all_strips = getattr(seq,'strips',None) or getattr(seq,'sequences_all',[])
            for s in all_strips:
                if s.name == strip_name:
                    frame_start = s.frame_start
                    break
        except Exception:
            pass

        # Canal: usa um canal acima do strip MIDI
        try:
            used = {s.channel for s in (getattr(seq,'strips',None) or [])}
        except Exception:
            used = set()
        ch = 1
        while ch in used: ch += 1

        # Remove strip de áudio antigo com mesmo nome, se existir
        audio_name = f"{strip_name}_audio"
        try:
            for s in list(getattr(seq,'strips',None) or []):
                if s.name == audio_name:
                    try:    seq.strips.remove(s)
                    except Exception: pass
        except Exception:
            pass

        # Cria o SOUND strip
        # (frame_start pode vir como float de s.frame_start dependendo da
        # versão do Blender/VSE -- new_sound() exige int estritamente)
        frame_start_int = int(round(frame_start))
        try:
            sound_strip = seq.strips.new_sound(
                name=audio_name,
                filepath=wav_path,
                channel=ch,
                frame_start=frame_start_int,
            )
        except AttributeError:
            try:
                sound_strip = seq.sequences.new_sound(
                    name=audio_name,
                    filepath=wav_path,
                    channel=ch,
                    frame_start=frame_start_int,
                )
            except Exception as e:
                self.report({'ERROR'}, f"Falha ao criar strip de áudio: {e}")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Falha ao criar strip de áudio: {e}")
            return {'CANCELLED'}

        self.report({'INFO'},
            f"✅ '{audio_name}' criado no canal {ch} — {len(notes)} notas, "
            f"{total_sec:.1f}s → {wav_path}")
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  DESENHO
# ═══════════════════════════════════════════════════════════════

_shader = None

def _sh():
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader

def _rect(x,y,w,h,col):
    if w<=0 or h<=0: return
    s=_sh(); b=batch_for_shader(s,'TRIS',{"pos":[(x,y),(x+w,y),(x+w,y+h),(x,y),(x+w,y+h),(x,y+h)]})
    s.uniform_float("color",col); b.draw(s)

def _line(x1,y1,x2,y2,col):
    s=_sh(); b=batch_for_shader(s,'LINES',{"pos":[(x1,y1),(x2,y2)]})
    s.uniform_float("color",col); b.draw(s)

def _tri(pts,col):
    s=_sh(); b=batch_for_shader(s,'TRIS',{"pos":pts})
    s.uniform_float("color",col); b.draw(s)

def _txt(text,x,y,size,col):
    blf.size(0,size); blf.color(0,*col); blf.position(0,x,y,0); blf.draw(0,text)

def _note_name(m): return f"{NOTE_NAMES[m%12]}{m//12-1}"
def _is_black(m):  return (m%12) in BLACK_NOTES

def _layout(W,H,state):
    vel_h  = VELOCITY_H if state.show_velocity else 0
    grid_y = SCROLLBAR + vel_h
    hdr_y  = H - TOOLBAR_H - HEADER_H
    return {
        'grid_x': PIANO_W, 'grid_y': grid_y,
        'grid_w': W-PIANO_W-SCROLLBAR, 'grid_h': hdr_y-grid_y,
        'header_y': hdr_y, 'vel_h': vel_h,
        'toolbar_y': H-TOOLBAR_H,
    }


def _draw_piano_roll(context):
    state  = context.scene.piano_roll
    region = context.region
    W, H   = region.width, region.height
    L      = _layout(W, H, state)
    gx,gy  = L['grid_x'], L['grid_y']
    gw,gh  = L['grid_w'], L['grid_h']
    vel_h  = L['vel_h']
    ty     = L['toolbar_y']
    hdr_y  = L['header_y']
    note_h = NOTE_H_BASE * state.zoom_y
    beat_w = BEAT_W_BASE  * state.zoom_x
    snap   = float(state.snap_mode)
    vis    = int(gh / note_h) + 2
    top    = min(int(state.scroll_y + vis/2), 127)

    gpu.state.blend_set('ALPHA')
    _rect(0,0,W,H, C['bg'])

    for i in range(vis+1):
        note = top - i
        if not 0 <= note <= 127: continue
        ny = gy + gh - (i+1)*note_h + (state.scroll_y%1)*note_h
        col = C['bg_c'] if note%12==0 else (C['bg_black'] if _is_black(note) else C['bg'])
        _rect(gx, ny, gw, note_h-0.5, col)
        if note%12==0: _line(gx, ny+note_h, gx+gw, ny+note_h, C['octave'])

    b = 0
    while True:
        bx = gx + b*beat_w - (state.scroll_x%snap)*beat_w
        if bx > gx+gw: break
        beat_abs = state.scroll_x + b*snap
        is_bar = abs(beat_abs%4) < 0.001
        if bx >= gx:
            col = C['grid_bar'] if is_bar else (C['grid_beat'] if abs(beat_abs%1)<0.001 else C['grid'])
            _line(bx, gy, bx, gy+gh, col)
        b += 1
        if b > 4000: break

    notes = _get_active_notes(state)
    for note in notes:
        ni = top - note.pitch
        ny = gy + gh - (ni+1)*note_h + (state.scroll_y%1)*note_h
        if ny+note_h < gy or ny > gy+gh: continue
        nx = gx + (note.start - state.scroll_x)*beat_w
        nw = max(note.length*beat_w-1, 3)
        if nx+nw < gx or nx > gx+gw: continue
        nx2 = max(nx, gx); nw2 = nw-(nx2-nx)
        if nw2 <= 0: continue
        body = C['note_sel'] if note.selected else C['note']
        top2 = C['note_sel']  if note.selected else C['note_top']
        dark = C['note_sel_d'] if note.selected else C['note_dark']
        _rect(nx2, ny+1, nw2, note_h-2, body)
        _rect(nx2, ny+note_h-3, nw2, 2, top2)
        _rect(nx2, ny+1, nw2, 2, dark)
        if nw2>22 and note_h>10:
            _txt(_note_name(note.pitch), nx2+3, ny+3, 9, C['note_txt'])

    ph   = _get_playhead_beat(context)
    ph_x = gx + (ph - state.scroll_x)*beat_w
    if gx <= ph_x <= gx+gw:
        _rect(ph_x-1, gy, 2, gh, C['playhead'])
        _tri([(ph_x-7, hdr_y+HEADER_H),(ph_x+7, hdr_y+HEADER_H),(ph_x, hdr_y+HEADER_H-10)], C['playhead_tri'])

    _rect(0, gy, PIANO_W, gh, (0.058,0.062,0.092,1.0))
    for i in range(vis+1):
        note = top - i
        if not 0 <= note <= 127: continue
        ny = gy + gh - (i+1)*note_h + (state.scroll_y%1)*note_h
        is_b = _is_black(note)
        col  = C['key_c'] if note%12==0 else (C['black_key'] if is_b else C['white_key'])
        pw   = PIANO_W-5 if is_b else PIANO_W-1
        _rect(1, ny+0.5, pw, note_h-1, col)
        if not is_b: _line(1, ny, pw+1, ny, C['key_sep'])
        if note%12==0 and note_h>9:
            _txt(_note_name(note), 3, ny+2, 8, C['text_dim'])
    _line(PIANO_W, gy, PIANO_W, gy+gh, C['separator'])

    _rect(0, hdr_y, W, HEADER_H, C['header'])
    b = 0
    while True:
        bx = gx + b*beat_w - (state.scroll_x%1)*beat_w
        if bx > gx+gw: break
        beat_abs = state.scroll_x + b
        if bx>=gx and abs(beat_abs%4)<0.001:
            _txt(str(int(beat_abs/4)+1), bx+3, hdr_y+6, 11, C['header_bar'])
            _line(bx, hdr_y, bx, hdr_y+HEADER_H, C['grid_bar'])
        elif bx>=gx and abs(beat_abs%1)<0.001:
            _line(bx, hdr_y, bx, hdr_y+HEADER_H//2, C['grid'])
        b += 1
        if b > 4000: break
    if gx <= ph_x <= gx+gw:
        _rect(ph_x-1, hdr_y, 2, HEADER_H, C['playhead'])

    if vel_h > 0:
        _rect(0, SCROLLBAR, W, vel_h, C['vel_bg'])
        _line(0, SCROLLBAR+vel_h, W, SCROLLBAR+vel_h, C['separator'])
        _line(gx, SCROLLBAR, gx, SCROLLBAR+vel_h, C['separator'])
        _txt("VEL", 4, SCROLLBAR+vel_h//2-5, 9, C['text_dim'])
        for note in notes:
            nx = gx + (note.start-state.scroll_x)*beat_w
            nw = max(note.length*beat_w*0.6, 4)
            if nx+nw < gx or nx > gx+gw: continue
            nx2=max(nx,gx); nw2=nw-(nx2-nx)
            if nw2 <= 0: continue
            bh = max(int((note.velocity/127.0)*(vel_h-8)), 2)
            _rect(nx2+1, SCROLLBAR+2, max(nw2-2,2), bh,
                  C['vel_sel'] if note.selected else C['vel_bar'])
        _line(gx, SCROLLBAR+vel_h-4, gx+gw, SCROLLBAR+vel_h-4, C['vel_line'])

    _rect(0, ty, W, TOOLBAR_H, C['toolbar'])
    _line(0, ty, W, ty, C['separator'])
    btn_w,btn_h = 52,22
    bx0 = PIANO_W+8
    for i,(tid,tlabel,ttip) in enumerate(TOOLS):
        bx=bx0+i*(btn_w+4); by=ty+(TOOLBAR_H-btn_h)//2
        is_a = state.tool==tid
        _rect(bx,by,btn_w,btn_h, C['btn_active'] if is_a else C['btn'])
        if is_a: _rect(bx,by,btn_w,2, C['btn_active2'])
        _txt(f"{tlabel[0]}  {ttip[:3]}", bx+6, by+6, 10, C['white'] if is_a else C['text_dim'])
    sx0 = bx0+len(TOOLS)*(btn_w+4)+16
    for i,(sv,sl) in enumerate([('1','1/1'),('0.5','1/2'),('0.25','1/4'),('0.125','1/8'),('0.0625','1/16')]):
        sx=sx0+i*42; sy=ty+(TOOLBAR_H-btn_h)//2; is_a=state.snap_mode==sv
        _rect(sx,sy,38,btn_h, C['btn_active'] if is_a else C['btn'])
        _txt(sl, sx+4, sy+6, 9, C['white'] if is_a else C['text_dim'])
    vtx=sx0+5*42+12; vty=ty+(TOOLBAR_H-btn_h)//2
    _rect(vtx,vty,40,btn_h, C['btn_active'] if state.show_velocity else C['btn'])
    _txt("VEL", vtx+10, vty+6, 10, C['white'] if state.show_velocity else C['text_dim'])

    # Botão Render (azul)
    rx = vtx+50; ry2 = vty
    _rect(rx, ry2, 72, btn_h, C['render_btn'])
    _txt("▶ RENDER", rx+6, ry2+6, 9, C['white'])

    _txt(f"  {state.active_strip or '—'}", 4, ty+10, 11, C['text'])
    _txt("ESC: fechar", W-80, ty+10, 9, C['text_dim'])

    _rect(gx,0,gw,SCROLLBAR-1, C['sb_bg'])
    tw=max(gw*(gw/max(state.total_beats*beat_w,gw+1)),20)
    tx=gx+(state.scroll_x/max(state.total_beats,1))*(gw-tw)
    _rect(tx,1,tw,SCROLLBAR-3, C['sb_th'])
    _rect(W-SCROLLBAR,gy,SCROLLBAR-1,gh, C['sb_bg'])
    th=max(gh*(vis/TOTAL_NOTES),20)
    ty2=gy+gh-(state.scroll_y/127.0)*(gh-th)-th
    _rect(W-SCROLLBAR+1,ty2,SCROLLBAR-3,th, C['sb_th'])

    gpu.state.blend_set('NONE')


def _get_playhead_beat(context):
    try:
        from ..core.register import get_engine
        e = get_engine()
        if e:
            s = e.get_state()
            if s: return s.position_beats
    except Exception: pass
    fps = context.scene.render.fps
    bpm = _get_bpm()
    return (context.scene.frame_current / fps) * (bpm / 60.0)


# ═══════════════════════════════════════════════════════════════
#  TOOLBAR HIT TEST
# ═══════════════════════════════════════════════════════════════

def _toolbar_hit(mx, my, W, H, state):
    L = _layout(W, H, state)
    if my < L['toolbar_y']: return None, None
    btn_w,btn_h = 52,22
    bx0 = PIANO_W+8; ty = L['toolbar_y']
    for i,(tid,_,_) in enumerate(TOOLS):
        bx=bx0+i*(btn_w+4); by=ty+(TOOLBAR_H-btn_h)//2
        if bx<=mx<=bx+btn_w and by<=my<=by+btn_h: return 'TOOL', tid
    sx0=bx0+len(TOOLS)*(btn_w+4)+16
    for i,sv in enumerate(['1','0.5','0.25','0.125','0.0625']):
        sx=sx0+i*42; sy=ty+(TOOLBAR_H-btn_h)//2
        if sx<=mx<=sx+38 and sy<=my<=sy+btn_h: return 'SNAP', sv
    vtx=sx0+5*42+12; vty=ty+(TOOLBAR_H-btn_h)//2
    if vtx<=mx<=vtx+40 and vty<=my<=vty+btn_h: return 'VEL', None
    rx=vtx+50; ry2=vty
    if rx<=mx<=rx+72 and ry2<=my<=ry2+btn_h: return 'RENDER', None
    return 'TOOLBAR', None


# ═══════════════════════════════════════════════════════════════
#  MODAL
# ═══════════════════════════════════════════════════════════════

class DAW_OT_PianoRollModal(bpy.types.Operator):
    bl_idname  = "daw.piano_roll_modal"
    bl_label   = "Piano Roll"
    bl_options = {'REGISTER'}

    _handle = None
    _dragging = False; _drag_mode = None
    _active_note_idx = -1
    _last_x = _last_y = 0

    def _beat(self,x,state,region):
        L=_layout(region.width,region.height,state)
        return state.scroll_x+(x-L['grid_x'])/(BEAT_W_BASE*state.zoom_x)

    def _pitch(self,y,state,region):
        L=_layout(region.width,region.height,state)
        nh=NOTE_H_BASE*state.zoom_y
        vis=L['grid_h']/nh; top=int(state.scroll_y+vis/2)
        return top - int((L['grid_y']+L['grid_h']-y)/nh)

    def _snap(self,beat,state):
        s=float(state.snap_mode); return round(beat/s)*s

    def _in_grid(self,mx,my,region,state):
        L=_layout(region.width,region.height,state)
        return (L['grid_x']<=mx<=region.width-SCROLLBAR and
                L['grid_y']<=my<=L['grid_y']+L['grid_h'])

    def _in_vel(self,mx,my,state,region):
        if not state.show_velocity: return False
        L=_layout(region.width,region.height,state)
        return (L['grid_x']<=mx<=region.width-SCROLLBAR and
                SCROLLBAR<=my<=SCROLLBAR+L['vel_h'])

    def _find(self,beat,pitch,state):
        for i,n in enumerate(_get_active_notes(state)):
            if n.pitch==pitch and n.start<=beat<n.start+n.length: return i
        return -1

    def _add(self,beat,pitch,state,context):
        sn=self._snap(beat,state)
        if self._find(sn,pitch,state) >= 0: return -1
        notes=_get_active_notes(state); n=notes.add()
        n.pitch=max(0,min(127,pitch)); n.start=max(0,sn)
        n.length=float(state.snap_mode); n.velocity=100
        _play_note_sound(n.pitch, state.instrument, n.length*0.5+0.1, n.velocity)
        if state.active_strip:
            _upsert_midi_strip(context, state.active_strip, len(notes))
        return len(notes)-1

    def _remove(self,beat,pitch,state):
        idx=self._find(beat,pitch,state)
        if idx >= 0: _get_active_notes(state).remove(idx)

    def _select_all(self,state,val):
        for n in _get_active_notes(state): n.selected=val

    def invoke(self,context,event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'},"Precisa de VIEW_3D"); return {'CANCELLED'}
        self._handle=bpy.types.SpaceView3D.draw_handler_add(
            _draw_piano_roll,(context,),'WINDOW','POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self,context,event):
        context.area.tag_redraw()
        state=context.scene.piano_roll; region=context.region
        mx,my=event.mouse_region_x,event.mouse_region_y
        W,H=region.width,region.height
        beat_w=BEAT_W_BASE*state.zoom_x; note_h=NOTE_H_BASE*state.zoom_y

        if event.type=='ESC': self._cleanup(context); return {'FINISHED'}

        if event.type=='WHEELUPMOUSE':
            if event.ctrl:    state.zoom_x=min(state.zoom_x*1.15,8.0)
            elif event.shift: state.zoom_y=min(state.zoom_y*1.15,4.0)
            else:             state.scroll_y=min(state.scroll_y+1,127.0)
            return {'RUNNING_MODAL'}
        if event.type=='WHEELDOWNMOUSE':
            if event.ctrl:    state.zoom_x=max(state.zoom_x/1.15,0.1)
            elif event.shift: state.zoom_y=max(state.zoom_y/1.15,0.3)
            else:             state.scroll_y=max(state.scroll_y-1,0.0)
            return {'RUNNING_MODAL'}

        smap={'ONE':'1','TWO':'0.5','THREE':'0.25','FOUR':'0.125','FIVE':'0.0625'}
        if event.type in smap and event.value=='PRESS':
            state.snap_mode=smap[event.type]; return {'RUNNING_MODAL'}

        tmap={'D':'DRAW','S':'SELECT','E':'ERASE','P':'PAN'}
        if event.type in tmap and event.value=='PRESS':
            state.tool=tmap[event.type]; return {'RUNNING_MODAL'}

        if event.type=='A' and event.ctrl and event.value=='PRESS':
            self._select_all(state,True); return {'RUNNING_MODAL'}

        if event.type in ('DEL','X') and event.value=='PRESS':
            notes=_get_active_notes(state)
            for i in range(len(notes)-1,-1,-1):
                if notes[i].selected: notes.remove(i)
            return {'RUNNING_MODAL'}

        if event.type=='MIDDLEMOUSE':
            if event.value=='PRESS':
                self._dragging=True; self._drag_mode='PAN'
                self._last_x,self._last_y=mx,my
            else: self._dragging=False; self._drag_mode=None
            return {'RUNNING_MODAL'}

        if self._dragging and self._drag_mode=='PAN' and event.type=='MOUSEMOVE':
            state.scroll_x=max(0,state.scroll_x-(mx-self._last_x)/beat_w)
            state.scroll_y=max(0,min(127,state.scroll_y+(my-self._last_y)/note_h))
            self._last_x,self._last_y=mx,my; return {'RUNNING_MODAL'}

        if event.type=='LEFTMOUSE':
            if event.value=='PRESS':
                typ,val=_toolbar_hit(mx,my,W,H,state)
                if typ=='TOOL':   state.tool=val; return {'RUNNING_MODAL'}
                if typ=='SNAP':   state.snap_mode=val; return {'RUNNING_MODAL'}
                if typ=='VEL':    state.show_velocity=not state.show_velocity; return {'RUNNING_MODAL'}
                if typ=='RENDER':
                    bpy.ops.daw.render_notes_to_strip('INVOKE_DEFAULT')
                    return {'RUNNING_MODAL'}
                if typ=='TOOLBAR': return {'RUNNING_MODAL'}

                if mx < PIANO_W:
                    p=self._pitch(my,state,region)
                    if 0<=p<=127:
                        _play_note_sound(p, state.instrument, 0.5, 90)
                    return {'RUNNING_MODAL'}

                beat=self._beat(mx,state,region); pitch=self._pitch(my,state,region)

                if self._in_vel(mx,my,state,region):
                    L=_layout(W,H,state); vel_h=L['vel_h']
                    nv=max(1,min(127,int(((my-SCROLLBAR)/max(vel_h,1))*127)))
                    for n in _get_active_notes(state):
                        nx=L['grid_x']+(n.start-state.scroll_x)*beat_w
                        if nx<=mx<=nx+n.length*beat_w: n.velocity=nv
                    self._dragging=True; self._drag_mode='VELOCITY'
                    return {'RUNNING_MODAL'}

                if self._in_grid(mx,my,region,state):
                    if state.tool=='DRAW':
                        self._drag_mode='NOTE_DRAW'
                        self._active_note_idx=self._add(beat,pitch,state,context)
                        self._dragging=True
                    elif state.tool=='SELECT':
                        self._drag_mode='NOTE_SELECT'
                        if not event.shift: self._select_all(state,False)
                        idx=self._find(beat,pitch,state)
                        if idx>=0: _get_active_notes(state)[idx].selected=True
                        self._dragging=True
                    elif state.tool=='ERASE':
                        self._remove(beat,pitch,state)
                        self._drag_mode='NOTE_ERASE'; self._dragging=True
                    elif state.tool=='PAN':
                        self._dragging=True; self._drag_mode='PAN'
                    self._last_x,self._last_y=mx,my

            elif event.value=='RELEASE':
                self._dragging=False; self._drag_mode=None; self._active_note_idx=-1
            return {'RUNNING_MODAL'}

        if event.type=='MOUSEMOVE' and self._dragging:
            beat=self._beat(mx,state,region); pitch=self._pitch(my,state,region)
            if self._drag_mode=='NOTE_DRAW':
                notes=_get_active_notes(state)
                if 0<=self._active_note_idx<len(notes):
                    n=notes[self._active_note_idx]; snap=float(state.snap_mode)
                    n.length=max(snap,self._snap(beat-n.start+snap,state))
            elif self._drag_mode=='NOTE_ERASE':
                self._remove(beat,pitch,state)
            elif self._drag_mode=='PAN':
                state.scroll_x=max(0,state.scroll_x-(mx-self._last_x)/beat_w)
                state.scroll_y=max(0,min(127,state.scroll_y+(my-self._last_y)/note_h))
                self._last_x,self._last_y=mx,my
            return {'RUNNING_MODAL'}

        if event.type=='RIGHTMOUSE' and event.value=='PRESS':
            if self._in_grid(mx,my,region,state):
                self._remove(self._beat(mx,state,region),self._pitch(my,state,region),state)
            elif mx < PIANO_W:
                p=self._pitch(my,state,region)
                if 0<=p<=127: _play_note_sound(p, state.instrument, 0.5, 90)
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}

    def _cleanup(self,context):
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle,'WINDOW')
            self._handle=None
        context.area.tag_redraw()


# ═══════════════════════════════════════════════════════════════
#  ABRIR JANELA FLUTUANTE
# ═══════════════════════════════════════════════════════════════

class DAW_OT_OpenPianoRoll(bpy.types.Operator):
    bl_idname      = "daw.open_piano_roll"
    bl_label       = "Abrir Piano Roll"
    bl_description = "Abre o Piano Roll em janela flutuante"

    def execute(self, context):
        bpy.ops.wm.window_new()
        def _setup():
            try:
                new_win = bpy.context.window_manager.windows[-1]
                for area in new_win.screen.areas:
                    area.type = 'VIEW_3D'
                    for sp in area.spaces:
                        if sp.type == 'VIEW_3D':
                            sp.overlay.show_overlays = False
                            sp.show_gizmo = False
                            sp.shading.type = 'SOLID'
                    win_reg = next((r for r in area.regions if r.type=='WINDOW'), None)
                    if win_reg:
                        with bpy.context.temp_override(window=new_win, area=area, region=win_reg):
                            bpy.ops.daw.piano_roll_modal('INVOKE_DEFAULT')
                    break
            except Exception as e:
                print(f"[Piano] Erro ao abrir: {e}")
            return None
        bpy.app.timers.register(_setup, first_interval=0.25)
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  NOVA TRACK MIDI
# ═══════════════════════════════════════════════════════════════

class DAW_OT_NewMidiStrip(bpy.types.Operator):
    bl_idname      = "daw.new_midi_strip"
    bl_label       = "Nova Track MIDI"
    bl_description = "Cria strip MIDI no Sequencer e abre o Piano Roll"

    def execute(self, context):
        scene = context.scene
        state = scene.piano_roll
        seq   = scene.sequence_editor_create()
        try:
            used = {s.channel for s in (getattr(seq,'strips',None) or [])}
        except Exception:
            used = set()
        ch = 1
        while ch in used: ch += 1
        idx  = len(state.midi_strips)+1
        name = f"MIDI {idx:02d}"
        fps  = scene.render.fps
        start = scene.frame_current; dur = fps*4
        strip = None
        for attempt in [
            lambda: seq.strips.new_effect(name=name, type='COLOR', channel=ch, frame_start=start, length=dur),
            lambda: seq.strips.new_effect(name=name, type='COLOR', channel=ch, frame_start=start, frame_end=start+dur),
            lambda: seq.sequences.new_effect(name=name, type='COLOR', channel=ch, frame_start=start, frame_end=start+dur),
        ]:
            try: strip=attempt(); break
            except Exception: continue
        if not strip:
            self.report({'ERROR'}, "Falha ao criar strip"); return {'CANCELLED'}
        strip.color = (0.08, 0.45, 0.26)
        ms = state.midi_strips.add()
        ms.strip_name = name
        state.active_strip = name
        bpy.ops.daw.open_piano_roll('INVOKE_DEFAULT')
        self.report({'INFO'}, f"Track '{name}' criada")
        return {'FINISHED'}


class DAW_OT_SelectMidiStrip(bpy.types.Operator):
    bl_idname  = "daw.select_midi_strip"
    bl_label   = "Editar Strip"
    strip_name: StringProperty()
    def execute(self, context):
        context.scene.piano_roll.active_strip = self.strip_name
        bpy.ops.daw.open_piano_roll('INVOKE_DEFAULT')
        return {'FINISHED'}


class DAW_OT_ClearNotes(bpy.types.Operator):
    bl_idname = "daw.clear_notes"
    bl_label  = "Limpar Notas"
    def execute(self, context):
        _get_active_notes(context.scene.piano_roll).clear()
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  TIMER REDRAW
# ═══════════════════════════════════════════════════════════════

def _pr_redraw():
    try:
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                if a.type == 'VIEW_3D': a.tag_redraw()
    except Exception: pass
    return 1/30


# ═══════════════════════════════════════════════════════════════
#  PANELS
# ═══════════════════════════════════════════════════════════════

class DAW_PT_PianoRollPanel(bpy.types.Panel):
    bl_label       = "Piano Roll"
    bl_idname      = "DAW_PT_piano_roll_panel"
    bl_space_type  = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category    = "DAW"
    bl_order       = 1

    def draw(self, context):
        layout = self.layout
        state  = context.scene.piano_roll

        layout.operator("daw.new_midi_strip", icon='ADD', text="Nova Track MIDI")
        layout.separator()

        if len(state.midi_strips) > 0:
            box = layout.box()
            box.label(text="Tracks MIDI:", icon='SEQUENCE')
            for ms in state.midi_strips:
                row = box.row(align=True)
                is_a = ms.strip_name == state.active_strip
                op   = row.operator("daw.select_midi_strip",
                                    text=ms.strip_name,
                                    icon='PLAY' if is_a else 'DOT')
                op.strip_name = ms.strip_name
                row.label(text=f"{len(ms.notes)} notas")
            layout.separator()

        layout.operator("daw.open_piano_roll", icon='SOUND', text="Abrir Piano Roll ↗")
        layout.separator()

        box2 = layout.box()
        box2.label(text="Synth Interno", icon='SOUND')
        box2.prop(state, "instrument", text="")

        # Renderização
        layout.separator()
        box3 = layout.box()
        box3.label(text="Exportar para Timeline", icon='FILE_SOUND')
        box3.operator("daw.render_notes_to_strip", icon='RENDER_STILL',
                      text="Renderizar Notas → Áudio")
        box3.label(text="Gera WAV em //daw_renders/", icon='INFO')

        notes = _get_active_notes(state)
        if len(notes) > 0:
            layout.separator()
            layout.operator("daw.clear_notes", icon='TRASH',
                            text=f"Limpar {len(notes)} notas")


class DAW_OT_LoadProgression(bpy.types.Operator):
    bl_idname      = "daw.load_progression"
    bl_label       = "Carregar Progressão"
    progression_name: StringProperty()

    def execute(self, context):
        state = context.scene.piano_roll
        try:
            from ..synth import progression_to_midi_notes
            midi_notes = progression_to_midi_notes(self.progression_name)
            notes = _get_active_notes(state)
            notes.clear()
            for nd in midi_notes:
                n = notes.add()
                n.pitch=nd["pitch"]; n.start=nd["start"]
                n.length=nd["length"]; n.velocity=nd["velocity"]
            if state.active_strip:
                _upsert_midi_strip(context, state.active_strip, len(notes))
            self.report({'INFO'}, f"✅ {len(midi_notes)} notas carregadas")
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  REGISTRO
# ═══════════════════════════════════════════════════════════════

classes = (
    MidiNote, MidiStripData, PianoRollState,
    DAW_OT_PianoRollModal, DAW_OT_OpenPianoRoll,
    DAW_OT_NewMidiStrip, DAW_OT_SelectMidiStrip,
    DAW_OT_ClearNotes, DAW_OT_LoadProgression,
    DAW_OT_RenderNotesToStrip,
    DAW_PT_PianoRollPanel,
)

addon_keymaps = []


def register():
    for cls in classes:
        try: bpy.utils.unregister_class(cls)
        except Exception: pass
        bpy.utils.register_class(cls)
    bpy.types.Scene.piano_roll = bpy.props.PointerProperty(type=PianoRollState)

    if not bpy.app.timers.is_registered(_pr_redraw):
        bpy.app.timers.register(_pr_redraw, persistent=True)

    # [FIX v7] Timer de alta frequência para scheduler de notas
    if not bpy.app.timers.is_registered(_pr_note_timer):
        bpy.app.timers.register(_pr_note_timer, persistent=True, first_interval=TIMER_INTERVAL)

    # Handler de frame para detectar início/fim do play
    if _piano_roll_frame_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_piano_roll_frame_handler)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km  = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(DAW_OT_OpenPianoRoll.bl_idname,
                                   type='P', value='PRESS', shift=True)
        addon_keymaps.append((km, kmi))


def unregister():
    if _piano_roll_frame_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_piano_roll_frame_handler)
    if bpy.app.timers.is_registered(_pr_note_timer):
        bpy.app.timers.unregister(_pr_note_timer)
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    if bpy.app.timers.is_registered(_pr_redraw):
        bpy.app.timers.unregister(_pr_redraw)
    try: del bpy.types.Scene.piano_roll
    except Exception: pass
    for cls in reversed(classes):
        try: bpy.utils.unregister_class(cls)
        except Exception: pass