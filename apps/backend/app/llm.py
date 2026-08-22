"""Central LLM client factory for all pipeline nodes.

Providers (settings.llm_provider):
- "openrouter" (default): https://openrouter.ai/api/v1 — e.g. stealth/ox-alpha
- "groq": api.groq.com — e.g. openai/gpt-oss-120b
"""
import logging

from app.config import settings

logger = logging.getLogger("llm-factory")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_llm(temperature: float = 0.2):
    """Returns a LangChain chat model for the configured provider."""
    provider = (settings.llm_provider or "groq").strip().lower()

    if provider == "openrouter":
        from langchain_openai import ChatOpenAI

        if not settings.openrouter_api_key:
            logger.warning("[LLM] openrouter_api_key is empty — LLM calls will fail")

        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
            temperature=temperature,
            max_retries=2,
            default_headers={
                "HTTP-Referer": settings.frontend_url,
                "X-Title": "TestPilot AI",
            },
        )

    # Default: Groq
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=temperature,
    )
