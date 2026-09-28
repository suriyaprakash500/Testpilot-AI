"""Tests for the LLM provider registry and factory.

These tests never hit the network: they assert that the registry resolves the
known providers, that an unknown provider name falls back to the configured
one, and that ``LLMFactory`` caches models per ``(provider, temperature)``.
"""
import pytest

from app.core.config import settings
from app.services.llm.base import (
    _PROVIDER_REGISTRY,
    LLMProvider,
    available_providers,
    get_provider_class,
)
from app.services.llm.base import register_provider
from app.services.llm.factory import LLMFactory


def test_registry_resolves_known_providers():
    for name in ("openrouter", "groq", "bedrock"):
        cls = get_provider_class(name)
        assert cls is not None, f"provider {name!r} is not registered"
        assert issubclass(cls, LLMProvider)
        assert cls.name == name


def test_available_providers_contains_known_providers():
    assert set(available_providers()) >= {"openrouter", "groq", "bedrock"}


def test_get_provider_class_is_case_insensitive():
    assert get_provider_class("OpenRouter") is get_provider_class("openrouter")
    assert get_provider_class("") is None
    assert get_provider_class("does-not-exist") is None


def test_unknown_provider_falls_back_to_configured(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openrouter", raising=False)
    # An unknown explicit provider falls back to the configured one.
    assert LLMFactory._resolve_provider_name("totally-bogus") == "openrouter"
    # A missing provider also resolves to the configured one.
    assert LLMFactory._resolve_provider_name(None) == "openrouter"


class _FakeProvider(LLMProvider):
    """A provider that records how many times ``build`` was called."""

    build_calls = 0

    def build(self, temperature: float = 0.2):
        type(self).build_calls += 1
        return {"provider": self.name, "temperature": temperature}


def test_factory_caches_per_provider_and_temperature():
    register_provider("fake-provider")(_FakeProvider)
    try:
        LLMFactory.clear_cache()
        _FakeProvider.build_calls = 0

        first = LLMFactory.get(provider="fake-provider", temperature=0.2)
        second = LLMFactory.get(provider="fake-provider", temperature=0.2)

        # Same provider + temperature -> the cached instance is reused.
        assert first is second
        assert _FakeProvider.build_calls == 1

        # A different temperature produces a distinct cached model.
        third = LLMFactory.get(provider="fake-provider", temperature=0.7)
        assert third is not first
        assert _FakeProvider.build_calls == 2
        assert third["temperature"] == 0.7
    finally:
        LLMFactory.clear_cache()
        _PROVIDER_REGISTRY.pop("fake-provider", None)


def test_factory_clear_cache_forces_rebuild():
    register_provider("fake-provider-2")(_FakeProvider)
    try:
        LLMFactory.clear_cache()
        _FakeProvider.build_calls = 0
        a = LLMFactory.get(provider="fake-provider-2", temperature=0.2)
        LLMFactory.clear_cache()
        b = LLMFactory.get(provider="fake-provider-2", temperature=0.2)
        assert a is not b
        assert _FakeProvider.build_calls == 2
    finally:
        LLMFactory.clear_cache()
        _PROVIDER_REGISTRY.pop("fake-provider-2", None)
