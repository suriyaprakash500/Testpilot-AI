import logging
from app.graph.state import TestPilotState

logger = logging.getLogger("graph-edges")

MAX_REPAIR_ATTEMPTS = 3
MAX_INCONCLUSIVE_RETRIES = 2


def route_after_auth(state: TestPilotState) -> str:
    """Conditional edge after auth verification."""
    if state.get("error"):
        logger.warning(f"Routing to abort due to auth error: {state.get('error')}")
        return "abort"
    return "repo_analysis"


def route_after_evaluation(state: TestPilotState) -> str:
    """Conditional edge after test evaluation.

    ALL PASS -> github_pr
    HAS FAILURES -> failure_analysis
    INCONCLUSIVE ONLY -> inconclusive_retry
    """
    evaluation_results = state.get("evaluation_results") or {}

    if not evaluation_results:
        logger.info("No evaluation results found, routing to github_pr")
        return "github_pr"

    verdicts = [r.get("verdict") for r in evaluation_results.values()]

    has_failures = "FAIL" in verdicts
    has_inconclusive = "INCONCLUSIVE" in verdicts
    all_pass = all(v == "PASS" for v in verdicts)

    if all_pass:
        logger.info("All tests passed, routing to github_pr")
        return "github_pr"

    # Failures take priority over inconclusive results
    if has_failures:
        logger.info(
            "Failed tests detected, routing to failure_analysis",
            extra={"fail_count": verdicts.count("FAIL")}
        )
        return "failure_analysis"

    if has_inconclusive:
        logger.info(
            "Inconclusive tests detected, routing to inconclusive_retry",
            extra={"inconclusive_count": verdicts.count("INCONCLUSIVE")}
        )
        return "inconclusive_retry"

    logger.info("No actionable verdicts, routing to github_pr")
    return "github_pr"


def route_after_failure_analysis(state: TestPilotState) -> str:
    """Conditional edge after failure analysis.

    Repairable tests with retries left -> test_repair
    Only app bugs or retries exhausted -> github_pr
    """
    failure_analyses = state.get("failure_analyses") or {}
    repair_attempts = state.get("repair_attempts") or {}

    repairable_tests = [
        test_id
        for test_id, analysis in failure_analyses.items()
        if analysis.get("root_cause") in {"selector_wrong", "timing_issue", "test_assumption_wrong"}
        and repair_attempts.get(test_id, 0) < MAX_REPAIR_ATTEMPTS
    ]

    if repairable_tests:
        logger.info(
            "Repairable tests found, routing to test_repair",
            extra={"repairable_count": len(repairable_tests)}
        )
        return "test_repair"

    logger.info("No repairable tests (all app bugs or retries exhausted), routing to github_pr")
    return "github_pr"


def route_after_inconclusive_retry(state: TestPilotState) -> str:
    """Conditional edge after inconclusive retry.

    Retries remaining -> browser_execution
    Retries exhausted -> github_pr
    """
    inconclusive_retries = state.get("inconclusive_retries") or {}

    has_retries_left = any(
        count < MAX_INCONCLUSIVE_RETRIES
        for count in inconclusive_retries.values()
    )

    if has_retries_left:
        logger.info("Inconclusive retries remaining, routing back to browser_execution")
        return "browser_execution"

    logger.info("Inconclusive retries exhausted, routing to github_pr")
    return "github_pr"
