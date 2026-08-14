import logging
from typing import Dict, Any, List
from app.graph.state import TestPilotState

logger = logging.getLogger("graph-inconclusive-retry")

MAX_INCONCLUSIVE_RETRIES = 2


async def inconclusive_retry_node(state: TestPilotState) -> Dict[str, Any]:
    """Retries inconclusive tests deterministically, without LLM.

    For infrastructure failures (DNS, timeout, service down) there is
    no test code to diagnose. This node simply increments the retry
    counter and schedules scoped re-execution of the affected tests.
    """
    run_id = state["run_id"]
    evaluation_results = state.get("evaluation_results") or {}
    current_retries = state.get("inconclusive_retries") or {}

    # Filter tests with INCONCLUSIVE verdict
    inconclusive_tests = [
        test_id
        for test_id, evaluation in evaluation_results.items()
        if evaluation.get("verdict") == "INCONCLUSIVE"
    ]

    logger.info(
        "Processing inconclusive test retries",
        extra={"run_id": run_id, "inconclusive_count": len(inconclusive_tests)}
    )

    new_retries: Dict[str, int] = {}
    retryable_ids: List[str] = []
    exhausted_ids: List[str] = []

    for test_id in inconclusive_tests:
        retry_count = current_retries.get(test_id, 0) + 1
        new_retries[test_id] = retry_count

        if retry_count <= MAX_INCONCLUSIVE_RETRIES:
            retryable_ids.append(test_id)
            logger.info(
                "Scheduling inconclusive test for retry",
                extra={
                    "run_id": run_id,
                    "test_id": test_id,
                    "retry_attempt": retry_count,
                    "max_retries": MAX_INCONCLUSIVE_RETRIES,
                }
            )
        else:
            exhausted_ids.append(test_id)
            logger.info(
                "Inconclusive test retries exhausted, marking as environment flaky",
                extra={"run_id": run_id, "test_id": test_id, "total_retries": retry_count}
            )

    summary_parts = []
    if retryable_ids:
        summary_parts.append(f"{len(retryable_ids)} tests scheduled for retry")
    if exhausted_ids:
        summary_parts.append(f"{len(exhausted_ids)} tests marked as environment-flaky (retries exhausted)")

    summary = "Inconclusive retry: " + ", ".join(summary_parts) if summary_parts else "No inconclusive tests to process."

    return {
        "inconclusive_retries": new_retries,
        "tests_to_execute": retryable_ids if retryable_ids else None,
        "status": "executing",
        "messages": [{"role": "assistant", "content": summary}],
    }
