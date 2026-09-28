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

# Patterns indicating HTTP 429 rate limiting. These are flagged by
# browser_execution (structured fields) OR appear verbatim in the output.
# A rate limit is a transient/environment condition: it must NEVER be treated
# as a selector failure, test defect, or application bug.
_RATE_LIMIT_PATTERNS = [
    "429",
    "too many requests",
    "rate limit",
    "rate-limit",
    "ratelimit",
    "retry-after",
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


def _rate_limit_retry_after(test_result: Dict[str, Any]) -> int:
    """Returns the Retry-After (seconds) advertised by the server, if any.

    Accepts either a numeric seconds value or an HTTP-date; unparseable
    values fall back to 0 (caller then uses bounded exponential backoff).
    """
    raw = test_result.get("retry_after")
    if raw in (None, ""):
        return 0
    try:
        return max(0, int(float(raw)))
    except (TypeError, ValueError):
        # HTTP-date form is rare here; fall back to bounded backoff.
        return 0


def _is_rate_limited(test_result: Dict[str, Any], error: str, logs: str) -> bool:
    """Detects an HTTP 429 rate-limit condition.

    Prefers browser_execution's structured signal (``rate_limited`` /
    ``http_status``). Falls back to unambiguous textual patterns so that a
    rate-limit condition is still recognised when only logs are available.
    """
    if test_result.get("rate_limited"):
        return True
    if str(test_result.get("http_status") or "") == "429":
        return True
    # Unambiguous phrases may appear in either error or logs.
    combined = f"{error} {logs}"
    if any(p in combined for p in ("too many requests", "rate limit", "rate-limit", "ratelimit", "retry-after")):
        return True
    # Bare "429" only counts when it is in the error field (avoids matching
    # stray digits in unrelated log lines / durations).
    return "429" in error


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

    # Pre-execution verification failure: live_verify refused to schedule this
    # test (fail-closed). It was never executed and is NOT a test failure nor an
    # application bug - it is a TestPilot validation failure.
    if status == "not_executed":
        return {
            "verdict": "NOT_EXECUTED",
            "category": "verification_failure",
            "reason": "Test was never executed: pre-execution selector verification failed.",
            "evidence": (error or "FAILED_VERIFICATION")[:300],
        }

    # Zero-duration test -> never executed
    if duration_ms == 0 and status != "passed":
        return {
            "verdict": "INCONCLUSIVE",
            "category": "never_executed",
            "reason": "Test reported zero duration, likely never ran.",
            "evidence": error or "No execution data"
        }

    # HTTP 429 rate limiting -> transient/environment condition, NOT a test
    # defect. Classified BEFORE selector patterns so a rate-limit alert page
    # can never be reinterpreted as a broken selector or an application bug.
    if status != "passed" and _is_rate_limited(test_result, error, logs):
        retry_after = _rate_limit_retry_after(test_result)
        return {
            "verdict": "INCONCLUSIVE",
            "category": "rate_limited",
            "reason": (
                "HTTP 429 rate limit encountered; treating as a transient "
                "environment condition and retrying with backoff."
            ),
            "evidence": (error or logs)[:300],
            "retry_after": retry_after,
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
