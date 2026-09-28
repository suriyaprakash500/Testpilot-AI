"""Unit tests for the Live Verify node.

Live Verify validates LLM-generated test steps against the ground-truth
page inspections (live DOM index) before browser execution. All logic is
deterministic — no LLM or Playwright mocking required.
"""
import pytest
from app.graph.live_verify_node import (
    live_verify_node,
    _score_hint,
    _selector_hints,
    _build_live_element_index,
    FUZZY_MATCH_THRESHOLD,
)


def _inspection(route="/", buttons=None, inputs=None, headings=None, links=None):
    return {
        "route": route,
        "buttons": [{"text": b} for b in (buttons or [])],
        "inputs": [
            {"label": lbl, "placeholder": None, "name": None, "type": "text"}
            for lbl in (inputs or [])
        ],
        "headings": [{"tag": "h1", "text": h} for h in (headings or [])],
        "links": [{"text": l, "href": "#"} for l in (links or [])],
    }


class TestScoreHint:

    def test_exact_match_scores_one(self):
        assert _score_hint("Sign In", "sign in") == 1.0

    def test_substring_match_scores_high(self):
        score = _score_hint("Sign In", "Sign In →")
        assert score >= 0.95

    def test_fuzzy_typo_above_threshold(self):
        # LLM hallucinated a small typo: "Search producats"
        score = _score_hint("Search products", "Search produktcs")
        assert score >= FUZZY_MATCH_THRESHOLD

    def test_unrelated_strings_score_below_threshold(self):
        score = _score_hint("Add to Cart", "Quarterly Financial Report")
        assert score < FUZZY_MATCH_THRESHOLD

    def test_empty_inputs_score_zero(self):
        assert _score_hint("", "anything") == 0.0
        assert _score_hint(None, "anything") == 0.0


class TestSelectorHints:

    def test_extracts_click_fill_and_assert_hints(self):
        steps = [
            {"action": "navigate", "value": "https://x.com"},
            {"action": "fill", "label": "Email", "value": "a@b.c"},
            {"action": "click", "role": "button", "name": "Subscribe", "first": True},
            {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Welcome"},
            {"action": "assert_visible", "locator_type": "text", "text": "Thanks!"},
        ]
        hints = _selector_hints(steps)

        assert len(hints) == 4
        assert hints[0]["step_field"] == "label"
        assert hints[1]["step_field"] == "name"
        assert hints[2]["pool"] == "role:heading"
        assert hints[3]["step_field"] == "text"

    def test_navigate_steps_produce_no_hints(self):
        steps = [{"action": "navigate", "value": "https://x.com"}]
        assert _selector_hints(steps) == []


class TestBuildLiveElementIndex:

    def test_flattens_all_element_kinds(self):
        inspection = _inspection(
            buttons=["Buy Now"],
            inputs=["Email address"],
            headings=["Pricing"],
            links=["Documentation"],
        )
        index = _build_live_element_index(inspection)
        texts = [e["text"] for e in index]

        assert "Buy Now" in texts
        assert "Email address" in texts
        assert "Pricing" in texts
        assert "Documentation" in texts


@pytest.mark.asyncio
class TestLiveVerifyNode:

    async def test_exact_selectors_are_verified(self):
        state = {
            "run_id": "run-1",
            "test_plan": [{
                "id": "TC-01",
                "name": "Login Flow",
                "route": "/login",
                "steps": [
                    {"action": "navigate", "value": "https://x.com/login"},
                    {"action": "fill", "label": "Email", "value": "a@b.c"},
                    {"action": "click", "role": "button", "name": "Sign In", "first": True},
                ],
            }],
            "page_inspections": [_inspection("/login", buttons=["Sign In"], inputs=["Email"])],
        }

        result = await live_verify_node(state)

        report = result["live_verifications"]["login_flow"]
        assert report["status"] == "verified"
        assert report["corrections"] == []
        assert report["unconfirmedSelectors"] == []
        assert result["status"] == "executing"

    async def test_hallucinated_selector_is_fuzzy_corrected(self):
        state = {
            "run_id": "run-1",
            "test_plan": [{
                "id": "TC-01",
                "name": "Newsletter Signup",
                "route": "/",
                "steps": [
                    {"action": "navigate", "value": "https://x.com"},
                    {"action": "click", "role": "button", "name": "Subscribe to Newsletter", "first": True},
                ],
            }],
            "page_inspections": [_inspection("/", buttons=["Subscribe to our Newsletter"])],
        }

        result = await live_verify_node(state)

        report = result["live_verifications"]["newsletter_signup"]
        assert report["status"] == "corrected"
        assert len(report["corrections"]) == 1

        correction = report["corrections"][0]
        assert correction["field"] == "name"
        assert correction["before"] == "Subscribe to Newsletter"
        assert correction["after"] == "Subscribe to our Newsletter"

        # The step itself must be rewritten in place for downstream execution
        corrected_step = result["test_plan"][0]["steps"][1]
        assert corrected_step["name"] == "Subscribe to our Newsletter"

        # Verification metadata embedded on the scenario
        assert result["test_plan"][0]["liveVerify"]["status"] == "corrected"
        assert result["test_plan"][0]["liveVerify"]["correctionsApplied"] == 1

    async def test_unknown_route_marks_scenario_unverified(self):
        state = {
            "run_id": "run-1",
            "test_plan": [{
                "id": "TC-01",
                "name": "Ghost Page",
                "route": "/does-not-exist",
                "steps": [
                    {"action": "navigate", "value": "https://x.com/does-not-exist"},
                ],
            }],
            "page_inspections": [_inspection("/", buttons=["Home CTA"])],
        }

        result = await live_verify_node(state)

        report = result["live_verifications"]["ghost_page"]
        assert report["status"] == "unverified"
        assert any("not inspected" in msg for msg in report["unconfirmedSelectors"])

    async def test_missing_selector_flags_but_does_not_fail_open(self):
        """Unconfirmable selectors are flagged, steps left untouched, pipeline proceeds."""
        original_step = {"action": "click", "role": "button", "name": "Totally Made Up Button", "first": True}
        state = {
            "run_id": "run-1",
            "test_plan": [{
                "id": "TC-01",
                "name": "Broken Scenario",
                "route": "/",
                "steps": [
                    {"action": "navigate", "value": "https://x.com"},
                    dict(original_step),
                ],
            }],
            "page_inspections": [_inspection("/", buttons=["Real Button"])],
        }

        result = await live_verify_node(state)

        report = result["live_verifications"]["broken_scenario"]
        assert report["status"] == "unverified"
        assert len(report["unconfirmedSelectors"]) == 1
        # Fail-open: step unchanged, run continues to execution status
        assert result["test_plan"][0]["steps"][1] == original_step
        assert result["status"] == "executing"

    async def test_empty_plan_returns_empty_verifications(self):
        state = {"run_id": "run-1", "test_plan": [], "page_inspections": []}
        result = await live_verify_node(state)

        assert result["live_verifications"] == {}
        assert result["test_plan"] == []

    async def test_mixed_scenarios_counted_in_message(self):
        state = {
            "run_id": "run-1",
            "test_plan": [
                {
                    "id": "TC-01",
                    "name": "Good One",
                    "route": "/",
                    "steps": [
                        {"action": "navigate", "value": "https://x.com"},
                        {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Pricing", "first": True},
                    ],
                },
                {
                    "id": "TC-02",
                    "name": "Unknown Route",
                    "route": "/missing",
                    "steps": [{"action": "navigate", "value": "https://x.com/missing"}],
                },
            ],
            "page_inspections": [_inspection("/", headings=["Pricing"])],
        }

        result = await live_verify_node(state)

        assert result["live_verifications"]["good_one"]["status"] == "verified"
        assert result["live_verifications"]["unknown_route"]["status"] == "unverified"

        message = result["messages"][0]["content"]
        assert "1 scenarios pre-verified" in message
        assert "1 flagged" in message


class TestLiveVerifyTestIds:
    """Grounded data-testids are verified exactly (no fuzzy rewriting)."""

    async def test_observed_testid_is_verified(self):
        state = {
            "run_id": "run-1",
            "test_plan": [{
                "id": "TC-01",
                "name": "Hero",
                "route": "/",
                "steps": [
                    {"action": "navigate", "value": "https://x.com"},
                    {"action": "assert_visible", "locator_type": "testid", "testid": "hero-title"},
                ],
            }],
            "page_inspections": [{
                "route": "/",
                "elements_with_testid": [{"testId": "hero-title", "tag": "h1", "text": "Welcome"}],
            }],
        }

        result = await live_verify_node(state)
        assert result["live_verifications"]["hero"]["status"] == "verified"

    async def test_invented_testid_is_flagged_not_corrected(self):
        state = {
            "run_id": "run-1",
            "test_plan": [{
                "id": "TC-01",
                "name": "Hero",
                "route": "/",
                "steps": [
                    {"action": "navigate", "value": "https://x.com"},
                    {"action": "click", "testid": "make-believe", "first": True},
                ],
            }],
            "page_inspections": [{
                "route": "/",
                "elements_with_testid": [{"testId": "hero-title"}],
            }],
        }

        result = await live_verify_node(state)
        report = result["live_verifications"]["hero"]
        assert report["status"] == "unverified"
        assert any("make-believe" in m for m in report["unconfirmedSelectors"])
        # Fail-open: an invented testid is never silently rewritten.
        assert result["test_plan"][0]["steps"][1]["testid"] == "make-believe"
        assert report["corrections"] == []

    def test_testid_hint_extraction(self):
        hints = _selector_hints([
            {"action": "click", "testid": "cta-button"},
            {"action": "fill", "testid": "email-input"},
        ])
        assert len(hints) == 2
        assert all(h["pool"] == "testid" for h in hints)
        assert hints[0]["step_field"] == "testid"



def _raw_inspection(
    route="/",
    title="Home",
    headings=None,
    buttons=None,
    inputs=None,
    links=None,
    images=None,
    testids=None,
    is_not_found=False,
    status_code=200,
):
    """Builds a RAW inspection dict in the exact shape page_inspection_node emits.

    Regression guard: prior grounding bugs slipped through because unit tests
    fed pre-shaped evidence instead of the real live inspection shape.
    """
    return {
        "route": route,
        "title": title,
        "page_type": "landing_page",
        "is_not_found": is_not_found,
        "headings": [{"tag": "h1", "text": h} for h in (headings or [])],
        "buttons": [{"text": b} for b in (buttons or [])],
        "inputs": [
            {"label": lbl, "placeholder": None, "name": None, "type": "text"}
            for lbl in (inputs or [])
        ],
        "links": [{"text": l, "href": "#"} for l in (links or [])],
        "images": [{"alt": a, "src": "logo.png"} for a in (images or [])],
        "elements_with_testid": [
            {"testId": t, "tag": "div", "text": ""} for t in (testids or [])
        ],
        "accessibility_tree": "",
        "status_code": status_code,
    }


class TestLiveVerifyFailClosed:
    """Fix 3: pre-execution verification is FAIL-CLOSED.

    VERIFIED / CORRECTED -> eligible for browser execution.
    UNVERIFIED           -> NOT executable, recorded as not_executed, excluded.
    """

    def test_raw_inspection_builder_matches_live_shape(self):
        insp = _raw_inspection(
            "/x", headings=["H"], buttons=["B"], inputs=["I"],
            links=["L"], images=["A"], testids=["t"],
        )
        for key in (
            "route", "title", "page_type", "is_not_found", "headings",
            "buttons", "inputs", "links", "images", "elements_with_testid",
            "accessibility_tree", "status_code",
        ):
            assert key in insp
        assert insp["images"] == [{"alt": "A", "src": "logo.png"}]
        assert insp["elements_with_testid"][0]["testId"] == "t"

    async def test_unverified_route_is_not_executable(self):
        state = {
            "run_id": "run-1",
            "test_plan": [{
                "id": "TC-01",
                "name": "Ghost Page",
                "route": "/ghost",
                "steps": [{"action": "navigate", "value": "https://x.com/ghost"}],
            }],
            "page_inspections": [_raw_inspection("/")],
        }

        result = await live_verify_node(state)

        report = result["live_verifications"]["ghost_page"]
        assert report["status"] == "unverified"
        assert report["executable"] is False
        assert report["execution_status"] == "NOT_EXECUTED"
        assert report["verification_status"] == "FAILED_VERIFICATION"

        # Never scheduled for browser execution.
        assert result["tests_to_execute"] == []
        results = result["execution_results"]
        assert len(results) == 1
        assert results[0]["status"] == "not_executed"
        assert results[0]["execution_status"] == "NOT_EXECUTED"
        assert results[0]["verification_status"] == "FAILED_VERIFICATION"
        assert results[0]["duration_ms"] == 0
        assert "FAILED_VERIFICATION" in results[0]["logs"]

    async def test_missing_selector_fails_closed(self):
        state = {
            "run_id": "run-1",
            "test_plan": [{
                "id": "TC-01",
                "name": "Broken Scenario",
                "route": "/",
                "steps": [
                    {"action": "navigate", "value": "https://x.com"},
                    {"action": "click", "role": "button", "name": "Totally Made Up Button", "first": True},
                ],
            }],
            "page_inspections": [_raw_inspection("/", buttons=["Real Button"])],
        }

        result = await live_verify_node(state)

        report = result["live_verifications"]["broken_scenario"]
        assert report["status"] == "unverified"
        assert report["executable"] is False
        assert result["tests_to_execute"] == []
        assert result["execution_results"][0]["status"] == "not_executed"

    async def test_verified_is_eligible_and_executes_all(self):
        state = {
            "run_id": "run-1",
            "test_plan": [{
                "id": "TC-01",
                "name": "Good One",
                "route": "/",
                "steps": [
                    {"action": "navigate", "value": "https://x.com"},
                    {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Pricing", "first": True},
                ],
            }],
            "page_inspections": [_raw_inspection("/", headings=["Pricing"])],
        }

        result = await live_verify_node(state)

        report = result["live_verifications"]["good_one"]
        assert report["status"] == "verified"
        assert report["executable"] is True
        assert report["execution_status"] == "ELIGIBLE"
        assert report["verification_status"] == "VERIFIED"
        # Nothing excluded -> sentinel None means "execute all".
        assert result["tests_to_execute"] is None
        assert "execution_results" not in result

    async def test_corrected_is_eligible(self):
        state = {
            "run_id": "run-1",
            "test_plan": [{
                "id": "TC-01",
                "name": "Newsletter Signup",
                "route": "/",
                "steps": [
                    {"action": "navigate", "value": "https://x.com"},
                    {"action": "click", "role": "button", "name": "Subscribe to Newsletter", "first": True},
                ],
            }],
            "page_inspections": [_raw_inspection("/", buttons=["Subscribe to our Newsletter"])],
        }

        result = await live_verify_node(state)

        report = result["live_verifications"]["newsletter_signup"]
        assert report["status"] == "corrected"
        assert report["executable"] is True
        assert report["execution_status"] == "ELIGIBLE"
        assert report["verification_status"] == "CORRECTED"
        assert result["tests_to_execute"] is None

    async def test_mixed_schedules_only_eligible_ids(self):
        state = {
            "run_id": "run-1",
            "test_plan": [
                {
                    "id": "TC-01",
                    "name": "Good One",
                    "route": "/",
                    "steps": [
                        {"action": "navigate", "value": "https://x.com"},
                        {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Pricing", "first": True},
                    ],
                },
                {
                    "id": "TC-02",
                    "name": "Unknown Route",
                    "route": "/missing",
                    "steps": [{"action": "navigate", "value": "https://x.com/missing"}],
                },
            ],
            "page_inspections": [_raw_inspection("/", headings=["Pricing"])],
        }

        result = await live_verify_node(state)

        assert result["tests_to_execute"] == ["good_one"]
        assert [r["test_name"] for r in result["execution_results"]] == ["Unknown Route"]
