"""Logging configurado vía rich. Llamar setup_logging() una sola vez en el arranque."""

from __future__ import annotations

import logging
import os
from logging import Logger

from rich.logging import RichHandler

_INITIALIZED = False


def setup_logging(level: str | None = None) -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    lvl = (level or os.environ.get("SPA_LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=lvl,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_time=True, show_path=False)],
    )
    # Silenciar ruidosos
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _INITIALIZED = True


def get_logger(name: str) -> Logger:
    if not _INITIALIZED:
        setup_logging()
    return logging.getLogger(name)
