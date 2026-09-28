"""Backward-compatible shim.

The canonical configuration now lives in :mod:`app.core.config`. This module
re-exports it so existing imports (``from app.config import settings``) keep
working unchanged during and after the refactor.
"""
from app.core.config import Settings, settings

__all__ = ["Settings", "settings"]
