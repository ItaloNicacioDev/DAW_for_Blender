# core/state.py
"""
Estado global de UI/edição da DAW (seleção, modo, cursor).

Correção vs versão anterior:
- select_track() permitia duplicatas na lista — agora verifica antes.
- Não havia deselect_track() individual, nem select_clip()/deselect_clip().
- Faltava reset() para usar no Engine.new_project()/open_project().
- Singleton via __new__ reatribuía os atributos toda vez que era chamado
  (bug sutil: __init__ do Python roda de novo mesmo em singleton, mas como
  os atributos eram setados dentro do if cls._instance is None, estava
  correto — documentado aqui para deixar claro que é intencional).
"""
from __future__ import annotations

from typing import Any, List, Optional


class State:
    """
    Mantém variáveis de estado de edição/UI: modo atual, seleção, cursor, loop.

    Singleton — sempre retorna a mesma instância.
    NÃO confundir com Session (que guarda o projeto) nem com EngineState
    (que é o estado de transporte da Engine).
    """

    _instance: Optional["State"] = None

    def __new__(cls) -> "State":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst.mode: str = "object"          # "object", "edit", "paint", etc.
            inst.selected_tracks: List[Any] = []
            inst.selected_clips:  List[Any] = []
            inst.cursor_position: float = 0.0  # em segundos
            inst.loop_start: float = 0.0
            inst.loop_end:   float = 4.0
            cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Modo de edição
    # ------------------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    # ------------------------------------------------------------------
    # Seleção de faixas
    # ------------------------------------------------------------------

    def select_track(self, track: Any, exclusive: bool = False) -> None:
        """
        Adiciona uma faixa à seleção.
        Se exclusive=True, limpa a seleção anterior antes (clique simples,
        sem Shift/Ctrl).
        """
        if exclusive:
            self.selected_tracks.clear()
        if track not in self.selected_tracks:
            self.selected_tracks.append(track)

    def deselect_track(self, track: Any) -> None:
        if track in self.selected_tracks:
            self.selected_tracks.remove(track)

    def is_track_selected(self, track: Any) -> bool:
        return track in self.selected_tracks

    # ------------------------------------------------------------------
    # Seleção de clips
    # ------------------------------------------------------------------

    def select_clip(self, clip: Any, exclusive: bool = False) -> None:
        if exclusive:
            self.selected_clips.clear()
        if clip not in self.selected_clips:
            self.selected_clips.append(clip)

    def deselect_clip(self, clip: Any) -> None:
        if clip in self.selected_clips:
            self.selected_clips.remove(clip)

    def is_clip_selected(self, clip: Any) -> bool:
        return clip in self.selected_clips

    # ------------------------------------------------------------------
    # Geral
    # ------------------------------------------------------------------

    def deselect_all(self) -> None:
        """Limpa toda a seleção (faixas e clips)."""
        self.selected_tracks.clear()
        self.selected_clips.clear()

    def reset(self) -> None:
        """
        Reseta o estado de edição para os valores padrão.
        Chamar ao criar/abrir um novo projeto para não carregar seleção
        de um projeto anterior.
        """
        self.mode = "object"
        self.selected_tracks.clear()
        self.selected_clips.clear()
        self.cursor_position = 0.0
        self.loop_start = 0.0
        self.loop_end = 4.0

    def __repr__(self) -> str:
        return (
            f"State(mode='{self.mode}', "
            f"tracks_selected={len(self.selected_tracks)}, "
            f"clips_selected={len(self.selected_clips)}, "
            f"cursor={self.cursor_position:.2f}s)"
        )