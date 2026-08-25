# modules/playlist/utils.py
"""
Utilitários do módulo Playlist -- índices, nomes únicos, formatação de
tempo/compasso pra exibição na UI.

CORREÇÃO: este arquivo continha, por engano, uma cópia do conteúdo de
`selection.py` (mesmo cabeçalho "# modules/playlist/selection.py",
mesmas funções `select_all`/`deselect_all`/etc., que já existem
corretamente no arquivo `selection.py` de verdade). Não tinha nenhuma
das funções que `operators.py` e `ui.py` já importavam
(`from .utils import clamp_index, unique_clip_name, format_beat` e
`from .utils import format_beat, format_time`), causando
`ImportError: cannot import name 'clamp_index' from
'daw.modules.playlist.utils'` e derrubando o módulo playlist inteiro.
"""
from __future__ import annotations

from typing import Iterable


def clamp_index(index: int, length: int) -> int:
    """Restringe um índice ao range válido [0, length-1]. Retorna 0 se length <= 0."""
    if length <= 0:
        return 0
    return max(0, min(index, length - 1))


def unique_clip_name(existing_names: Iterable[str], base_name: str) -> str:
    """Garante que `base_name` seja único entre os nomes já existentes,
    no mesmo padrão usado pelo mixer (`mixer/utils.py::unique_track_name`):
    'Nome', 'Nome (2)', 'Nome (3)', ..."""
    existing = set(existing_names)
    if base_name not in existing:
        return base_name
    n = 2
    while f"{base_name} ({n})" in existing:
        n += 1
    return f"{base_name} ({n})"


def format_beat(beat: float, beats_per_bar: int = 4) -> str:
    """Formata uma posição em beats como 'compasso.beat', ex.: beat=6.5
    com beats_per_bar=4 -> '2.2.50' (compasso 2, beat 2.50 dentro dele).
    Compassos e beats são exibidos a partir de 1 (convenção musical),
    não de 0."""
    beats_per_bar = max(1, beats_per_bar)
    bar = int(beat // beats_per_bar) + 1
    beat_in_bar = (beat % beats_per_bar) + 1
    return f"{bar}.{beat_in_bar:.2f}"


def format_time(beat: float, bpm: float) -> str:
    """Converte uma posição em beats + BPM pro tempo real decorrido,
    formatado como 'MM:SS.mmm'."""
    bpm = max(1.0, bpm)
    seconds = beat * 60.0 / bpm
    minutes = int(seconds // 60)
    secs = seconds - minutes * 60
    return f"{minutes:02d}:{secs:06.3f}"