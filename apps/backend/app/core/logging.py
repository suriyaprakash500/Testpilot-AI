"""Centralized logging configuration.

Call :func:`configure_logging` once at application startup (see ``app/main.py``).
Use :func:`get_logger` for module loggers so log levels stay consistent.
"""
import logging
from typing import Optional

from app.core.config import settings

_CONFIGURED = False


def configure_logging(level: Optional[str] = None) -> None:
    """Configure the root logger exactly once (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved_level = (level or settings.log_level or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, resolved_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (kept tiny so call sites stay uniform)."""
    return logging.getLogger(name)
