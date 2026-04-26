"""
telemetry.py
============
Logging setup for the Clarity Bot.
- Rotating file log (5 MB × 3 backups) + stdout stream.
- Timed context manager for measuring pipeline stages.
- Quiet noisy third-party libraries.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
import time
from contextlib import contextmanager
from typing import Generator

import config


def setup() -> None:
    fmt      = "%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=date_fmt)

    file_handler = logging.handlers.RotatingFileHandler(
        config.LOG_PATH,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    stream_handler = logging.StreamHandler(sys.stdout)

    for handler in (file_handler, stream_handler):
        handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    # Suppress noisy third-party loggers
    for name in ("httpx", "httpcore", "urllib3", "telegram.vendor", "telegram.ext.updater"):
        logging.getLogger(name).setLevel(logging.WARNING)


@contextmanager
def timed(log: logging.Logger, label: str) -> Generator[None, None, None]:
    """Logs duration of the wrapped block."""
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - start
        log.info("%s | duration=%.1fs", label, elapsed)
