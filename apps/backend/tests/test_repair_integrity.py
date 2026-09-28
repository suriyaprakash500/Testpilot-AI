"""Fix 4/5: a repair must preserve the test's SEMANTIC intent.

A repair may change the locator / timing / implementation but never remove a
required action, retarget the route, or delete assertions to force a pass
("passing by degrading"). Disallowed repairs become REJECTED and terminal.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.graph.test_repair_node import (
    test_repair_node as repair_node,
    _validate_repair_integrity,
    _action_route,
    _derive_intent,
    _build_repair_prompt,
)

WEBSITE = "https://app.example.com"

# Original intent: "click Customer link -> navigate -> verify Customer page".
INTENT = {
    "test_id": "customer_flow",
    "test_name": "Customer Flow",
    "feature": "Customers",
    "route": "/customers",
    "required_actions": [
        {"action": "navigate", "value": "https://app.example.com/login"},
        {"action": "click", "name": "Customer", "first": True},
        {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Customers"},
    ],
    "expected_outcome": "Customer page is displayed",
}

# Valid: same action types / route / assertion count, only the locator changed
# (get_by_text -> get_by_role).
VALID_REPAIR = [
    {"action": "navigate", "value": "https://app.example.com/login"},
    {"action": "click", "role": "link", "name": "Customer", "first": True},
    {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Customers"},
]

# Degraded: the whole flow collapsed into one trivial assertion.
DEGRADED_REPAIR = [
    {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Sign In"},
]


class TestActionRoute:

    def test_relative_route(self):
        assert _action_route({"action": "navigate", "value": "https://app.example.com/login"}, WEBSITE) == "/login"

    def test_root_route(self):
        assert _action_route({"action": "navigate", "value": "https://app.example.com"}, WEBSITE) == "/"

    def test_non_navigate_is_none(self):
        assert _action_route({"action": "click", "name": "x"}, WEBSITE) is None


class TestDeriveIntent:

    def test_derives_from_plan(self):
        plan = [{
            "name": "Customer Flow",
            "feature": "Customers",
            "route": "/customers",
            "steps": [
                {"action": "navigate", "value": "https://app.example.com/login"},
                {"action": "click", "name": "Customer"},
            ],
            "expected_result": "Customer page",
        }]
        intent = _derive_intent("customer_flow", plan)
        assert intent["test_id"] == "customer_flow"
        assert intent["feature"] == "Customers"
        assert [a["action"] for a in intent["required_actions"]] == ["navigate", "click"]
        assert intent["expected_outcome"] == "Customer page"

    def test_missing_id_returns_empty(self):
        assert _derive_intent("nope", [{"name": "Other", "steps": []}]) == {}


class TestValidateRepairIntegrity:

    def test_selector_only_change_is_accepted(self):
        ok, reason = _validate_repair_integrity(INTENT, VALID_REPAIR, WEBSITE)
        assert ok is True
        assert reason

    def test_degraded_repair_is_rejected(self):
        ok, reason = _validate_repair_integrity(INTENT, DEGRADED_REPAIR, WEBSITE)
        assert ok is False
        assert "action" in reason.lower() or "route" in reason.lower()

    def test_route_change_is_rejected(self):
        repaired = [
            {"action": "navigate", "value": "https://app.example.com/signin"},
            {"action": "click", "role": "link", "name": "Customer", "first": True},
            {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Customers"},
        ]
        ok, reason = _validate_repair_integrity(INTENT, repaired, WEBSITE)
        assert ok is False
        assert "route" in reason.lower()

    def test_assertion_decrease_is_rejected(self):
        # Original verifies TWO things; the "repair" keeps the flow but drops one
        # assertion to force a pass -> rejected even though action types match.
        intent = {
            **INTENT,
            "required_actions": INTENT["required_actions"] + [
                {"action": "assert_visible", "locator_type": "text", "text": "Active"},
            ],
        }
        repaired = [
            {"action": "navigate", "value": "https://app.example.com/login"},
            {"action": "click", "role": "link", "name": "Customer", "first": True},
            {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Customers"},
        ]
        ok, reason = _validate_repair_integrity(intent, repaired, WEBSITE)
        assert ok is False
        assert "assertion" in reason.lower()

    def test_dropped_assertion_action_type_is_rejected(self):
        repaired = [
            {"action": "navigate", "value": "https://app.example.com/login"},
            {"action": "click", "role": "link", "name": "Customer", "first": True},
        ]
        ok, reason = _validate_repair_integrity(INTENT, repaired, WEBSITE)
        assert ok is False
        assert "assert" in reason.lower()

    def test_added_assertion_is_allowed(self):
        repaired = VALID_REPAIR + [
            {"action": "assert_visible", "locator_type": "text", "text": "Active"},
        ]
        ok, _ = _validate_repair_integrity(INTENT, repaired, WEBSITE)
        assert ok is True

    def test_empty_intent_has_no_basis_to_reject(self):
        ok, _ = _validate_repair_integrity({}, VALID_REPAIR, WEBSITE)
        assert ok is True


class TestRepairPrompt:

    def test_prompt_lists_required_actions_and_forbids_intent_change(self):
        prompt = _build_repair_prompt(
            "customer_flow", "code", {"root_cause": "selector_wrong"}, {}, {}, INTENT
        )
        assert "PRESERVE TEST INTENT" in prompt
        assert "assert_visible" in prompt
        assert "never retarget the test" in prompt
        assert "never delete or weaken assertions" in prompt


def _node_state(repair_statuses=None):
    return {
        "run_id": "r1",
        "website_url": WEBSITE,
        "failure_analyses": {
            "customer_flow": {
                "root_cause": "selector_wrong",
                "repairable": True,
                "explanation": "locator did not match the DOM",
            }
        },
        "repair_attempts": {},
        "repair_statuses": repair_statuses or {},
        "generated_tests": [],
        "execution_results": [],
        "test_plan": [{"name": "Customer Flow", "feature": "Customers", "route": "/customers", "steps": []}],
        "page_inspections": [],
        "test_intents": {"customer_flow": INTENT},
    }


@pytest.mark.asyncio
class TestRepairNodeIntegrity:

    async def test_accepts_selector_only_repair_and_schedules_it(self):
        with patch(
            "app.graph.test_repair_node._llm_repair_test",
            new=AsyncMock(return_value=VALID_REPAIR),
        ):
            res = await repair_node(_node_state())
        assert res["repair_statuses"]["customer_flow"]["status"] == "ACCEPTED"
        assert res["tests_to_execute"] == ["customer_flow"]
        assert res["repaired_tests"]["customer_flow"] == VALID_REPAIR
        assert res["repair_attempts"]["customer_flow"] == 1

    async def test_rejects_degraded_repair_and_does_not_schedule(self):
        with patch(
            "app.graph.test_repair_node._llm_repair_test",
            new=AsyncMock(return_value=DEGRADED_REPAIR),
        ):
            res = await repair_node(_node_state())
        # Not scheduled for re-execution; no repaired steps; budget untouched.
        assert res["repair_statuses"]["customer_flow"]["status"] == "REJECTED"
        assert res["tests_to_execute"] is None
        assert "repaired_tests" not in res
        assert res["repair_attempts"].get("customer_flow") is None

    async def test_already_rejected_test_is_not_repaired_again(self):
        state = _node_state(repair_statuses={"customer_flow": {"status": "REJECTED", "reason": "intent"}})
        with patch(
            "app.graph.test_repair_node._llm_repair_test",
            new=AsyncMock(return_value=VALID_REPAIR),
        ) as mocked:
            res = await repair_node(state)
        mocked.assert_not_awaited()
        assert res["tests_to_execute"] is None
        assert res["repair_statuses"] == {}
