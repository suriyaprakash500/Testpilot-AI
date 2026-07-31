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
    """Routes to github_pr after execution completes."""
    return "github_pr"
