"""
DAW Sampler - Addon de Síntese por Samples para Blender

Um módulo de sampler completo integrado ao Blender, com suporte a:
  • Reprodução polifônica de samples (até 64 vozes simultâneas)
  • Transposição de pitch via MIDI notes (resampling linear)
  • Envelope ADSR clássico
  • Modos de loop (OFF, FORWARD, PING_PONG) com crossfade
  • Fatiamento automático (equal, transientes)
  • Time-stretch (overlap-add)
  • Snap de loop para zero-crossing
  • UI completa em Blender Properties

Arquitetura:
  - adsr.py: Envelope ADSR (5 estágios + idle)
  - envelopes.py: Fades genéricos (linear, equal-power) + breakpoint envelope
  - looping.py: Loop cursor, crossfade de junções, busca de zero-crossing
  - pitch.py: Cálculos de ratio (semitons, cents) + resampling
  - player.py: Classe Voice (reprodutor com pitch/loop/envelope)
  - properties.py: PropertyGroups Blender (samples, ADSR, slices, settings)
  - slicing.py: Fatiamento igual + detecção automática de transientes
  - timestretch.py: Time-stretch via overlap-add
  - operators.py: Operadores Blender (load, preview, slice, loop snap)
  - ui.py: Painéis da UI (main, sample settings, slicing, preview)
  - utils.py: Utilitários (MIDI note ↔ freq, dB ↔ linear, WAV parser)
  - register.py: Registro centralizado

Use: ativar addon em Blender → Scene Properties → "Sampler" panel
"""

bl_info = {
    "name": "DAW Sampler",
    "description": "Sintetizador por samples com pitch, loop, envelope e fatiamento",
    "author": "ItaloNicacio (GeckoLabs)",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "Scene Properties > Sampler",
    "category": "Audio",
    "support": "COMMUNITY",
    "doc_url": "https://github.com/ItaloNicacioDev",
    "tracker_url": "https://github.com/ItaloNicacioDev/issues",
}

import sys
import importlib
from pathlib import Path

# ============================================================================
# Importação dinâmica dos módulos com hot-reload suportado
# ============================================================================

# Referência ao pacote de módulos
_module_base = Path(__file__).parent.name
_modules = [
    'adsr',
    'envelopes',
    'looping',
    'pitch',
    'player',
    'properties',
    'slicing',
    'timestretch',
    'utils',
    'operators',
    'ui',
    'register',
]

# Recarrega módulos já importados em hot-reload
for mod_name in _modules:
    full_name = f"bpy.app.handlers.{_module_base}.{mod_name}" if '.' in __name__ else f"{__name__}.{mod_name}"
    if full_name in sys.modules:
        importlib.reload(sys.modules[full_name])

# Importação limpa
from . import (
    adsr,
    envelopes,
    looping,
    pitch,
    player,
    properties,
    slicing,
    timestretch,
    utils,
    operators,
    ui,
)
# [FIX] Ver comentário equivalente em modules/settings/__init__.py -- sem
# alias, `from . import register` colidia com `def register()` abaixo e
# quebrava com "AttributeError: 'function' object has no attribute
# 'register'", impedindo o módulo sampler de registrar.
from . import register as register_module

__all__ = [
    'adsr',
    'envelopes',
    'looping',
    'pitch',
    'player',
    'properties',
    'slicing',
    'timestretch',
    'utils',
    'operators',
    'ui',
    'register_module',
]


def register():
    """Registra o addon (chamado automaticamente pelo Blender)."""
    register_module.register()


def unregister():
    """Desregistra o addon (chamado automaticamente pelo Blender)."""
    register_module.unregister()


if __name__ == "__main__":
    register()