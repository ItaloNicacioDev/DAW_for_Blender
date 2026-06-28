# core/history.py
"""Histórico de ações (desfazer/refazer) com persistência."""
from .commands import CommandManager

class History:
    """Facade para CommandManager."""
    def __init__(self):
        self._cmd_manager = CommandManager()
        self._max_undo = 50

    def push(self, command):
        self._cmd_manager.execute(command)

    def undo(self):
        self._cmd_manager.undo()

    def redo(self):
        self._cmd_manager.redo()

    def clear(self):
        self._cmd_manager._undo_stack.clear()
        self._cmd_manager._redo_stack.clear()