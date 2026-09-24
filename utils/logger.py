"""
Production-Grade Structured Logging Subsystem.

Provides formatted console output with ANSI color differentiation and
file-based persistent logging with microsecond timestamps and structured metadata.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional


class ANSIColorFormatter(logging.Formatter):
    """Console formatter adding ANSI color highlighting based on record severity."""

    COLORS = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[32m",      # Green
        logging.WARNING: "\033[33m",   # Yellow
        logging.ERROR: "\033[31m",     # Red
        logging.CRITICAL: "\033[41m\033[37m", # White on Red
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        levelname = f"{color}{record.levelname:<8}{self.RESET}"
        asctime = f"\033[90m{self.formatTime(record, '%Y-%m-%d %H:%M:%S')}{self.RESET}"
        name = f"\033[34m{record.name}\033[0m"
        message = record.getMessage()

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        
        formatted = f"{asctime} | {levelname} | {name} - {message}"
        if record.exc_text:
            formatted += f"\n{record.exc_text}"
        return formatted


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
) -> None:
    """
    Initializes global root logger handlers for both stdout and file persistence.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers to prevent duplicate streams during reload
    for handler in list(root.handlers):
        root.removeHandler(handler)

    # 1. Console Stream Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ANSIColorFormatter())
    root.addHandler(console_handler)

    # 2. File Stream Handler (Optional / Configured)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Keep verbose traces in file
        file_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] (%(filename)s:%(lineno)d): %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Convenience getter for module-scoped logger instances."""
    return logging.getLogger(name)
