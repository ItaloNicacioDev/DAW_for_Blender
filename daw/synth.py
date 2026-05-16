"""
daw/synth.py

Sintetizador interno da DAW — estilo GM (General MIDI)
Usa o módulo `aud` nativo do Blender (Audaspace) para síntese em tempo real.

Instrumentos disponíveis (aproximação por síntese aditiva):
  0  — Acoustic Grand Piano
  1  — Electric Piano
  2  — Strings / Pad
  3  — Organ
  4  — Bass
  5  — Synth Lead
  6  — Vibraphone
  7  — Choir

Progressões de acordes pré-carregadas:
  C major scale, minor progressions, jazz, phonk, etc.
"""

import math
import struct
import aud

# ═══════════════════════════════════════════════════════════════
#  CONSTANTES
# ═══════════════════════════════════════════════════════════════

SAMPLE_RATE = 44100
CHANNELS    = 1      # mono (mixado externamente)
NOTE_NAMES  = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']


# ═══════════════════════════════════════════════════════════════
#  MIDI → FREQUÊNCIA
# ═══════════════════════════════════════════════════════════════

def midi_to_freq(note: int) -> float:
    """Converte nota MIDI (0-127) para frequência Hz."""
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def note_name(midi: int) -> str:
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


# ═══════════════════════════════════════════════════════════════
#  DEFINIÇÕES DOS INSTRUMENTOS GM
#  Cada instrumento: lista de (harmônico, amplitude, detune_cents)
#  + envelope ADSR em segundos/fração
# ═══════════════════════════════════════════════════════════════

INSTRUMENTS = {
    0: {  # Acoustic Grand Piano
        "name": "Acoustic Piano",
        "harmonics": [
            (1,  1.00,  0.0),
            (2,  0.50,  0.3),
            (3,  0.25,  0.0),
            (4,  0.12, -0.2),
            (5,  0.06,  0.1),
            (6,  0.03,  0.0),
            (7,  0.015, 0.2),
            (8,  0.008, 0.0),
        ],
        "attack":  0.003,
        "decay":   0.25,
        "sustain": 0.45,
        "release": 0.40,
        "brightness": 0.8,
    },
    1: {  # Electric Piano (Rhodes-style)
        "name": "Electric Piano",
        "harmonics": [
            (1,  1.00,  0.0),
            (2,  0.30,  0.5),
            (3,  0.60,  0.0),
            (4,  0.10, -0.5),
            (5,  0.20,  0.3),
        ],
        "attack":  0.005,
        "decay":   0.30,
        "sustain": 0.55,
        "release": 0.35,
        "brightness": 0.6,
    },
    2: {  # Strings / Pad
        "name": "Strings",
        "harmonics": [
            (1,  1.00,  0.0),
            (2,  0.60,  1.5),   # detune para chorus
            (3,  0.35, -1.5),
            (4,  0.20,  0.8),
            (5,  0.10, -0.8),
        ],
        "attack":  0.08,
        "decay":   0.50,
        "sustain": 0.80,
        "release": 0.60,
        "brightness": 0.4,
    },
    3: {  # Organ (Hammond-style)
        "name": "Organ",
        "harmonics": [
            (1,  1.00, 0.0),
            (2,  1.00, 0.0),
            (3,  0.80, 0.0),
            (4,  0.70, 0.0),
            (5,  0.00, 0.0),
            (6,  0.50, 0.0),
            (8,  0.30, 0.0),
        ],
        "attack":  0.01,
        "decay":   0.01,
        "sustain": 0.95,
        "release": 0.05,
        "brightness": 1.0,
    },
    4: {  # Bass
        "name": "Bass",
        "harmonics": [
            (1,  1.00,  0.0),
            (2,  0.80,  0.2),
            (3,  0.40,  0.0),
            (4,  0.15, -0.2),
        ],
        "attack":  0.004,
        "decay":   0.12,
        "sustain": 0.60,
        "release": 0.15,
        "brightness": 0.7,
    },
    5: {  # Synth Lead
        "name": "Synth Lead",
        "harmonics": [
            (1,  1.00,  0.0),
            (2,  0.70,  2.0),   # detune "supersaw"
            (3,  0.50, -2.0),
            (4,  0.30,  1.0),
            (5,  0.20, -1.0),
        ],
        "attack":  0.01,
        "decay":   0.20,
        "sustain": 0.70,
        "release": 0.25,
        "brightness": 0.9,
    },
    6: {  # Vibraphone
        "name": "Vibraphone",
        "harmonics": [
            (1,  1.00, 0.0),
            (2,  0.05, 0.0),
            (3,  0.30, 0.0),
            (4,  0.02, 0.0),
        ],
        "attack":  0.005,
        "decay":   0.80,
        "sustain": 0.20,
        "release": 0.70,
        "brightness": 0.95,
    },
    7: {  # Choir / Vocal Pad
        "name": "Choir",
        "harmonics": [
            (1,  1.00,  0.0),
            (2,  0.50,  2.0),
            (3,  0.70,  0.0),
            (4,  0.30, -2.0),
            (5,  0.40,  1.0),
            (6,  0.20, -1.0),
        ],
        "attack":  0.12,
        "decay":   0.40,
        "sustain": 0.75,
        "release": 0.50,
        "brightness": 0.5,
    },
}


# ═══════════════════════════════════════════════════════════════
#  GERAÇÃO DE AMOSTRAS PCM
# ═══════════════════════════════════════════════════════════════

def _cents_to_ratio(cents: float) -> float:
    return 2.0 ** (cents / 1200.0)


def generate_note_pcm(midi_note: int, instrument_id: int = 0,
                      duration: float = 1.0, velocity: int = 100) -> bytes:
    """
    Gera dados PCM (16-bit, mono, 44100 Hz) para uma nota MIDI.
    Usa síntese aditiva com envelope ADSR.
    """
    inst   = INSTRUMENTS.get(instrument_id, INSTRUMENTS[0])
    freq   = midi_to_freq(midi_note)
    vol    = (velocity / 127.0) ** 0.8  # curva de velocidade

    n_samples = int(SAMPLE_RATE * duration)

    attack   = inst["attack"]
    decay    = inst["decay"]
    sustain  = inst["sustain"]
    release  = inst["release"]

    a_smp = int(attack  * SAMPLE_RATE)
    d_smp = int(decay   * SAMPLE_RATE)
    r_smp = int(release * SAMPLE_RATE)
    s_smp = max(0, n_samples - a_smp - d_smp - r_smp)

    samples = []
    for i in range(n_samples):
        t = i / SAMPLE_RATE

        # ADSR envelope
        if i < a_smp:
            env = i / max(a_smp, 1)
        elif i < a_smp + d_smp:
            p   = (i - a_smp) / max(d_smp, 1)
            env = 1.0 - p * (1.0 - sustain)
        elif i < a_smp + d_smp + s_smp:
            env = sustain
        else:
            p   = (i - a_smp - d_smp - s_smp) / max(r_smp, 1)
            env = sustain * (1.0 - p)

        # Síntese aditiva — soma harmônicos
        sample = 0.0
        for (harm, amp, detune) in inst["harmonics"]:
            f = freq * harm * _cents_to_ratio(detune)
            sample += amp * math.sin(2.0 * math.pi * f * t)

        # Normaliza e aplica envelope + velocity
        sample = (sample / len(inst["harmonics"])) * env * vol * 0.7

        # Quantiza para int16
        s16 = max(-32767, min(32767, int(sample * 32767)))
        samples.append(s16)

    return struct.pack(f"<{n_samples}h", *samples)


# ═══════════════════════════════════════════════════════════════
#  PLAYER VIA MÓDULO aud DO BLENDER
# ═══════════════════════════════════════════════════════════════

_device: aud.Device = None


def _get_device() -> aud.Device:
    global _device
    if _device is None:
        try:
            _device = aud.Device()
        except Exception as e:
            print(f"[DAW Synth] Erro ao abrir dispositivo de áudio: {e}")
    return _device


def play_note(midi_note: int, instrument_id: int = 0,
              duration: float = 0.8, velocity: int = 100):
    """Toca uma nota MIDI imediatamente via aud."""
    try:
        dev = _get_device()
        if dev is None:
            return

        pcm  = generate_note_pcm(midi_note, instrument_id, duration, velocity)
        snd  = aud.Sound.buffer(pcm, SAMPLE_RATE, CHANNELS, aud.FORMAT_S16)
        dev.play(snd)

    except Exception as e:
        print(f"[DAW Synth] Erro ao tocar nota {midi_note}: {e}")


def play_chord(midi_notes: list, instrument_id: int = 0,
               duration: float = 1.5, velocity: int = 90):
    """Toca um acorde (várias notas simultaneamente)."""
    for note in midi_notes:
        play_note(note, instrument_id, duration, velocity)


# ═══════════════════════════════════════════════════════════════
#  PROGRESSÕES DE ACORDES PRÉ-DEFINIDAS
# ═══════════════════════════════════════════════════════════════

# Notas MIDI — oitava 4 (C4 = 60)
def _chord(root, intervals):
    return [root + i for i in intervals]

MAJ  = [0, 4, 7]           # maior
MIN  = [0, 3, 7]           # menor
MAJ7 = [0, 4, 7, 11]       # maior 7
MIN7 = [0, 3, 7, 10]       # menor 7
DOM7 = [0, 4, 7, 10]       # dominante 7
SUS4 = [0, 5, 7]           # sus4
DIM  = [0, 3, 6]           # diminuto
AUG  = [0, 4, 8]           # aumentado
ADD9 = [0, 4, 7, 14]       # add9

# Raízes MIDI (oitava 3)
_C3, _D3, _E3, _F3, _G3, _A3, _B3 = 48, 50, 52, 53, 55, 57, 59
_C4, _D4, _E4, _F4, _G4, _A4, _B4 = 60, 62, 64, 65, 67, 69, 71

CHORD_PROGRESSIONS = {

    # ── Pop / Positivo ────────────────────────────────────────
    "I–V–vi–IV (Pop)": {
        "description": "A progressão mais usada no pop",
        "bpm": 120,
        "beats_per_chord": 4,
        "chords": [
            {"name": "C maj",  "notes": _chord(_C4, MAJ),  "beat": 0},
            {"name": "G maj",  "notes": _chord(_G3, MAJ),  "beat": 4},
            {"name": "A min",  "notes": _chord(_A3, MIN),  "beat": 8},
            {"name": "F maj",  "notes": _chord(_F3, MAJ),  "beat": 12},
        ]
    },

    "I–IV–V–I (Blues/Gospel)": {
        "description": "12-bar blues condensado",
        "bpm": 95,
        "beats_per_chord": 4,
        "chords": [
            {"name": "C7",     "notes": _chord(_C3, DOM7), "beat": 0},
            {"name": "F7",     "notes": _chord(_F3, DOM7), "beat": 4},
            {"name": "C7",     "notes": _chord(_C3, DOM7), "beat": 8},
            {"name": "G7",     "notes": _chord(_G3, DOM7), "beat": 12},
        ]
    },

    # ── Sad / Melancólico ─────────────────────────────────────
    "vi–IV–I–V (Sad Pop)": {
        "description": "Progressão melancólica muito usada",
        "bpm": 75,
        "beats_per_chord": 4,
        "chords": [
            {"name": "A min",  "notes": _chord(_A3, MIN),  "beat": 0},
            {"name": "F maj",  "notes": _chord(_F3, MAJ),  "beat": 4},
            {"name": "C maj",  "notes": _chord(_C4, MAJ),  "beat": 8},
            {"name": "G maj",  "notes": _chord(_G3, MAJ),  "beat": 12},
        ]
    },

    "Dó Menor (Épico)": {
        "description": "Dark, cinematográfico",
        "bpm": 80,
        "beats_per_chord": 4,
        "chords": [
            {"name": "C min",  "notes": _chord(_C4, MIN),  "beat": 0},
            {"name": "Bb maj", "notes": _chord(_B3-2, MAJ),"beat": 4},
            {"name": "Ab maj", "notes": _chord(_A3-1, MAJ),"beat": 8},
            {"name": "G maj",  "notes": _chord(_G3, MAJ),  "beat": 12},
        ]
    },

    # ── Jazz ──────────────────────────────────────────────────
    "ii–V–I (Jazz)": {
        "description": "Progressão fundamental do jazz",
        "bpm": 110,
        "beats_per_chord": 4,
        "chords": [
            {"name": "D min7", "notes": _chord(_D4, MIN7), "beat": 0},
            {"name": "G dom7", "notes": _chord(_G3, DOM7), "beat": 4},
            {"name": "C maj7", "notes": _chord(_C4, MAJ7), "beat": 8},
            {"name": "C maj7", "notes": _chord(_C4, MAJ7), "beat": 12},
        ]
    },

    "Autumn Leaves (Jazz)": {
        "description": "Clássico do jazz",
        "bpm": 100,
        "beats_per_chord": 4,
        "chords": [
            {"name": "C min7", "notes": _chord(_C4, MIN7), "beat": 0},
            {"name": "F dom7", "notes": _chord(_F3, DOM7), "beat": 4},
            {"name": "Bb maj7","notes": _chord(_B3-2, MAJ7),"beat": 8},
            {"name": "Eb maj7","notes": _chord(_E3-1, MAJ7),"beat": 12},
        ]
    },

    # ── Phonk / Lo-fi ─────────────────────────────────────────
    "Phonk Dark": {
        "description": "Progressão phonk/trap sombria",
        "bpm": 73,
        "beats_per_chord": 4,
        "chords": [
            {"name": "F min",  "notes": _chord(_F3, MIN),  "beat": 0},
            {"name": "Eb maj", "notes": _chord(_E3-1, MAJ),"beat": 4},
            {"name": "Db maj", "notes": _chord(_D3-1, MAJ),"beat": 8},
            {"name": "C maj",  "notes": _chord(_C4, MAJ),  "beat": 12},
        ]
    },

    "Lo-Fi Chill": {
        "description": "Jazz-hop relaxado",
        "bpm": 85,
        "beats_per_chord": 4,
        "chords": [
            {"name": "D maj7", "notes": _chord(_D4, MAJ7), "beat": 0},
            {"name": "B min7", "notes": _chord(_B3, MIN7), "beat": 4},
            {"name": "G maj7", "notes": _chord(_G3, MAJ7), "beat": 8},
            {"name": "A dom7", "notes": _chord(_A3, DOM7), "beat": 12},
        ]
    },

    # ── Épico / Cinematográfico ───────────────────────────────
    "Epic Cinematic": {
        "description": "Trilha cinematográfica épica",
        "bpm": 88,
        "beats_per_chord": 4,
        "chords": [
            {"name": "D min",  "notes": _chord(_D4, MIN),  "beat": 0},
            {"name": "Bb maj", "notes": _chord(_B3-2, MAJ),"beat": 4},
            {"name": "C maj",  "notes": _chord(_C4, MAJ),  "beat": 8},
            {"name": "A min",  "notes": _chord(_A3, MIN),  "beat": 12},
        ]
    },

    "Hans Zimmer-ish": {
        "description": "Minimalista e tenso",
        "bpm": 70,
        "beats_per_chord": 4,
        "chords": [
            {"name": "A min",  "notes": _chord(_A3, MIN),  "beat": 0},
            {"name": "E min",  "notes": _chord(_E3, MIN),  "beat": 4},
            {"name": "F maj",  "notes": _chord(_F3, MAJ),  "beat": 8},
            {"name": "E min",  "notes": _chord(_E3, MIN),  "beat": 12},
        ]
    },
}


def get_progression_names() -> list:
    return list(CHORD_PROGRESSIONS.keys())


def get_progression(name: str) -> dict:
    return CHORD_PROGRESSIONS.get(name, {})


def progression_to_midi_notes(name: str, snap: float = 0.25) -> list:
    """
    Converte uma progressão de acordes em lista de notas MIDI
    prontas para inserir no Piano Roll.

    Retorna lista de dicts: {pitch, start, length, velocity}
    """
    prog = get_progression(name)
    if not prog:
        return []

    bpc  = prog.get("beats_per_chord", 4)
    out  = []

    for chord in prog["chords"]:
        beat = chord["beat"]
        for i, note in enumerate(chord["notes"]):
            # Arpeja levemente as notas do acorde (+0.05 por voz)
            out.append({
                "pitch":    note,
                "start":    beat + i * 0.02,
                "length":   bpc - 0.1,
                "velocity": 90 if i == 0 else 75,
            })

    return out


# ═══════════════════════════════════════════════════════════════
#  PREVIEW — toca o acorde ao clicar na tecla do piano
# ═══════════════════════════════════════════════════════════════

_current_instrument = 0


def set_instrument(instrument_id: int):
    global _current_instrument
    _current_instrument = instrument_id


def get_instrument() -> int:
    return _current_instrument


def preview_note(midi_note: int, velocity: int = 90):
    """Toca preview de nota ao clicar na lateral do Piano Roll."""
    play_note(midi_note, _current_instrument, duration=0.6, velocity=velocity)


def preview_chord_by_name(name: str):
    """Toca preview de uma progressão de acordes."""
    prog = get_progression(name)
    if prog and prog.get("chords"):
        first_chord = prog["chords"][0]
        play_chord(first_chord["notes"], _current_instrument,
                   duration=2.0, velocity=85)