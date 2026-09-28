"""Concrete LLM provider strategies.

Each provider preserves the behavior of the original ``app/llm.py``
implementation for OpenRouter and Groq, and adds Bedrock support. Third-party
integrations are imported lazily inside :meth:`build` so that merely importing
this module never requires the optional SDK to be installed.
"""
import logging

from app.core.config import settings
from app.services.llm.base import LLMProvider, register_provider

logger = logging.getLogger("llm-providers")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _optional_model_kwargs() -> dict:
    """Shared optional kwargs.

    ``LLM_TIMEOUT_S`` / ``LLM_MAX_TOKENS`` of ``0`` (or unset) mean "defer to
    the library default", which preserves the original behavior.
    """
    kwargs: dict = {}
    if settings.llm_timeout_s:
        kwargs["timeout"] = settings.llm_timeout_s
    if settings.llm_max_tokens:
        kwargs["max_tokens"] = settings.llm_max_tokens
    return kwargs


@register_provider("openrouter")
class OpenRouterProvider(LLMProvider):
    """OpenRouter via the OpenAI-compatible endpoint (existing behavior)."""

    def build(self, temperature: float = 0.2):
        from langchain_openai import ChatOpenAI

        if not settings.openrouter_api_key:
            logger.warning("[LLM] openrouter_api_key is empty — LLM calls will fail")

        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
            temperature=temperature,
            max_retries=settings.llm_max_retries,
            default_headers={
                "HTTP-Referer": settings.frontend_url,
                "X-Title": "Verity",
            },
            **_optional_model_kwargs(),
        )


@register_provider("groq")
class GroqProvider(LLMProvider):
    """Groq-hosted chat models (existing behavior)."""

    def build(self, temperature: float = 0.2):
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=temperature,
            max_retries=settings.llm_max_retries,
            **_optional_model_kwargs(),
        )


@register_provider("bedrock")
class BedrockProvider(LLMProvider):
    """AWS Bedrock via ``langchain-aws`` (``ChatBedrockConverse``).

    Authentication uses boto3's normal credential provider chain, which on EC2
    resolves through the instance IAM role. No credentials are configured here.
    """

    def build(self, temperature: float = 0.2):
        from langchain_aws import ChatBedrockConverse

        if not settings.bedrock_model_id:
            logger.warning("[LLM] bedrock_model_id is empty — Bedrock calls will fail")
        if not settings.aws_region:
            logger.warning("[LLM] aws_region is empty — boto3 will fall back to its default region")

        kwargs: dict = {
            "model": settings.bedrock_model_id,
            "temperature": temperature,
            "max_retries": settings.llm_max_retries,
        }
        if settings.aws_region:
            kwargs["region_name"] = settings.aws_region
        kwargs.update(_optional_model_kwargs())

        guardrail_config = self._guardrail_config()
        if guardrail_config:
            kwargs["guardrail_config"] = guardrail_config

        return ChatBedrockConverse(**kwargs)

    @staticmethod
    def _guardrail_config() -> dict:
        """Build optional guardrail configuration when both id and version are set."""
        if settings.bedrock_guardrail_id and settings.bedrock_guardrail_version:
            return {
                "guardrailIdentifier": settings.bedrock_guardrail_id,
                "guardrailVersion": settings.bedrock_guardrail_version,
            }
        return {}
