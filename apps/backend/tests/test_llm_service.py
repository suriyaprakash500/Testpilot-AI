"""Tests for the ``LLMService`` facade.

The provider is stubbed via ``set_model_factory`` so no network access is
required. Coverage: text responses, JSON objects/arrays, Markdown fence
stripping, malformed JSON, wrong shape, and invocation errors — all of which
must degrade gracefully to ``None`` so callers keep their fallbacks.
"""
import pytest

from app.services.llm.service import (
    LLMService,
    extract_text,
    strip_markdown_fences,
)


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeModel:
    """Minimal stand-in for a LangChain chat model (async ``ainvoke``)."""

    def __init__(self, content=None, error=None):
        self._content = content
        self._error = error

    async def ainvoke(self, prompt):
        if self._error is not None:
            raise self._error
        return _FakeMessage(self._content)


def _factory(content=None, error=None):
    """Return a model factory compatible with ``LLMService``'s injection seam."""
    return lambda provider=None, temperature=None: _FakeModel(
        content=content, error=error
    )


@pytest.fixture
def service():
    svc = LLMService()
    yield svc
    # Restore the real factory so the singleton does not leak test state.
    svc.reset_model_factory()


# ---------------- helpers ----------------


def test_strip_markdown_fences_json_block():
    assert strip_markdown_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_markdown_fences("```\n[1, 2]\n```") == "[1, 2]"


def test_strip_markdown_fences_leaves_plain_text():
    assert strip_markdown_fences('{"a": 1}') == '{"a": 1}'
    assert strip_markdown_fences("") == ""


def test_extract_text_flattens_content_blocks():
    class Response:
        content = [{"text": "hello "}, {"text": "world"}]

    assert extract_text(Response()) == "hello world"


def test_extract_text_handles_plain_string():
    class Response:
        content = "  plain text  "

    assert extract_text(Response()) == "plain text"


# ---------------- invoke_text ----------------


@pytest.mark.asyncio
async def test_invoke_text_returns_model_output(service):
    service.set_model_factory(_factory(content="hello world"))
    result = await service.invoke_text("prompt")
    assert result == "hello world"


@pytest.mark.asyncio
async def test_invoke_text_returns_none_on_error(service):
    service.set_model_factory(_factory(error=RuntimeError("boom")))
    assert await service.invoke_text("prompt") is None


# ---------------- invoke_json ----------------


@pytest.mark.asyncio
async def test_invoke_json_object(service):
    service.set_model_factory(_factory(content='{"key": "value", "n": 3}'))
    result = await service.invoke_json("prompt", expect="object")
    assert result == {"key": "value", "n": 3}


@pytest.mark.asyncio
async def test_invoke_json_array(service):
    service.set_model_factory(_factory(content='[{"action": "navigate"}]'))
    result = await service.invoke_json("prompt", expect="array")
    assert result == [{"action": "navigate"}]


@pytest.mark.asyncio
async def test_invoke_json_strips_markdown_fence(service):
    service.set_model_factory(_factory(content='```json\n{"a": 1}\n```'))
    assert await service.invoke_json("prompt", expect="object") == {"a": 1}


@pytest.mark.asyncio
async def test_invoke_json_malformed_returns_none(service):
    service.set_model_factory(_factory(content="{not valid json"))
    assert await service.invoke_json("prompt", expect="object") is None


@pytest.mark.asyncio
async def test_invoke_json_wrong_shape_object_expected(service):
    # Model returns an array but an object was expected.
    service.set_model_factory(_factory(content="[1, 2, 3]"))
    assert await service.invoke_json("prompt", expect="object") is None


@pytest.mark.asyncio
async def test_invoke_json_wrong_shape_array_expected(service):
    # Model returns an object but an array was expected.
    service.set_model_factory(_factory(content='{"a": 1}'))
    assert await service.invoke_json("prompt", expect="array") is None


@pytest.mark.asyncio
async def test_invoke_json_invocation_error_returns_none(service):
    service.set_model_factory(_factory(error=ValueError("provider down")))
    assert await service.invoke_json("prompt", expect="object") is None


@pytest.mark.asyncio
async def test_invoke_json_passes_provider_and_temperature(service):
    captured = {}

    def factory(provider=None, temperature=None):
        captured["provider"] = provider
        captured["temperature"] = temperature
        return _FakeModel(content='{"ok": true}')

    service.set_model_factory(factory)
    result = await service.invoke_json(
        "prompt", expect="object", temperature=0.5, provider="groq"
    )
    assert result == {"ok": True}
    assert captured == {"provider": "groq", "temperature": 0.5}
