import logging
from typing import Dict, Any, List
from app.graph.state import TestPilotState

logger = logging.getLogger("graph-test-evaluation")


# Keywords indicating infrastructure/environment failure.
# NOTE: deliberately SPECIFIC signals only — a generic "timeout" is NOT here,
# because Playwright interaction timeouts ("Timeout ... exceeded waiting for
# locator(...)") are usually repairable test defects, not environment flakes.
_ENVIRONMENT_ERROR_PATTERNS = [
    "net::err_",
    "dns_probe",
    "econnrefused",
    "connection refused",
    "navigation timeout",
    "goto timeout",
    "err_connection_reset",
    "err_name_not_resolved",
    "service unavailable",
    "502 bad gateway",
    "503 service",
]

# Patterns indicating a Playwright selector/element error.
# NOTE: these are checked BEFORE environment patterns so that errors which
# contain BOTH kinds of text (e.g. "Locator.click: Timeout 30000ms exceeded.
# waiting for locator(...)") are correctly classified as repairable FAILs.
_SELECTOR_ERROR_PATTERNS = [
    "waiting for selector",
    "waiting for locator",
    "waiting for get_by_",
    "locator resolved to",
    "strict mode violation",
    "no element matches",
    "element(s) not found",
    "element is not visible",
    "element is not attached",
]


def _classify_test_result(test_result: Dict[str, Any]) -> Dict[str, Any]:
    """Classifies a single test result deterministically.

    Analyzes status, error, logs, and duration to determine
    whether the result is PASS, FAIL, or INCONCLUSIVE without LLM.
    """
    status = test_result.get("status", "unknown")
    error = (test_result.get("error") or "").lower()
    logs = (test_result.get("logs") or "").lower()
    duration_ms = test_result.get("duration_ms", 0)
    combined_output = f"{error} {logs}"

    # Test passed with no errors
    if status == "passed" and not error:
        return {
            "verdict": "PASS",
            "category": "all_assertions_passed",
            "reason": "All assertions passed successfully.",
            "evidence": ""
        }

        # Zero-duration test -> never executed
    if duration_ms == 0 and status != "passed":
        return {
            "verdict": "INCONCLUSIVE",
            "category": "never_executed",
            "reason": "Test reported zero duration, likely never ran.",
            "evidence": error or "No execution data"
        }

        # Playwright selector/element error (checked FIRST: interaction timeouts
    # that mention locators are repairable defects, not environment flakes).
    # Matched against the ERROR FIELD ONLY so stale locator-wait text in old
    # log lines cannot hijack a genuine navigation/environment timeout.
    for pattern in _SELECTOR_ERROR_PATTERNS:
        if pattern in error:
            return {
                "verdict": "FAIL",
                "category": "selector_failure",
                "reason": f"Playwright selector error: '{pattern}' found in output.",
                "evidence": error[:300] if error else logs[:300]
            }

    # Infrastructure/environment failure (DNS, connection, navigation timeout)
    for pattern in _ENVIRONMENT_ERROR_PATTERNS:
        if pattern in combined_output:
            return {
                "verdict": "INCONCLUSIVE",
                "category": "environment_error",
                "reason": f"Environment/infrastructure failure detected: '{pattern}' found in output.",
                "evidence": error[:300] if error else logs[:300]
            }

    # Generic failure with error message
    if status == "failed" and error:
        return {
            "verdict": "FAIL",
            "category": "assertion_failure",
            "reason": f"Test failed with error: {error[:200]}",
            "evidence": error[:300]
        }

    # Generic failure without a clear error message
    if status == "failed":
        return {
            "verdict": "FAIL",
            "category": "unknown_failure",
            "reason": "Test reported failure without a classifiable error pattern.",
            "evidence": logs[:300]
        }

    # Default case for unexpected statuses
    return {
        "verdict": "INCONCLUSIVE",
        "category": "unclassified",
        "reason": f"Test finished with unrecognized status: '{status}'.",
        "evidence": error[:200] if error else ""
    }


async def test_evaluation_node(state: TestPilotState) -> Dict[str, Any]:
    """Evaluates execution results and classifies each test as PASS/FAIL/INCONCLUSIVE.

    Uses deterministic checks first (HTTP status, error patterns, duration).
    Reserves LLM fallback only for semantically ambiguous cases.
    """
    run_id = state["run_id"]
    execution_results = state.get("execution_results") or []

    logger.info(
        "Evaluating execution results",
        extra={"run_id": run_id, "test_count": len(execution_results)}
    )

    evaluation_results: Dict[str, dict] = {}
    pass_count = 0
    fail_count = 0
    inconclusive_count = 0

    for result in execution_results:
        test_name = result.get("test_name", "unknown_test")
        # Normalize ID for use as state key
        test_id = test_name.lower().replace(" ", "_").replace(":", "").strip("_")

        classification = _classify_test_result(result)
        evaluation_results[test_id] = classification

        verdict = classification["verdict"]
        if verdict == "PASS":
            pass_count += 1
        elif verdict == "FAIL":
            fail_count += 1
        else:
            inconclusive_count += 1

        logger.info(
            "Test evaluated",
            extra={
                "run_id": run_id,
                "test_id": test_id,
                "verdict": verdict,
                "category": classification["category"]
            }
        )

    summary = (
        f"Evaluation complete: {pass_count} passed, "
        f"{fail_count} failed, {inconclusive_count} inconclusive "
        f"out of {len(execution_results)} tests."
    )

    return {
        "evaluation_results": evaluation_results,
        "status": "executing",
        "messages": [{"role": "assistant", "content": summary}]
    }
