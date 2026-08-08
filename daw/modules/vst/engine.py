# modules/vst/engine.py
"""
Utilitarios de plugin que nao dependem de nenhum motor de audio
especifico (dawdreamer, worker IPC, etc.).

O carregamento/processamento de VST de verdade vive em
`modules/vst/ipc_engine.py` (worker externo, vendorizado junto com o
addon). Este modulo ficou só com a deteccao de formato de plugin, que
é usada tanto pelo scanner (utils.py) quanto pelo VST.load() (vst.py).
"""
from __future__ import annotations

from pathlib import Path

_VST3_EXTENSIONS = {".vst3"}
_VST2_EXTENSIONS = {".dll", ".so", ".dylib", ".vst"}


def detect_plugin_format(path: str | Path) -> str:
    """
    Detecta se um caminho é um plugin VST2 ou VST3 pela extensão.

    Retorna "VST3", "VST2" ou "UNKNOWN".

    Notas:
        - VST3 é normalmente um bundle (.vst3), que no Windows/Linux
          pode aparecer como arquivo único ou como pasta terminando em
          .vst3 (contendo Contents/<arch>/*.so|*.dll por dentro).
        - VST2 é sempre um único binário: .dll (Windows), .so (Linux,
          fora de um bundle .vst3) ou .vst (pacote .vst do macOS, que
          internamente também é um diretório, mas a extensão já entrega
          o formato).
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in _VST3_EXTENSIONS:
        return "VST3"
    if suffix in _VST2_EXTENSIONS:
        return "VST2"

    # Fallback: bundles .vst3 às vezes são passados sem checar suffix
    # diretamente (ex.: caminho apontando para dentro do bundle).
    for parent in p.parents:
        if parent.suffix.lower() == ".vst3":
            return "VST3"
        if parent.suffix.lower() == ".vst":
            return "VST2"

    return "UNKNOWN"