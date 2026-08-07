# dawdreamer/__init__.py
"""
Ponte entre o pacote Python `dawdreamer` e a extensao nativa compilada
(`dawdreamer.pyd` no Windows, `dawdreamer.so` no Linux/macOS), que fica
dentro desta mesma pasta.

Sem isso, `import dawdreamer` acha a pasta (e um pacote valido por ter
`__init__.py`), mas o modulo fica vazio -- nenhum atributo como
`RenderEngine`, `PluginProcessor` etc. e exposto no nivel do pacote.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent

# -----------------------------------------------------------------
# Windows: garante que DLLs dependentes ao lado da extensao sejam
# encontradas mesmo quando este pacote nao esta instalado via pip
# (Python 3.8+ nao usa mais PATH para isso, precisa de add_dll_directory).
# -----------------------------------------------------------------
if sys.platform.startswith("win") and hasattr(os, "add_dll_directory"):
    try:
        os.add_dll_directory(str(_PKG_DIR))
    except (OSError, FileNotFoundError):
        pass

# -----------------------------------------------------------------
# Importa a extensao nativa (submodulo com o mesmo nome do pacote,
# ex.: dawdreamer.dawdreamer, que resolve para dawdreamer.pyd/.so)
# e reexporta tudo dela no nivel do pacote.
# -----------------------------------------------------------------
from . import dawdreamer as _native  # type: ignore

_exported = {
    name: getattr(_native, name)
    for name in dir(_native)
    if not name.startswith("_")
}
globals().update(_exported)

__all__ = sorted(_exported.keys())

# Alguns bindings tambem expoem submodulos proprios (ex.: dawdreamer.faust).
# Garante que fiquem acessiveis via `import dawdreamer.faust`, se existirem.
for _sub in ("faust",):
    if hasattr(_native, _sub):
        sys.modules[f"{__name__}.{_sub}"] = getattr(_native, _sub)
if "_sub" in dir():
    del _sub