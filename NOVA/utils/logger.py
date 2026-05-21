"""
utils/logger.py — Coloured console logging for all NOVA modules.

Usage:
  from utils.logger import get_logger
  logger = get_logger("my_module")
  logger.info("message")
"""

import logging
import sys

# ANSI colour codes per log level
COLORS = {
    "DEBUG":   "\033[36m",
    "INFO":    "\033[32m",
    "WARNING": "\033[33m",
    "ERROR":   "\033[31m",
    "RESET":   "\033[0m",
}


class ColorFormatter(logging.Formatter):
    """Apply terminal colours to log level and message text."""

    def format(self, record):
        color = COLORS.get(record.levelname, COLORS["RESET"])
        record.levelname = f"{color}{record.levelname}{COLORS['RESET']}"
        record.msg = f"{color}{record.msg}{COLORS['RESET']}"
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger named NOVA.<name>.
    Handlers are attached only once per logger name.
    """
    logger = logging.getLogger(f"NOVA.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColorFormatter(
            "[%(asctime)s] %(levelname)s | %(name)s: %(message)s",
            datefmt="%H:%M:%S"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger
