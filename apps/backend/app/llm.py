"""Central LLM client factory for all pipeline nodes.

Providers (settings.llm_provider):
- "openrouter" (default): https://openrouter.ai/api/v1 — e.g. stealth/ox-alpha
- "groq": api.groq.com — e.g. openai/gpt-oss-120b
"""
from app.services.llm import LLMFactory, LLMService, llm_service
from app.services.llm.providers import OPENROUTER_BASE_URL


def get_llm(temperature: float = 0.2):
    """Returns a LangChain chat model for the configured provider."""
    return LLMFactory.get(temperature=temperature)


__all__ = [
    "get_llm",
    "LLMFactory",
    "LLMService",
    "llm_service",
    "OPENROUTER_BASE_URL",
]
