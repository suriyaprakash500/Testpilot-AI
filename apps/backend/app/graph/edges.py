import logging
from app.graph.state import TestPilotState

logger = logging.getLogger("graph-edges")

def route_after_auth(state: TestPilotState) -> str:
    """Conditional edge after auth verification."""
    if state.get("error"):
        logger.warning(f"Routing to abort due to auth error: {state.get('error')}")
        return "abort"
    return "repo_analysis"

def route_after_execution(state: TestPilotState) -> str:
    """Conditional edge after test execution."""
    results = state.get("execution_results", [])
    failures = [r for r in results if r.get("status") == "failed"]

    if not failures:
        logger.info("All tests passed! Routing to github_pr.")
        return "github_pr"

    retry_count = state.get("retry_count", 0)
    if retry_count >= 2:
        logger.warning(f"Reached max retries ({retry_count}). Routing to github_pr with partial results.")
        return "github_pr"

    logger.info(f"Detected {len(failures)} failures. Routing to self-healing failure_analysis (Retry #{retry_count + 1}).")
    return "failure_analysis"
