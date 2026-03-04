import os
import logging
from logging.handlers import RotatingFileHandler
from Frontend.config_frontend import LOGGING_LEVEL, LOGGING_LEVEL_FILE

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

class GuiHandler(logging.Handler):
    """Forward formatted log records into the Tk GUI safely via root.after.

    The GUI is expected to expose `root` (tk root) and `log(message: str, level: int)`.
    """
    def __init__(self, gui, level: int | None = None):
        # If no explicit level passed, use configured console level
        level = level if level is not None else getattr(logging, LOGGING_LEVEL.upper(), logging.INFO)
        super().__init__(level)
        self.gui = gui
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # Schedule GUI insertion on the Tk main thread and pass numeric level for coloring
            self.gui.root.after(0, lambda: self.gui.log(msg, record.levelno))
        except Exception:
            self.handleError(record)


class _ColorFormatter(logging.Formatter):
    """Minimal ANSI color wrapper for console output (no external deps)."""
    _RESET = "\x1b[0m"
    _COLORS = {
        'DEBUG': "\x1b[38;5;244m",
        'INFO': "\x1b[37m",
        'WARNING': "\x1b[33m",
        'ERROR': "\x1b[31m",
        'CRITICAL': "\x1b[1;31m",
    }

    def __init__(self, base_fmt: str, datefmt: str | None = None):
        super().__init__(base_fmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        color = self._COLORS.get(record.levelname, '')
        return f"{color}{base}{self._RESET}" if color else base


def setup_logging() -> logging.Logger:
    """Configure and return the application logger named 'cobot'.

    - Reads `config.LOGGING_LEVEL` for console/GUI level and
      `config.LOGGING_LEVEL_FILE` for file verbosity.
    - Creates a rotating file handler (DEBUG/LOGGING_LEVEL_FILE) and
      a colored console handler (LOGGING_LEVEL).
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("cobot")
    if logger.handlers:
        return logger

    logger.propagate = False

    console_level = getattr(logging, LOGGING_LEVEL.upper(), logging.INFO)
    file_level = getattr(logging, LOGGING_LEVEL_FILE.upper(), logging.DEBUG)

    # Allow handlers to filter independently: set logger to the most permissive level
    logger.setLevel(min(console_level, file_level))

    fmt = "%(asctime)s  %(levelname)-8s  %(filename)s  %(message)s"
    datefmt = "%H:%M:%S"

    # File handler (plain, verbose)
    fh = RotatingFileHandler(os.path.join(LOG_DIR, "cobot.log"), maxBytes=500_000, backupCount=3, encoding="utf-8")
    fh.setLevel(file_level)
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logger.addHandler(fh)

    # Console handler (colored)
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(_ColorFormatter(fmt, datefmt=datefmt))
    logger.addHandler(ch)

    return logger
