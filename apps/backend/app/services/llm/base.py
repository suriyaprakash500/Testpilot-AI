"""LLM provider abstraction and registry.

A *provider* is a thin strategy object whose single responsibility is to build
a LangChain chat model from configuration. Providers register themselves in a
process-wide registry via :func:`register_provider` so that adding a new
provider never requires editing an ``if/else`` chain.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type

# Registry: provider name -> provider class.
_PROVIDER_REGISTRY: Dict[str, Type["LLMProvider"]] = {}


def register_provider(name: str):
    """Class decorator that registers an :class:`LLMProvider` under ``name``."""

    def decorator(cls: Type["LLMProvider"]) -> Type["LLMProvider"]:
        key = name.strip().lower()
        cls.name = key
        _PROVIDER_REGISTRY[key] = cls
        return cls

    return decorator


def get_provider_class(name: str) -> Optional[Type["LLMProvider"]]:
    """Return the provider class registered under ``name`` (or ``None``)."""
    if not name:
        return None
    return _PROVIDER_REGISTRY.get(name.strip().lower())


def available_providers() -> List[str]:
    """Return the sorted names of all registered providers."""
    return sorted(_PROVIDER_REGISTRY)


class LLMProvider(ABC):
    """Strategy interface for constructing a LangChain chat model.

    Concrete providers know *how* their client is constructed; callers (the
    factory, the service, graph nodes) stay provider-agnostic.
    """

    name: str = ""

    @abstractmethod
    def build(self, temperature: float = 0.2):
        """Return a LangChain chat model instance.

        The returned object must expose an async ``ainvoke`` coroutine so the
        LangGraph pipeline can stay fully asynchronous.
        """
        raise NotImplementedError
