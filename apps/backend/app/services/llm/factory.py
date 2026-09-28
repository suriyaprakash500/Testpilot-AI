"""LLM factory — resolves the configured provider from the registry.

Provider resolution chain::

    configuration -> provider registry -> provider implementation -> chat model

Model/client instances are cached per ``(provider, temperature)`` so graph
nodes reuse a single client instead of reconstructing one on every invocation.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings
from app.services.llm.base import available_providers, get_provider_class

logger = logging.getLogger("llm-factory")


class LLMFactory:
    """Creates (and caches) LangChain chat models for the configured provider."""

    _cache: Dict[Tuple[str, float], Any] = {}

    @classmethod
    def _resolve_provider_name(cls, provider: Optional[str]) -> str:
        name = (provider or settings.llm_provider or "openrouter").strip().lower()
        if get_provider_class(name) is None:
            fallback = (settings.llm_provider or "openrouter").strip().lower()
            logger.warning(
                "Unknown LLM provider '%s'. Falling back to '%s'. Available: %s",
                name,
                fallback,
                available_providers(),
            )
            name = fallback
        return name

    @classmethod
    def get(cls, provider: Optional[str] = None, temperature: Optional[float] = None) -> Any:
        """Return a LangChain chat model for the resolved provider.

        Args:
            provider: optional provider override; defaults to ``settings.llm_provider``.
            temperature: optional temperature override; defaults to ``settings.llm_temperature``.
        """
        name = cls._resolve_provider_name(provider)
        temp = settings.llm_temperature if temperature is None else temperature

        provider_cls = get_provider_class(name)
        if provider_cls is None:
            # Should be unreachable given _resolve_provider_name, but guard anyway.
            raise ValueError(
                f"No LLM provider registered for '{name}'. Available: {available_providers()}"
            )

        cache_key = (name, float(temp))
        if cache_key not in cls._cache:
            logger.info("Building LLM provider '%s' (temperature=%s)", name, temp)
            cls._cache[cache_key] = provider_cls().build(temperature=temp)
        return cls._cache[cache_key]

    @classmethod
    def clear_cache(cls) -> None:
        """Drop cached models. Useful for tests and configuration reloads."""
        cls._cache.clear()
