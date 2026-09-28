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

from unittest.mock import AsyncMock, patch

from app.graph.inconclusive_retry_node import (
    _compute_backoff,
    BASE_BACKOFF_SECONDS,
    MAX_BACKOFF_SECONDS,
)


class TestComputeBackoff:

    def test_retry_after_takes_priority(self):
        assert _compute_backoff(1, 12) == 12.0

    def test_exponential_backoff_grows(self):
        assert _compute_backoff(1, 0) == BASE_BACKOFF_SECONDS
        assert _compute_backoff(2, 0) == BASE_BACKOFF_SECONDS * 2
        assert _compute_backoff(3, 0) == BASE_BACKOFF_SECONDS * 4

    def test_backoff_is_capped(self):
        assert _compute_backoff(20, 0) == MAX_BACKOFF_SECONDS
        assert _compute_backoff(1, 9999) == MAX_BACKOFF_SECONDS

    def test_zero_retry_count_is_safe(self):
        assert _compute_backoff(0, 0) == BASE_BACKOFF_SECONDS


class TestRateLimitedRetry:

    @pytest.mark.asyncio
    async def test_rate_limited_test_is_scheduled_for_retry(self):
        with patch("app.graph.inconclusive_retry_node.asyncio.sleep", new=AsyncMock()) as sleeper:
            state = {
                "run_id": "run-1",
                "evaluation_results": {
                    "t1": {"verdict": "INCONCLUSIVE", "category": "rate_limited", "retry_after": 0},
                },
                "inconclusive_retries": {},
            }
            result = await inconclusive_retry_node(state)

        assert result["tests_to_execute"] == ["t1"]
        assert result["inconclusive_retries"]["t1"] == 1
        # Bounded backoff slept once before retrying.
        sleeper.assert_awaited_once_with(BASE_BACKOFF_SECONDS)

    @pytest.mark.asyncio
    async def test_retry_after_is_honoured_for_backoff(self):
        with patch("app.graph.inconclusive_retry_node.asyncio.sleep", new=AsyncMock()) as sleeper:
            state = {
                "run_id": "run-1",
                "evaluation_results": {
                    "t1": {"verdict": "INCONCLUSIVE", "category": "rate_limited", "retry_after": 5},
                },
                "inconclusive_retries": {},
            }
            await inconclusive_retry_node(state)

        sleeper.assert_awaited_once_with(5.0)

    @pytest.mark.asyncio
    async def test_rate_limited_retries_are_bounded(self):
        with patch("app.graph.inconclusive_retry_node.asyncio.sleep", new=AsyncMock()) as sleeper:
            state = {
                "run_id": "run-1",
                "evaluation_results": {
                    "t1": {"verdict": "INCONCLUSIVE", "category": "rate_limited", "retry_after": 0},
                },
                "inconclusive_retries": {"t1": MAX_INCONCLUSIVE_RETRIES},
            }
            result = await inconclusive_retry_node(state)

        assert result["tests_to_execute"] is None
        # Exhausted -> no backoff wait performed.
        sleeper.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_rate_limited_inconclusive_does_not_sleep(self):
        with patch("app.graph.inconclusive_retry_node.asyncio.sleep", new=AsyncMock()) as sleeper:
            state = {
                "run_id": "run-1",
                "evaluation_results": {
                    "t1": {"verdict": "INCONCLUSIVE", "category": "environment_error"},
                },
                "inconclusive_retries": {},
            }
            result = await inconclusive_retry_node(state)

        assert result["tests_to_execute"] == ["t1"]
        sleeper.assert_not_awaited()
