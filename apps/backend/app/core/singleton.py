"""Shared singleton infrastructure.

Several long-lived collaborators (settings-backed stores, the database
repository, the LLM facade) need exactly one process-wide instance so that
their state is shared and their lifecycle is predictable.

This module provides a small, thread-safe ``Singleton`` base class. Subclasses
keep their normal ``__init__``; it runs exactly once because the first
constructed instance is cached and reused on subsequent calls.

Usage::

    class CredentialStore(Singleton):
        def __init__(self):
            self.store = {}
"""
import threading
from typing import Any, Optional


class _SingletonMeta(type):
    """Metaclass guaranteeing one instance per class.

    Crucially, ``__init__`` runs **exactly once**: re-instantiating the class
    returns the already-initialised cached object without re-running its
    ``__init__`` (which is what makes singleton *state* actually persist).
    """

    def __call__(cls, *args: Any, **kwargs: Any):
        instance = cls.__dict__.get("_instance")
        if instance is None:
            with cls._singleton_lock:
                instance = cls.__dict__.get("_instance")
                if instance is None:
                    instance = super().__call__(*args, **kwargs)
                    cls._instance = instance
        return instance


class Singleton(metaclass=_SingletonMeta):
    """Thread-safe, per-subclass singleton base class.

    The cached instance is stored on the *subclass* (``cls._instance``), so
    different subclasses do not share state even though they inherit from the
    same base. Subclasses keep a normal ``__init__``; it runs exactly once.
    """

    _instance: Optional["Singleton"] = None
    _singleton_lock = threading.Lock()

    @classmethod
    def reset_instance(cls) -> None:
        """Drop the cached instance. Primarily useful for test isolation."""
        with cls._singleton_lock:
            cls._instance = None
