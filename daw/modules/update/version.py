# modules/update/version.py
"""
Utilitários de parsing e comparação de versões.

Aceita tags como "v0.19.0", "0.19.0", "0.19.0-beta", "1.2" etc.
Compara apenas os 3 primeiros números (major, minor, patch) — sufixos
como "-beta"/"alpha" são ignorados na comparação (mas exibidos ao
usuário como texto).
"""
from __future__ import annotations

import re

VersionTuple = tuple


def parse_version(text: str) -> VersionTuple:
    """Extrai (major, minor, patch) de uma string de versão qualquer."""
    if not text:
        return (0, 0, 0)

    text = text.strip()
    if text[:1] in ("v", "V"):
        text = text[1:]

    numbers = re.findall(r"\d+", text)
    numbers = [int(n) for n in numbers[:3]]
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def format_version(v: VersionTuple) -> str:
    return ".".join(str(n) for n in v[:3])


def is_newer(remote_text: str, local_version) -> bool:
    """True se a versão remota (string de tag) for maior que a local
    (tupla vinda de bl_info['version'], ex.: (0, 18, 1, 'beta'))."""
    remote = parse_version(remote_text)
    local = tuple(int(n) for n in list(local_version)[:3] if isinstance(n, int))
    while len(local) < 3:
        local = local + (0,)
    return remote > local