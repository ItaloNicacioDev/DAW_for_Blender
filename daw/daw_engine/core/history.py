# core/history.py
"""
Facade de histórico de ações (desfazer/refazer) sobre o CommandManager.

Correção vs versão anterior:
- clear() acessava atributos privados (_undo_stack/_redo_stack) do
  CommandManager diretamente — quebra de encapsulamento. Agora usa
  o método público CommandManager.clear() que já existe.
- push() não retornava o status de execução — agora propaga.
- Adicionado can_undo/can_redo/undo_label/redo_label como passthrough,
  já que a UI (panels.py) deve consultar History e não CommandManager
  diretamente.
"""
from __future__ import annotations

from typing import Optional

from .commands import Command, CommandManager
from .constants import CommandStatus


class History:
    """
    Facade simplificada para CommandManager.

    Mantém max_undo configurável e expõe só o necessário para a Engine
    e para a UI, sem vazar a implementação interna (pilhas).
    """

    def __init__(self, max_undo: int = 50) -> None:
        self._cmd_manager = CommandManager(max_history=max_undo)

    # ------------------------------------------------------------------
    # Operações
    # ------------------------------------------------------------------

    def push(self, command: Command) -> CommandStatus:
        """Executa e registra um comando no histórico."""
        return self._cmd_manager.execute(command)

    def undo(self) -> CommandStatus:
        return self._cmd_manager.undo()

    def redo(self) -> CommandStatus:
        return self._cmd_manager.redo()

    def clear(self) -> None:
        """Limpa todo o histórico (chamar ao trocar de projeto)."""
        self._cmd_manager.clear()

    # ------------------------------------------------------------------
    # Consulta de estado (para UI habilitar/desabilitar botões)
    # ------------------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        return self._cmd_manager.can_undo

    @property
    def can_redo(self) -> bool:
        return self._cmd_manager.can_redo

    @property
    def undo_label(self) -> Optional[str]:
        return self._cmd_manager.undo_label

    @property
    def redo_label(self) -> Optional[str]:
        return self._cmd_manager.redo_label

    def __repr__(self) -> str:
        return f"History({self._cmd_manager!r})"