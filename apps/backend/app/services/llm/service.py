"""LLM service facade.

``LLMService`` is the single entry point graph nodes use to talk to a model.
It centralizes everything that used to be duplicated at ~6 call sites:

* model construction (delegated to :class:`LLMFactory`)
* async invocation
* response text extraction
* Markdown code-fence removal
* JSON parsing and shape validation
* logging and graceful fallback

On any failure the service returns ``None`` so callers can keep their existing
deterministic fallbacks. Fallback behavior is therefore preserved, not removed.
"""
import json
import logging
from typing import Any, Optional

from app.core.singleton import Singleton
from app.services.llm.factory import LLMFactory

logger = logging.getLogger("llm-service")


def extract_text(response: Any) -> str:
    """Extract a plain string from a LangChain message/response.

    Some models return ``content`` as a list of content blocks; those are
    flattened into a single string.
    """
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        content = "".join(parts)
    return str(content).strip()


def strip_markdown_fences(text: str) -> str:
    """Remove a surrounding ```/```json code fence, if present."""
    if not text:
        return text
    stripped = text.strip()
    if stripped.startswith("```"):
        # Drop the opening fence line (``` or ```json).
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rsplit("```", 1)[0]
        stripped = stripped.strip()
    return stripped


class LLMService(Singleton):
    """Facade over the configured LLM provider."""

    def __init__(self) -> None:
        # Indirection allows tests to inject a stub without touching the network.
        self._model_factory = LLMFactory.get

    # -------- test seams --------

    def set_model_factory(self, factory) -> None:
        """Override how models are obtained (primarily for testing)."""
        self._model_factory = factory

    def reset_model_factory(self) -> None:
        self._model_factory = LLMFactory.get

    def _get_model(self, provider: Optional[str], temperature: Optional[float]):
        return self._model_factory(provider=provider, temperature=temperature)

    # -------- public API --------

    async def invoke_text(
        self,
        prompt: str,
        *,
        temperature: Optional[float] = None,
        provider: Optional[str] = None,
    ) -> Optional[str]:
        """Invoke the model and return the raw text response (or ``None``)."""
        model = self._get_model(provider, temperature)
        try:
            response = await model.ainvoke(prompt)
        except Exception as err:  # noqa: BLE001 - callers rely on graceful fallback
            logger.warning("[LLMService] invoke_text failed: %s", err)
            return None
        return extract_text(response)

    async def invoke_json(
        self,
        prompt: str,
        expect: str = "object",
        *,
        temperature: Optional[float] = None,
        provider: Optional[str] = None,
    ) -> Optional[Any]:
        """Invoke the model and parse a JSON ``object`` or ``array`` from it.

        Args:
            prompt: the fully-rendered prompt to send.
            expect: ``"object"`` (dict) or ``"array"`` (list); other values skip
                shape validation.

        Returns:
            The parsed value, or ``None`` on any failure (so callers fall back).
        """
        model = self._get_model(provider, temperature)
        try:
            response = await model.ainvoke(prompt)
        except Exception as err:  # noqa: BLE001 - callers rely on graceful fallback
            logger.warning("[LLMService] invoke_json invocation failed: %s", err)
            return None

        raw = extract_text(response)
        cleaned = strip_markdown_fences(raw)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as err:
            logger.warning(
                "[LLMService] invalid JSON response: %s. Raw: %s", err, raw[:300]
            )
            return None

        if expect == "object" and not isinstance(data, dict):
            logger.warning("[LLMService] expected a JSON object, got %s", type(data).__name__)
            return None
        if expect == "array" and not isinstance(data, list):
            logger.warning("[LLMService] expected a JSON array, got %s", type(data).__name__)
            return None

        return data


# Process-wide facade instance used by the pipeline nodes.
llm_service = LLMService()
