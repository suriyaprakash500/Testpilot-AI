"""Fix 1: SPA in-app 404 detection + bounded post-navigation stabilization.

The bug: page_inspection classified routes before a SPA's client-side router
rendered, so an in-app 404 view (HTTP 200, title "No Found") was treated as a
valid route. These tests lock in the detector AND the bounded stabilization
that samples the FINAL DOM before classification.
"""
import pytest

from app.graph.page_inspection_node import (
    _is_not_found_page,
    _stabilize_page,
    classify_page_type,
    NETWORKIDLE_TIMEOUT_MS,
    SETTLE_TIMEOUT_MS,
)


class TestIsNotFoundPage:
    """The idurar live in-app 404 shape must be detected (SPA returns HTTP 200)."""

    def test_in_app_404_title_and_body(self):
        # Exact live shape observed on /about, /customer, /invoice.
        assert _is_not_found_page(
            "No Found",
            "Error 404 Sorry The Page You Requested Does Not Exist",
        ) is True

    def test_404_in_title(self):
        assert _is_not_found_page("404 - Not Found", "") is True

    def test_not_found_in_title(self):
        assert _is_not_found_page("Page Not Found", "") is True

    def test_404_body_regex(self):
        assert _is_not_found_page("", "Oops! The page does not exist.") is True

    def test_200_landing_page_is_not_404(self):
        assert _is_not_found_page("Dashboard", "Welcome back to your dashboard") is False

    def test_empty_is_not_404(self):
        assert _is_not_found_page("", "") is False


class _FakePage:
    """Records wait calls; optionally raises on the networkidle wait."""

    def __init__(self, raise_networkidle: bool = False):
        self.calls = []
        self._raise = raise_networkidle

    async def wait_for_load_state(self, state, timeout=None):
        self.calls.append(("load_state", state, timeout))
        if self._raise:
            raise TimeoutError("networkidle never reached")

    async def wait_for_timeout(self, ms):
        self.calls.append(("timeout", ms))


@pytest.mark.asyncio
class TestStabilizePage:
    """Stabilization must be bounded (no arbitrary multi-second waits)."""

    async def test_awaits_networkidle_then_short_settle(self):
        page = _FakePage()
        await _stabilize_page(page)
        assert page.calls[0] == ("load_state", "networkidle", NETWORKIDLE_TIMEOUT_MS)
        assert page.calls[1] == ("timeout", SETTLE_TIMEOUT_MS)

    async def test_networkidle_timeout_is_swallowed_and_still_settles(self):
        page = _FakePage(raise_networkidle=True)
        # Must not raise: SPAs frequently never reach networkidle.
        await _stabilize_page(page)
        assert page.calls[-1] == ("timeout", SETTLE_TIMEOUT_MS)

    async def test_waits_are_bounded(self):
        assert 0 < NETWORKIDLE_TIMEOUT_MS <= 5000
        assert 0 <= SETTLE_TIMEOUT_MS <= 1000


class TestNotFundClassificationWins:
    """A hydrated 404 body must classify as not_found regardless of route name."""

    def test_classify_not_found_override(self):
        # /about looks innocuous by route, but the rendered body is a 404.
        metadata = {
            "title": "No Found",
            "bodyText": "Error 404 Sorry The Page You Requested Does Not Exist",
            "inputs": [],
            "forms": [],
            "tables": [],
            "cards": [],
        }
        assert _is_not_found_page(metadata["title"], metadata["bodyText"]) is True
        # The caller forces page_type = "not_found"; sanity-check the base type
        # is not itself landing_page so the override is meaningful.
        assert classify_page_type("/about", metadata) != "landing_page"
