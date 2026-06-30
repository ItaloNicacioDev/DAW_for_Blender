# core/commands.py
"""
Sistema de comandos (padrão Command) para desfazer/refazer.

Correção vs versão anterior:
- execute() não tinha tratamento de erro: se command.execute() lançasse
  exceção, o comando ainda era empilhado no undo_stack (bug — um comando
  que falhou não deveria poder ser desfeito). Agora só empilha em caso
  de sucesso.
- Faltava CommandStatus (já existe em constants.py mas não era usado).
- Adicionado limite de tamanho da pilha de undo (evita crescimento
  infinito de memória em sessões longas).
- Adicionado can_undo / can_redo para a UI habilitar/desabilitar botões.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from .constants import CommandStatus


class Command(ABC):
    """
    Comando executável e reversível.

    Subclasses devem implementar execute() e undo() de forma que
    undo() desfaça exatamente o efeito de execute().
    """

    #: Nome legível exibido em menus "Desfazer X" / "Refazer X"
    label: str = "Comando"

    @abstractmethod
    def execute(self) -> None:
        ...

    @abstractmethod
    def undo(self) -> None:
        ...

    def __repr__(self) -> str:
        return f"<Command: {self.label}>"


class CommandManager:
    """
    Gerencia a pilha de comandos para histórico de undo/redo.

    Garantias:
    - Um comando só entra na pilha de undo se execute() não lançar exceção.
    - redo_stack é limpo sempre que um novo comando é executado
      (comportamento padrão de qualquer editor: não dá pra "redo"
      depois de uma ação nova).
    """

    def __init__(self, max_history: int = 100) -> None:
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self._max_history = max_history

    # ------------------------------------------------------------------
    # Execução
    # ------------------------------------------------------------------

    def execute(self, command: Command) -> CommandStatus:
        """
        Executa o comando. Só empilha para undo se não houver exceção.
        Retorna o status da execução.
        """
        try:
            command.execute()
        except Exception as e:
            from .logger import LOGGER
            LOGGER.error("CommandManager", f"Falha ao executar '{command.label}': {e}")
            return CommandStatus.FAILED

        self._undo_stack.append(command)
        self._redo_stack.clear()

        # Limita o tamanho da pilha para não crescer infinitamente
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)

        return CommandStatus.SUCCESS

    def undo(self) -> CommandStatus:
        if not self._undo_stack:
            return CommandStatus.CANCELLED

        cmd = self._undo_stack.pop()
        try:
            cmd.undo()
        except Exception as e:
            from .logger import LOGGER
            LOGGER.error("CommandManager", f"Falha ao desfazer '{cmd.label}': {e}")
            # Não devolve à pilha de undo — o estado pode estar inconsistente,
            # melhor não permitir redo de algo que falhou ao desfazer.
            return CommandStatus.FAILED

        self._redo_stack.append(cmd)
        return CommandStatus.SUCCESS

    def redo(self) -> CommandStatus:
        if not self._redo_stack:
            return CommandStatus.CANCELLED

        cmd = self._redo_stack.pop()
        try:
            cmd.execute()
        except Exception as e:
            from .logger import LOGGER
            LOGGER.error("CommandManager", f"Falha ao refazer '{cmd.label}': {e}")
            return CommandStatus.FAILED

        self._undo_stack.append(cmd)
        return CommandStatus.SUCCESS

    # ------------------------------------------------------------------
    # Consulta de estado (para UI)
    # ------------------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    @property
    def undo_label(self) -> Optional[str]:
        return self._undo_stack[-1].label if self._undo_stack else None

    @property
    def redo_label(self) -> Optional[str]:
        return self._redo_stack[-1].label if self._redo_stack else None

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    def __repr__(self) -> str:
        return f"CommandManager(undo={len(self._undo_stack)}, redo={len(self._redo_stack)})"