import os
import logging
from logging.handlers import RotatingFileHandler
from config import LOGGING_LEVEL, LOGGING_LEVEL_FILE  # Adjust import as needed

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

class _ColorFormatter(logging.Formatter):
    """ANSI color wrapper for console output."""
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


def setup_logging(logger_name: str = "cobot_backend") -> logging.Logger:
    """Configure logger for backend: rotating file + colored console."""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    logger.propagate = False

    console_level = getattr(logging, LOGGING_LEVEL.upper(), logging.INFO)
    file_level = getattr(logging, LOGGING_LEVEL_FILE.upper(), logging.DEBUG)

    logger.setLevel(min(console_level, file_level))

    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # File handler
    fh = RotatingFileHandler(
        os.path.join(LOG_DIR, f"{logger_name}.log"),
        maxBytes=500_000,
        backupCount=3,
        encoding="utf-8"
    )
    fh.setLevel(file_level)
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logger.addHandler(fh)

    # Console handler (colored)
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(_ColorFormatter(fmt, datefmt=datefmt))
    logger.addHandler(ch)

    return logger
