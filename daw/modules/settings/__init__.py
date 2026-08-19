"""
DAW Settings - Módulo de Configurações e Preferências

Gerencia todas as configurações do addon DAW:
  • Preferências globais (audio, UI, workspace)
  • Temas visuais (escuro, claro, Blender padrão)
  • Atalhos de teclado customizáveis
  • Salva/carrega presets de configuração
  • Export/import de settings
  • Auto-save e recovery

Arquitetura:
  - preferences.py: AddonPreferences + PropertyGroups
  - themes.py: Paletas de cores (DARK, LIGHT, BLENDER)
  - shortcuts.py: Gerenciador de keymaps
  - operators.py: Operadores de settings (reset, export, etc)
  - ui.py: Painéis de preferências do Blender
  - utils.py: Utilitários (JSON, validação, serialização)
  - register.py: Registro centralizado + app handlers

Use: Edit → Preferences → Add-ons → DAW → Preferences button
"""

import sys
import importlib
from pathlib import Path

# ============================================================================
# Importação dinâmica dos módulos com hot-reload suportado
# ============================================================================

_module_base = Path(__file__).parent.name
_modules = [
    'preferences',
    'themes',
    'shortcuts',
    'utils',
    'operators',
    'ui',
    'register',
]

# Recarrega módulos já importados em hot-reload
for mod_name in _modules:
    full_name = f"{__name__}.{mod_name}"
    if full_name in sys.modules:
        importlib.reload(sys.modules[full_name])

# Importação limpa
from . import (
    preferences,
    themes,
    shortcuts,
    utils,
    operators,
    ui,
)
# [FIX] Importado com alias -- `from . import register` sem alias colide
# com a função `def register()` definida embaixo neste mesmo arquivo: o
# nome global `register` acaba sendo sobrescrito pela função no momento
# em que ela é definida, então `register.register()` (dentro da própria
# função) passava a chamar um atributo da função, não do submódulo, e
# quebrava com "AttributeError: 'function' object has no attribute
# 'register'". Isso fazia o módulo settings (preferências de áudio,
# incluindo `prefs.audio`) nunca registrar de verdade.
from . import register as register_module

__all__ = [
    'preferences',
    'themes',
    'shortcuts',
    'utils',
    'operators',
    'ui',
    'register_module',
]


def register():
    """Registra o módulo (chamado automaticamente pelo Blender)."""
    register_module.register()
    register_module.register_handlers()


def unregister():
    """Desregistra o módulo (chamado automaticamente pelo Blender)."""
    register_module.unregister_handlers()
    register_module.unregister()


if __name__ == "__main__":
    register()