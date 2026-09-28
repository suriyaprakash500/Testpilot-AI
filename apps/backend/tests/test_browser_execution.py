"""Unit tests for browser_execution 429 capture and Retry-After parsing.

These exercise _execute_step's navigation error handling directly with a
lightweight fake page, so no real browser / Playwright is required.
"""
import pytest

from app.graph.nodes import (
    _execute_step,
    _parse_retry_after,
    RateLimitError,
)


class _FakeResponse:
    def __init__(self, status, headers=None):
        self.status = status
        self.headers = headers or {}


class _FakePage:
    def __init__(self, response):
        self._response = response
        self.goto_calls = []

    async def goto(self, url, **kwargs):
        self.goto_calls.append(url)
        return self._response


class TestParseRetryAfter:

    def test_integer_seconds(self):
        assert _parse_retry_after("5") == 5

    def test_missing_header_is_zero(self):
        assert _parse_retry_after(None) == 0
        assert _parse_retry_after("") == 0

    def test_http_date_is_treated_as_zero(self):
        # We only support the delta-seconds form; dates fall back to 0.
        assert _parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0

    def test_negative_is_clamped_to_zero(self):
        assert _parse_retry_after("-3") == 0


class TestExecuteStepRateLimit:

    @pytest.mark.asyncio
    async def test_navigate_429_raises_rate_limit_error(self):
        page = _FakePage(_FakeResponse(429, {"retry-after": "7"}))
        with pytest.raises(RateLimitError) as exc:
            await _execute_step(page, {"action": "navigate", "value": "https://x.com"}, [])
        assert exc.value.retry_after == 7

    @pytest.mark.asyncio
    async def test_navigate_429_without_header(self):
        page = _FakePage(_FakeResponse(429))
        with pytest.raises(RateLimitError) as exc:
            await _execute_step(page, {"action": "navigate", "value": "https://x.com"}, [])
        assert exc.value.retry_after == 0

    @pytest.mark.asyncio
    async def test_navigate_non_429_error_raises_generic(self):
        page = _FakePage(_FakeResponse(500))
        with pytest.raises(Exception) as exc:
            await _execute_step(page, {"action": "navigate", "value": "https://x.com"}, [])
        assert not isinstance(exc.value, RateLimitError)

    @pytest.mark.asyncio
    async def test_navigate_success_does_not_raise(self):
        page = _FakePage(_FakeResponse(200))
        logs = []
        await _execute_step(page, {"action": "navigate", "value": "https://x.com"}, logs)
        assert any("Navigation resolved" in line for line in logs)
