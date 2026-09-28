"""LLM service package: provider abstraction, registry, factory and facade."""
from app.services.llm.base import (
    LLMProvider,
    available_providers,
    get_provider_class,
    register_provider,
)
from app.services.llm.factory import LLMFactory
from app.services.llm.service import LLMService, llm_service

# Importing providers triggers their ``@register_provider`` decorators.
from app.services.llm import providers as _providers  # noqa: F401,E402

__all__ = [
    "LLMProvider",
    "register_provider",
    "get_provider_class",
    "available_providers",
    "LLMFactory",
    "LLMService",
    "llm_service",
]
