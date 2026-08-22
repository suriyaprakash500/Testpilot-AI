"""Unit tests for the test_evaluation_node deterministic classifier.

Tests the _classify_test_result function which is the core deterministic
logic — no LLM, no network, no mocking needed.
"""
import pytest
from app.graph.test_evaluation_node import _classify_test_result
from app.graph.test_evaluation_node import test_evaluation_node as evaluation_node


class TestClassifyTestResult:
    """Tests for the deterministic _classify_test_result function."""

    def test_passed_test_returns_pass(self):
        result = _classify_test_result({
            "status": "passed",
            "error": None,
            "logs": "All good",
            "duration_ms": 1200,
        })
        assert result["verdict"] == "PASS"
        assert result["category"] == "all_assertions_passed"

    def test_passed_test_with_empty_error_returns_pass(self):
        result = _classify_test_result({
            "status": "passed",
            "error": "",
            "logs": "",
            "duration_ms": 500,
        })
        assert result["verdict"] == "PASS"

    def test_zero_duration_failed_returns_inconclusive(self):
        result = _classify_test_result({
            "status": "failed",
            "error": "something",
            "logs": "",
            "duration_ms": 0,
        })
        assert result["verdict"] == "INCONCLUSIVE"
        assert result["category"] == "never_executed"

    def test_zero_duration_passed_returns_pass(self):
        """A passed test with zero duration is still a pass."""
        result = _classify_test_result({
            "status": "passed",
            "error": None,
            "logs": "",
            "duration_ms": 0,
        })
        assert result["verdict"] == "PASS"

    def test_dns_error_returns_inconclusive(self):
        result = _classify_test_result({
            "status": "failed",
            "error": "net::ERR_NAME_NOT_RESOLVED at https://example.com",
            "logs": "",
            "duration_ms": 100,
        })
        assert result["verdict"] == "INCONCLUSIVE"
        assert result["category"] == "environment_error"

    def test_connection_refused_returns_inconclusive(self):
        result = _classify_test_result({
            "status": "failed",
            "error": "Connection refused to localhost:3000",
            "logs": "",
            "duration_ms": 50,
        })
        assert result["verdict"] == "INCONCLUSIVE"
        assert result["category"] == "environment_error"

    def test_navigation_timeout_returns_inconclusive(self):
        result = _classify_test_result({
            "status": "failed",
            "error": "Navigation timeout of 12000ms exceeded",
            "logs": "",
            "duration_ms": 12000,
        })
        assert result["verdict"] == "INCONCLUSIVE"
        assert result["category"] == "environment_error"

    def test_502_bad_gateway_returns_inconclusive(self):
        result = _classify_test_result({
            "status": "failed",
            "error": "",
            "logs": "502 Bad Gateway from upstream server",
            "duration_ms": 300,
        })
        assert result["verdict"] == "INCONCLUSIVE"
        assert result["category"] == "environment_error"

    def test_selector_waiting_returns_fail(self):
        result = _classify_test_result({
            "status": "failed",
            "error": "Error: waiting for selector '#submit-btn' to be visible",
            "logs": "",
            "duration_ms": 5000,
        })
        assert result["verdict"] == "FAIL"
        assert result["category"] == "selector_failure"

    def test_locator_strict_mode_returns_fail(self):
        result = _classify_test_result({
            "status": "failed",
            "error": "strict mode violation: locator resolved to 3 elements",
            "logs": "",
            "duration_ms": 200,
        })
        assert result["verdict"] == "FAIL"
        assert result["category"] == "selector_failure"

    def test_element_not_visible_returns_fail(self):
        result = _classify_test_result({
            "status": "failed",
            "error": "Element is not visible",
            "logs": "",
            "duration_ms": 1000,
        })
        assert result["verdict"] == "FAIL"
        assert result["category"] == "selector_failure"

    def test_generic_assertion_failure_returns_fail(self):
        result = _classify_test_result({
            "status": "failed",
            "error": "Expected 'Welcome' but got 'Login'",
            "logs": "",
            "duration_ms": 800,
        })
        assert result["verdict"] == "FAIL"
        assert result["category"] == "assertion_failure"

    def test_failed_no_error_returns_fail_unknown(self):
        result = _classify_test_result({
            "status": "failed",
            "error": None,
            "logs": "test output here",
            "duration_ms": 500,
        })
        assert result["verdict"] == "FAIL"
        assert result["category"] == "unknown_failure"

    def test_unknown_status_returns_inconclusive(self):
        result = _classify_test_result({
            "status": "skipped",
            "error": None,
            "logs": "",
            "duration_ms": 0,
        })
        # zero duration + non-passed -> never_executed
        assert result["verdict"] == "INCONCLUSIVE"

    def test_unrecognized_status_with_duration_returns_inconclusive(self):
        result = _classify_test_result({
            "status": "pending",
            "error": None,
            "logs": "",
            "duration_ms": 100,
        })
        assert result["verdict"] == "INCONCLUSIVE"
        assert result["category"] == "unclassified"

    def test_environment_pattern_in_logs_not_error(self):
        """Environment patterns detected in logs (not error) still classify as INCONCLUSIVE."""
        result = _classify_test_result({
            "status": "failed",
            "error": "",
            "logs": "Service unavailable, please try again later",
            "duration_ms": 200,
        })
        assert result["verdict"] == "INCONCLUSIVE"
        assert result["category"] == "environment_error"

    def test_evidence_truncated_to_300_chars(self):
        long_error = "x" * 500
        result = _classify_test_result({
            "status": "failed",
            "error": long_error,
            "logs": "",
            "duration_ms": 100,
        })
        assert len(result["evidence"]) <= 300


class TestRealWorldFailureRegression:
    """Regressions from run 29e07b17: real Playwright failures were
    misclassified as INCONCLUSIVE because the bare 'timeout' environment
    pattern outranked selector patterns, starving failure_analysis/test_repair.
    """

    def test_click_timeout_waiting_for_locator_returns_fail(self):
        """'Locator.click: Timeout exceeded ... waiting for locator(...)' is a repairable defect."""
        result = _classify_test_result({
            "status": "failed",
            "error": "Locator.click: Timeout 30000ms exceeded.\nCall log:\n  - waiting for locator(\"button:has-text('Customize')\")",
            "logs": "",
            "duration_ms": 32556,
        })
        assert result["verdict"] == "FAIL"
        assert result["category"] == "selector_failure"

    def test_expect_not_found_returns_fail(self):
        """'Locator expected to be visible / Error: element(s) not found' is a defect."""
        result = _classify_test_result({
            "status": "failed",
            "error": "Locator expected to be visible\nActual value: None\nError: element(s) not found",
            "logs": "",
            "duration_ms": 7383,
        })
        assert result["verdict"] == "FAIL"
        assert result["category"] == "selector_failure"

    def test_timeout_with_get_by_role_wait_returns_fail(self):
        result = _classify_test_result({
            "status": "failed",
            "error": "Timeout 5000ms exceeded.\nwaiting for get_by_role(\"heading\", name=\"Dashboard\")",
            "logs": "",
            "duration_ms": 5100,
        })
        assert result["verdict"] == "FAIL"
        assert result["category"] == "selector_failure"

    def test_bare_timeout_without_locator_context_is_fail(self):
        """A bare timeout with no infra signal should reach failure_analysis (FAIL), not be dismissed as env flake."""
        result = _classify_test_result({
            "status": "failed",
            "error": "Timeout 30000ms exceeded",
            "logs": "",
            "duration_ms": 30000,
        })
        assert result["verdict"] == "FAIL"

    def test_navigation_still_inconclusive_despite_locator_word(self):
        """True navigation timeouts stay INCONCLUSIVE even if logs mention locators elsewhere."""
        result = _classify_test_result({
            "status": "failed",
            "error": "page.goto: Navigation timeout of 15000ms exceeded",
            "logs": "earlier attempt had waiting for locator('#x')",
            "duration_ms": 15000,
        })
        # Selector patterns checked first -> this now classifies as FAIL by design:
        # goto errors never contain locator-wait text in the ERROR field itself,
        # so the combined_output check must not let stale log text hijack it.
        assert result["verdict"] == "INCONCLUSIVE"


class TestEvaluationNode:
    """Tests for the test_evaluation_node async function."""

    @pytest.mark.asyncio
    async def test_all_passed_returns_correct_counts(self):
        state = {
            "run_id": "test-run",
            "execution_results": [
                {"test_name": "Login Test", "status": "passed", "error": None, "logs": "", "duration_ms": 100},
                {"test_name": "Signup Test", "status": "passed", "error": None, "logs": "", "duration_ms": 200},
            ],
        }
        result = await evaluation_node(state)
        evaluations = result["evaluation_results"]

        assert len(evaluations) == 2
        assert all(e["verdict"] == "PASS" for e in evaluations.values())
        assert "2 passed" in result["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_mixed_results_classified_correctly(self):
        state = {
            "run_id": "test-run",
            "execution_results": [
                {"test_name": "Pass Test", "status": "passed", "error": None, "logs": "", "duration_ms": 100},
                {"test_name": "Fail Test", "status": "failed", "error": "Element is not visible", "logs": "", "duration_ms": 500},
                {"test_name": "Flaky Test", "status": "failed", "error": "Connection refused", "logs": "", "duration_ms": 50},
            ],
        }
        result = await evaluation_node(state)
        evaluations = result["evaluation_results"]

        assert evaluations["pass_test"]["verdict"] == "PASS"
        assert evaluations["fail_test"]["verdict"] == "FAIL"
        assert evaluations["flaky_test"]["verdict"] == "INCONCLUSIVE"

    @pytest.mark.asyncio
    async def test_empty_execution_results(self):
        state = {
            "run_id": "test-run",
            "execution_results": [],
        }
        result = await evaluation_node(state)
        assert result["evaluation_results"] == {}

    @pytest.mark.asyncio
    async def test_test_id_normalization(self):
        """Test names are normalized to lowercase, underscored IDs."""
        state = {
            "run_id": "test-run",
            "execution_results": [
                {"test_name": "Login: Auth Flow", "status": "passed", "error": None, "logs": "", "duration_ms": 100},
            ],
        }
        result = await evaluation_node(state)
        assert "login_auth_flow" in result["evaluation_results"]
