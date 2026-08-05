# modules/update/config.py
"""
Configuração do sistema de auto-atualização da DAW.

>>> EDITE AS DUAS CONSTANTES ABAIXO com o dono/nome do repositório
    do GitHub onde os releases da DAW são publicados. <<<

Como funciona a busca da versão mais nova:
    O updater consulta a API pública do GitHub:
        GET https://api.github.com/repos/{OWNER}/{REPO}/releases/latest

    Isso retorna o *último release publicado* do repositório (não
    "pre-release", não "draft"). Portanto, para disponibilizar uma
    atualização para os usuários, basta publicar um novo Release no
    GitHub com uma tag de versão (ex.: "v0.19.0").

Sobre o pacote .zip do release:
    - Se o Release tiver um arquivo .zip anexado como "Asset", o updater
      baixa esse arquivo diretamente (recomendado — mais rápido e permite
      excluir arquivos de desenvolvimento do pacote final).
    - Se não houver nenhum asset .zip, o updater cai automaticamente para
      o "Source code (zip)" que o GitHub gera sozinho para todo release
      (zipball_url) — funciona sem nenhuma configuração extra, mas inclui
      todo o conteúdo do repositório (README, .gitignore, etc).

    Em ambos os casos, o instalador procura recursivamente dentro do
    .zip pela pasta que contém o `__init__.py` com `bl_info` (ou seja,
    a pasta "daw/"), então não importa como o .zip está organizado por
    dentro.
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────
#  EDITE AQUI
# ─────────────────────────────────────────────────────────────────
GITHUB_OWNER = "ItaloNicacioDev"     # usuário/organização do GitHub
GITHUB_REPO = "Daw_for_Blender"      # nome do repositório

# ─────────────────────────────────────────────────────────────────
#  Parâmetros gerais (normalmente não precisam mudar)
# ─────────────────────────────────────────────────────────────────

# Intervalo mínimo entre verificações automáticas ao abrir o Blender.
CHECK_INTERVAL_HOURS = 24

# Timeout (segundos) para requisições HTTP à API do GitHub.
REQUEST_TIMEOUT = 10

# Timeout (segundos) para o download do pacote .zip da atualização.
DOWNLOAD_TIMEOUT = 60

# User-Agent enviado nas requisições (a API do GitHub exige um).
USER_AGENT = "DAW-for-Blender-Update"

# Nome do arquivo de cache (fica em Blender > user config dir).
CACHE_FILENAME = "daw_update_cache.json"


def api_latest_release_url() -> str:
    """Endpoint oficial "latest" — só retorna release publicado que NÃO
    seja draft nem pre-release. Enquanto o projeto estiver em beta (só
    pre-releases publicados), este endpoint responde 404; ver
    `api_releases_list_url()` como fallback."""
    return f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def api_releases_list_url() -> str:
    """Lista todos os releases (inclui pre-release), do mais recente para
    o mais antigo. Usado como fallback quando `api_latest_release_url()`
    retorna 404 (nenhuma release estável publicada ainda)."""
    return f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"


def releases_page_url() -> str:
    return f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"


def repo_url() -> str:
    return f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"