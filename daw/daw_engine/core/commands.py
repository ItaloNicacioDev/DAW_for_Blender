# core/commands.py
"""Sistema de comandos (padrão Command) para desfazer/refazer."""
from abc import ABC, abstractmethod

class Command(ABC):
    """Comando executável e reversível."""
    @abstractmethod
    def execute(self):
        pass

    @abstractmethod
    def undo(self):
        pass

class CommandManager:
    """Gerencia pilha de comandos para histórico."""
    def __init__(self):
        self._undo_stack = []
        self._redo_stack = []

    def execute(self, command: Command):
        command.execute()
        self._undo_stack.append(command)
        self._redo_stack.clear()

    def undo(self):
        if self._undo_stack:
            cmd = self._undo_stack.pop()
            cmd.undo()
            self._redo_stack.append(cmd)

    def redo(self):
        if self._redo_stack:
            cmd = self._redo_stack.pop()
            cmd.execute()
            self._undo_stack.append(cmd)