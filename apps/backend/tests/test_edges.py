"""Unit tests for conditional edge routing functions.

All routing functions are pure deterministic logic operating on state dicts.
No mocking needed.
"""
import pytest
from app.graph.edges import (
    route_after_auth,
    route_after_evaluation,
    route_after_failure_analysis,
    route_after_inconclusive_retry,
    MAX_REPAIR_ATTEMPTS,
    MAX_INCONCLUSIVE_RETRIES,
)


class TestRouteAfterAuth:

    def test_routes_to_abort_on_error(self):
        state = {"error": "Invalid credentials"}
        assert route_after_auth(state) == "abort"

    def test_routes_to_repo_analysis_on_success(self):
        state = {"error": None}
        assert route_after_auth(state) == "repo_analysis"

    def test_routes_to_repo_analysis_when_no_error_key(self):
        state = {}
        assert route_after_auth(state) == "repo_analysis"


class TestRouteAfterEvaluation:

    def test_all_pass_routes_to_pr(self):
        state = {
            "evaluation_results": {
                "test_1": {"verdict": "PASS"},
                "test_2": {"verdict": "PASS"},
            }
        }
        assert route_after_evaluation(state) == "github_pr"

    def test_has_failures_routes_to_failure_analysis(self):
        state = {
            "evaluation_results": {
                "test_1": {"verdict": "PASS"},
                "test_2": {"verdict": "FAIL"},
            }
        }
        assert route_after_evaluation(state) == "failure_analysis"

    def test_inconclusive_only_routes_to_retry(self):
        state = {
            "evaluation_results": {
                "test_1": {"verdict": "PASS"},
                "test_2": {"verdict": "INCONCLUSIVE"},
            }
        }
        assert route_after_evaluation(state) == "inconclusive_retry"

    def test_failures_take_priority_over_inconclusive(self):
        """When both FAIL and INCONCLUSIVE exist, failures are handled first."""
        state = {
            "evaluation_results": {
                "test_1": {"verdict": "FAIL"},
                "test_2": {"verdict": "INCONCLUSIVE"},
                "test_3": {"verdict": "PASS"},
            }
        }
        assert route_after_evaluation(state) == "failure_analysis"

    def test_empty_evaluation_results_routes_to_pr(self):
        state = {"evaluation_results": {}}
        assert route_after_evaluation(state) == "github_pr"

    def test_missing_evaluation_results_routes_to_pr(self):
        state = {}
        assert route_after_evaluation(state) == "github_pr"

    def test_none_evaluation_results_routes_to_pr(self):
        state = {"evaluation_results": None}
        assert route_after_evaluation(state) == "github_pr"


class TestRouteAfterFailureAnalysis:

    def test_repairable_test_routes_to_repair(self):
        state = {
            "failure_analyses": {
                "test_1": {"root_cause": "selector_wrong"},
            },
            "repair_attempts": {},
        }
        assert route_after_failure_analysis(state) == "test_repair"

    def test_timing_issue_routes_to_repair(self):
        state = {
            "failure_analyses": {
                "test_1": {"root_cause": "timing_issue"},
            },
            "repair_attempts": {},
        }
        assert route_after_failure_analysis(state) == "test_repair"

    def test_test_assumption_wrong_routes_to_repair(self):
        state = {
            "failure_analyses": {
                "test_1": {"root_cause": "test_assumption_wrong"},
            },
            "repair_attempts": {},
        }
        assert route_after_failure_analysis(state) == "test_repair"

    def test_app_bug_routes_to_pr(self):
        state = {
            "failure_analyses": {
                "test_1": {"root_cause": "application_bug"},
            },
            "repair_attempts": {},
        }
        assert route_after_failure_analysis(state) == "github_pr"

    def test_max_retries_exhausted_routes_to_pr(self):
        state = {
            "failure_analyses": {
                "test_1": {"root_cause": "selector_wrong"},
            },
            "repair_attempts": {"test_1": MAX_REPAIR_ATTEMPTS},
        }
        assert route_after_failure_analysis(state) == "github_pr"

    def test_retries_below_max_routes_to_repair(self):
        state = {
            "failure_analyses": {
                "test_1": {"root_cause": "selector_wrong"},
            },
            "repair_attempts": {"test_1": MAX_REPAIR_ATTEMPTS - 1},
        }
        assert route_after_failure_analysis(state) == "test_repair"

    def test_mixed_repairable_and_app_bug(self):
        """If at least one test is repairable, route to repair."""
        state = {
            "failure_analyses": {
                "test_1": {"root_cause": "application_bug"},
                "test_2": {"root_cause": "selector_wrong"},
            },
            "repair_attempts": {},
        }
        assert route_after_failure_analysis(state) == "test_repair"

    def test_all_app_bugs_routes_to_pr(self):
        state = {
            "failure_analyses": {
                "test_1": {"root_cause": "application_bug"},
                "test_2": {"root_cause": "application_bug"},
            },
            "repair_attempts": {},
        }
        assert route_after_failure_analysis(state) == "github_pr"

    def test_empty_failure_analyses_routes_to_pr(self):
        state = {"failure_analyses": {}, "repair_attempts": {}}
        assert route_after_failure_analysis(state) == "github_pr"

    def test_missing_state_keys_routes_to_pr(self):
        state = {}
        assert route_after_failure_analysis(state) == "github_pr"


class TestRouteAfterInconclusiveRetry:

    def test_retries_left_routes_to_execution(self):
        state = {
            "inconclusive_retries": {"test_1": 1},
        }
        assert route_after_inconclusive_retry(state) == "browser_execution"

    def test_retries_exhausted_routes_to_pr(self):
        state = {
            "inconclusive_retries": {"test_1": MAX_INCONCLUSIVE_RETRIES},
        }
        assert route_after_inconclusive_retry(state) == "github_pr"

    def test_mixed_retries_routes_to_execution(self):
        """If any test has retries left, route back to execution."""
        state = {
            "inconclusive_retries": {
                "test_1": MAX_INCONCLUSIVE_RETRIES,
                "test_2": 1,
            },
        }
        assert route_after_inconclusive_retry(state) == "browser_execution"

    def test_all_exhausted_routes_to_pr(self):
        state = {
            "inconclusive_retries": {
                "test_1": MAX_INCONCLUSIVE_RETRIES,
                "test_2": MAX_INCONCLUSIVE_RETRIES + 1,
            },
        }
        assert route_after_inconclusive_retry(state) == "github_pr"

    def test_empty_retries_routes_to_pr(self):
        state = {"inconclusive_retries": {}}
        assert route_after_inconclusive_retry(state) == "github_pr"

    def test_missing_state_key_routes_to_pr(self):
        state = {}
        assert route_after_inconclusive_retry(state) == "github_pr"
