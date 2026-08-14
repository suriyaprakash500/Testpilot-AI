"""Unit tests for the inconclusive_retry_node.

Purely deterministic node — no LLM, no mocking needed.
"""
import pytest
from app.graph.inconclusive_retry_node import (
    inconclusive_retry_node,
    MAX_INCONCLUSIVE_RETRIES,
)


class TestInconclusiveRetryNode:

    @pytest.mark.asyncio
    async def test_first_retry_schedules_reexecution(self):
        state = {
            "run_id": "run-1",
            "evaluation_results": {
                "test_1": {"verdict": "INCONCLUSIVE"},
            },
            "inconclusive_retries": {},
        }
        result = await inconclusive_retry_node(state)

        assert result["inconclusive_retries"]["test_1"] == 1
        assert result["tests_to_execute"] == ["test_1"]

    @pytest.mark.asyncio
    async def test_second_retry_still_retryable(self):
        state = {
            "run_id": "run-1",
            "evaluation_results": {
                "test_1": {"verdict": "INCONCLUSIVE"},
            },
            "inconclusive_retries": {"test_1": 1},
        }
        result = await inconclusive_retry_node(state)

        assert result["inconclusive_retries"]["test_1"] == 2
        assert result["tests_to_execute"] == ["test_1"]

    @pytest.mark.asyncio
    async def test_retries_exhausted_returns_none_tests(self):
        state = {
            "run_id": "run-1",
            "evaluation_results": {
                "test_1": {"verdict": "INCONCLUSIVE"},
            },
            "inconclusive_retries": {"test_1": MAX_INCONCLUSIVE_RETRIES},
        }
        result = await inconclusive_retry_node(state)

        assert result["inconclusive_retries"]["test_1"] == MAX_INCONCLUSIVE_RETRIES + 1
        assert result["tests_to_execute"] is None

    @pytest.mark.asyncio
    async def test_mixed_retryable_and_exhausted(self):
        state = {
            "run_id": "run-1",
            "evaluation_results": {
                "test_1": {"verdict": "INCONCLUSIVE"},
                "test_2": {"verdict": "INCONCLUSIVE"},
            },
            "inconclusive_retries": {
                "test_1": MAX_INCONCLUSIVE_RETRIES,
                "test_2": 0,
            },
        }
        result = await inconclusive_retry_node(state)

        # test_1 exhausted, test_2 retryable
        assert "test_2" in result["tests_to_execute"]
        assert "test_1" not in result["tests_to_execute"]

    @pytest.mark.asyncio
    async def test_only_inconclusive_tests_processed(self):
        """Tests with PASS or FAIL verdicts are ignored."""
        state = {
            "run_id": "run-1",
            "evaluation_results": {
                "test_pass": {"verdict": "PASS"},
                "test_fail": {"verdict": "FAIL"},
                "test_flaky": {"verdict": "INCONCLUSIVE"},
            },
            "inconclusive_retries": {},
        }
        result = await inconclusive_retry_node(state)

        assert "test_flaky" in result["inconclusive_retries"]
        assert "test_pass" not in result["inconclusive_retries"]
        assert "test_fail" not in result["inconclusive_retries"]
        assert result["tests_to_execute"] == ["test_flaky"]

    @pytest.mark.asyncio
    async def test_no_inconclusive_tests(self):
        state = {
            "run_id": "run-1",
            "evaluation_results": {
                "test_1": {"verdict": "PASS"},
            },
            "inconclusive_retries": {},
        }
        result = await inconclusive_retry_node(state)

        assert result["inconclusive_retries"] == {}
        assert result["tests_to_execute"] is None

    @pytest.mark.asyncio
    async def test_status_remains_executing(self):
        state = {
            "run_id": "run-1",
            "evaluation_results": {
                "test_1": {"verdict": "INCONCLUSIVE"},
            },
            "inconclusive_retries": {},
        }
        result = await inconclusive_retry_node(state)
        assert result["status"] == "executing"
