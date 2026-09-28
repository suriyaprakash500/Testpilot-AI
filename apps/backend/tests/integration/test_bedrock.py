"""Optional AWS Bedrock integration test.

This test performs a *real* Bedrock invocation and therefore requires:

* ``TESTPILOT_BEDROCK=1`` (explicit opt-in),
* reachable AWS credentials via the normal boto3 chain (e.g. an EC2 IAM role),
* ``AWS_REGION`` and ``BEDROCK_MODEL_ID`` configured.

It is skipped by default so the unit suite never depends on AWS. Run it inside
the company sandbox to verify the path:

    EC2 -> IAM credentials -> boto3 -> Bedrock -> configured model
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("TESTPILOT_BEDROCK", "").lower() not in ("1", "true"),
    reason=(
        "Bedrock integration test — needs AWS credentials and model access. "
        "Set TESTPILOT_BEDROCK=1 (plus AWS_REGION / BEDROCK_MODEL_ID) to run."
    ),
)


@pytest.mark.asyncio
async def test_bedrock_provider_invokes_configured_model():
    """Minimal model invocation through the Bedrock provider strategy."""
    from app.core.config import settings
    from app.services.llm.providers import BedrockProvider

    assert settings.bedrock_model_id, "BEDROCK_MODEL_ID must be configured to run this test"

    model = BedrockProvider().build(temperature=0.0)
    response = await model.ainvoke("Reply with the single word: ok")

    text = getattr(response, "content", response)
    if isinstance(text, list):
        text = "".join(
            str(block.get("text", "")) if isinstance(block, dict) else str(block)
            for block in text
        )
    assert str(text).strip(), "Bedrock returned an empty response"


@pytest.mark.asyncio
async def test_llm_service_uses_bedrock_provider():
    """The factory must resolve to the Bedrock provider when configured."""
    from app.core.config import settings
    from app.services.llm.base import get_provider_class
    from app.services.llm.factory import LLMFactory
    from app.services.llm.providers import BedrockProvider

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "llm_provider", "bedrock", raising=False)
        LLMFactory.clear_cache()
        try:
            assert get_provider_class("bedrock") is BedrockProvider
            model = LLMFactory.get(provider="bedrock", temperature=0.0)
            assert hasattr(model, "ainvoke")
        finally:
            LLMFactory.clear_cache()
