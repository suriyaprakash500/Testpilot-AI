"""Unit tests for the state merge_dicts reducer.

Validates that the custom reducer prevents last-write-wins corruption
when LangGraph updates per-test dictionary fields during repair loops.
"""
import pytest
from app.graph.state import merge_dicts


class TestMergeDicts:

    def test_merges_non_overlapping_keys(self):
        left = {"test_1": {"verdict": "PASS"}}
        right = {"test_2": {"verdict": "FAIL"}}
        merged = merge_dicts(left, right)

        assert merged == {
            "test_1": {"verdict": "PASS"},
            "test_2": {"verdict": "FAIL"},
        }

    def test_right_overwrites_overlapping_keys(self):
        """For a specific test_id, the latest update wins."""
        left = {"test_1": {"verdict": "FAIL", "category": "selector_failure"}}
        right = {"test_1": {"verdict": "PASS", "category": "all_assertions_passed"}}
        merged = merge_dicts(left, right)

        assert merged["test_1"]["verdict"] == "PASS"

    def test_preserves_existing_keys_on_partial_update(self):
        """Updating test_2 does not destroy test_1 data."""
        left = {
            "test_1": {"verdict": "PASS"},
            "test_2": {"verdict": "FAIL"},
        }
        right = {"test_2": {"verdict": "PASS"}}
        merged = merge_dicts(left, right)

        assert merged["test_1"]["verdict"] == "PASS"
        assert merged["test_2"]["verdict"] == "PASS"

    def test_left_empty_returns_right(self):
        merged = merge_dicts({}, {"test_1": {"verdict": "PASS"}})
        assert merged == {"test_1": {"verdict": "PASS"}}

    def test_right_empty_returns_left(self):
        merged = merge_dicts({"test_1": {"verdict": "PASS"}}, {})
        assert merged == {"test_1": {"verdict": "PASS"}}

    def test_both_empty_returns_empty(self):
        merged = merge_dicts({}, {})
        assert merged == {}

    def test_left_none_returns_right(self):
        merged = merge_dicts(None, {"test_1": 1})
        assert merged == {"test_1": 1}

    def test_right_none_returns_left(self):
        merged = merge_dicts({"test_1": 1}, None)
        assert merged == {"test_1": 1}

    def test_does_not_mutate_left(self):
        left = {"test_1": {"verdict": "PASS"}}
        right = {"test_2": {"verdict": "FAIL"}}
        original_left = left.copy()
        merge_dicts(left, right)

        assert left == original_left

    def test_simulates_repair_loop_state_preservation(self):
        """Simulates 3 repair cycles where only 1 test is updated each time.

        Verifies that previously evaluated tests are not destroyed.
        """
        # Cycle 1: evaluation of all 3 tests
        state = {}
        cycle_1 = {
            "test_login": {"verdict": "PASS"},
            "test_signup": {"verdict": "FAIL"},
            "test_checkout": {"verdict": "FAIL"},
        }
        state = merge_dicts(state, cycle_1)
        assert len(state) == 3

        # Cycle 2: repair of test_signup only
        cycle_2 = {"test_signup": {"verdict": "PASS"}}
        state = merge_dicts(state, cycle_2)
        assert state["test_login"]["verdict"] == "PASS"  # Preserved
        assert state["test_signup"]["verdict"] == "PASS"  # Updated
        assert state["test_checkout"]["verdict"] == "FAIL"  # Preserved

        # Cycle 3: repair of test_checkout only
        cycle_3 = {"test_checkout": {"verdict": "PASS"}}
        state = merge_dicts(state, cycle_3)
        assert state["test_login"]["verdict"] == "PASS"  # Still preserved
        assert state["test_signup"]["verdict"] == "PASS"  # Still preserved
        assert state["test_checkout"]["verdict"] == "PASS"  # Updated
