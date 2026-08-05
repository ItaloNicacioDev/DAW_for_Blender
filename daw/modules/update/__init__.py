# modules/update/__init__.py
"""
Módulo de auto-atualização da DAW (checagem/download/instalação de
novos releases via GitHub Releases).

Arquivos:
    config.py      — GITHUB_OWNER/GITHUB_REPO e parâmetros gerais
    github_api.py  — cliente mínimo da API pública do GitHub
    version.py     — comparação de versões (bl_info x tag do release)
    downloader.py  — download do .zip do release
    installer.py   — extração/instalação do .zip sobre o addon atual
    jobs.py         — orquestra checagem automática (throttle, startup)
    properties.py  — estado exposto em bpy.types.WindowManager.daw_updater
    operators.py   — Operators (checar, baixar+instalar, reiniciar, abrir releases)
    ui.py          — painéis reutilizáveis (compacto/completo), usados por
                      modules/settings/preferences.py e modules/settings/ui.py
    register.py    — register()/unregister() (o que este __init__ expõe)
"""
from __future__ import annotations

from .register import register, unregister

__all__ = ["register", "unregister"]