"""
core/logger.py

Professional logging system for the DAW Engine.

Features
--------
- Thread-safe
- Singleton logger
- Console history
- Optional file logging
- Log listeners (UI callbacks)
- Engine statistics
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

# ==========================================================
# Log Entry
# ==========================================================

@dataclass(slots=True)
class LogEntry:

    timestamp: datetime

    level: int

    module: str

    message: str

    thread: str


# ==========================================================
# Logger
# ==========================================================

class EngineLogger:

    MAX_HISTORY = 5000

    def __init__(self):

        self._lock = threading.RLock()

        self._history = deque(maxlen=self.MAX_HISTORY)

        self._listeners: list[Callable[[LogEntry], None]] = []

        self._logger = logging.getLogger("DAWEngine")

        self._logger.setLevel(logging.DEBUG)

        self._logger.propagate = False

        self._console_handler = logging.StreamHandler()

        self._console_handler.setFormatter(

            logging.Formatter(

                "[%(levelname)s] %(message)s"

            )

        )

        self._logger.addHandler(

            self._console_handler

        )

        self._file_handler = None

        self.debug_count = 0

        self.info_count = 0

        self.warning_count = 0

        self.error_count = 0

        self.critical_count = 0

    # ======================================================

    def enable_file_logging(

        self,

        filename: str | Path,

    ):

        filename = Path(filename)

        filename.parent.mkdir(

            parents=True,

            exist_ok=True,

        )

        handler = logging.FileHandler(

            filename,

            encoding="utf-8",

        )

        handler.setFormatter(

            logging.Formatter(

                "%(asctime)s | %(levelname)s | %(message)s"

            )

        )

        self._logger.addHandler(handler)

        self._file_handler = handler

    # ======================================================

    def disable_file_logging(self):

        if self._file_handler:

            self._logger.removeHandler(

                self._file_handler

            )

            self._file_handler.close()

            self._file_handler = None

    # ======================================================

    def add_listener(

        self,

        callback: Callable[[LogEntry], None],

    ):

        self._listeners.append(callback)

    # ======================================================

    def remove_listener(

        self,

        callback,

    ):

        if callback in self._listeners:

            self._listeners.remove(callback)

    # ======================================================

    def _emit(

        self,

        level,

        module,

        message,

    ):

        with self._lock:

            entry = LogEntry(

                timestamp=datetime.now(),

                level=level,

                module=module,

                message=message,

                thread=threading.current_thread().name,

            )

            self._history.append(entry)

            if level == logging.DEBUG:

                self.debug_count += 1

            elif level == logging.INFO:

                self.info_count += 1

            elif level == logging.WARNING:

                self.warning_count += 1

            elif level == logging.ERROR:

                self.error_count += 1

            elif level == logging.CRITICAL:

                self.critical_count += 1

            self._logger.log(

                level,

                f"[{module}] {message}"

            )

            for listener in tuple(self._listeners):

                try:

                    listener(entry)

                except Exception:

                    pass

    # ======================================================

    def debug(self, module, message):

        self._emit(

            logging.DEBUG,

            module,

            message,

        )

    def info(self, module, message):

        self._emit(

            logging.INFO,

            module,

            message,

        )

    def warning(self, module, message):

        self._emit(

            logging.WARNING,

            module,

            message,

        )

    def error(self, module, message):

        self._emit(

            logging.ERROR,

            module,

            message,

        )

    def critical(self, module, message):

        self._emit(

            logging.CRITICAL,

            module,

            message,

        )

    # ======================================================

    @property

    def history(self):

        return tuple(self._history)

    # ======================================================

    def clear(self):

        with self._lock:

            self._history.clear()

            self.debug_count = 0

            self.info_count = 0

            self.warning_count = 0

            self.error_count = 0

            self.critical_count = 0

    # ======================================================

    @property

    def statistics(self):

        return {

            "debug": self.debug_count,

            "info": self.info_count,

            "warning": self.warning_count,

            "error": self.error_count,

            "critical": self.critical_count,

            "history_size": len(self._history),

        }


# ==========================================================
# Singleton
# ==========================================================

LOGGER = EngineLogger()