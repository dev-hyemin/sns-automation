import logging
import sys
from datetime import datetime

_loggers: dict = {}


def setup_logger(name: str = "sns-automation", level: int = logging.INFO) -> logging.Logger:
    """Configure and return a logger with console output."""
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] %(levelname)-8s %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.propagate = False
    _loggers[name] = logger
    return logger


def get_logger(name: str = "sns-automation") -> logging.Logger:
    """Return an existing logger or create a new one."""
    return _loggers.get(name, setup_logger(name))
