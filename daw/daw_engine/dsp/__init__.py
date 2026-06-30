# dsp/__init__.py
"""
Pacote de processamento de sinal digital (DSP) da DAW.

Contém os blocos de construção de baixo nível usados pelos instrumentos
(daw_engine/instruments/) e pelo mixer: osciladores e envelopes.

Estava vazio antes — exportar aqui evita que outros módulos precisem
saber o caminho interno exato de cada classe (ex: instruments/synth.py
pode fazer `from ..dsp import SineOsc, ADSR` em vez de importar de
arquivos individuais).
"""
from __future__ import annotations

from .oscillator import (
    Oscillator,
    SineOsc,
    SawOsc,
    SquareOsc,
    TriangleOsc,
    create_oscillator,
    available_waveforms,
)
from .adsr import ADSR, ADSRStage

__all__ = [
    "Oscillator",
    "SineOsc",
    "SawOsc",
    "SquareOsc",
    "TriangleOsc",
    "create_oscillator",
    "available_waveforms",
    "ADSR",
    "ADSRStage",
]