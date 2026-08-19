import logging
import asyncio
from typing import Dict, Any, Optional, Callable
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.graph.state import TestPilotState
from app.graph.nodes import (
    auth_check_node,
    repo_analysis_node,
    test_planning_node,
    playwright_gen_node,
    browser_execution_node,
    github_pr_node,
    abort_node
)
from app.graph.page_inspection_node import page_inspection_node
from app.graph.code_analysis_node import code_analysis_node
from app.graph.app_understanding_node import app_understanding_node
from app.graph.feature_segregation_node import feature_segregation_node
from app.graph.test_evaluation_node import test_evaluation_node
from app.graph.failure_analysis_node import failure_analysis_node
from app.graph.test_repair_node import test_repair_node
from app.graph.inconclusive_retry_node import inconclusive_retry_node
from app.graph.edges import (
    route_after_auth,
    route_after_evaluation,
    route_after_failure_analysis,
    route_after_inconclusive_retry,
)

logger = logging.getLogger("graph-pipeline")

# Generous margin to accommodate nested repair cycles.
# 5 failed tests x 3 attempts x 4 nodes/cycle = 60 theoretical super-steps.
# The actual termination limit is controlled by deterministic counters
# in the routing edges; this is only a catastrophic circuit breaker.
GRAPH_RECURSION_LIMIT = 150


def build_pipeline():
    """Assembles and compiles the LangGraph StateGraph pipeline with feedback loops."""
    graph = StateGraph(TestPilotState)

    # --- Register Nodes ---
    # Linear path (generation)
    graph.add_node("auth_check", auth_check_node)
    graph.add_node("repo_analysis", repo_analysis_node)
    graph.add_node("page_inspection", page_inspection_node)
    graph.add_node("code_analysis", code_analysis_node)
    graph.add_node("app_understanding", app_understanding_node)
    graph.add_node("feature_segregation", feature_segregation_node)
    graph.add_node("test_planning", test_planning_node)
    graph.add_node("playwright_gen", playwright_gen_node)
    graph.add_node("browser_execution", browser_execution_node)
    graph.add_node("abort", abort_node)

    # Cyclical path (evaluation -> repair)
    graph.add_node("test_evaluation", test_evaluation_node)
    graph.add_node("failure_analysis", failure_analysis_node)
    graph.add_node("test_repair", test_repair_node)
    graph.add_node("inconclusive_retry", inconclusive_retry_node)
    graph.add_node("github_pr", github_pr_node)

    # --- Wire Edges ---
    # Linear path
    graph.set_entry_point("auth_check")
    graph.add_conditional_edges("auth_check", route_after_auth)
    graph.add_edge("repo_analysis", "page_inspection")
    graph.add_edge("page_inspection", "code_analysis")
    graph.add_edge("code_analysis", "app_understanding")
    graph.add_edge("app_understanding", "feature_segregation")
    graph.add_edge("feature_segregation", "test_planning")
    graph.add_edge("test_planning", "playwright_gen")
    graph.add_edge("playwright_gen", "browser_execution")

    # Feedback loop: execution -> evaluation -> analysis/retry -> repair -> execution
    graph.add_edge("browser_execution", "test_evaluation")

    graph.add_conditional_edges("test_evaluation", route_after_evaluation, {
        "github_pr": "github_pr",
        "failure_analysis": "failure_analysis",
        "inconclusive_retry": "inconclusive_retry",
    })

    graph.add_conditional_edges("failure_analysis", route_after_failure_analysis, {
        "test_repair": "test_repair",
        "github_pr": "github_pr",
    })

    # Loop back: test_repair → browser_execution (scoped re-execution)
    graph.add_edge("test_repair", "browser_execution")

    graph.add_conditional_edges("inconclusive_retry", route_after_inconclusive_retry, {
        "browser_execution": "browser_execution",
        "github_pr": "github_pr",
    })

    # Terminal
    graph.add_edge("github_pr", END)
    graph.add_edge("abort", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)

pipeline_app = build_pipeline()

# Maps node names to frontend-visible status strings.
# Feedback loop nodes map to "executing" to maintain backward
# compatibility with the existing frontend polling contract.
NODE_STATUS_MAP = {
    "auth_check": "repo_analysis",
    "repo_analysis": "repo_analysis",
    "page_inspection": "page_inspection",
    "code_analysis": "code_analysis",
    "app_understanding": "app_understanding",
    "feature_segregation": "app_understanding",
    "test_planning": "test_planning",
    "playwright_gen": "playwright_gen",
    "browser_execution": "execution",
    "test_evaluation": "executing",
    "failure_analysis": "executing",
    "test_repair": "executing",
    "inconclusive_retry": "executing",
    "github_pr": "execution",
    "abort": "failed",
}

async def run_pipeline(
    project_id: str,
    run_id: str,
    website_url: str,
    repo_url: str,
    on_status_change: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Invokes the LangGraph StateGraph pipeline with real-time status updates."""
    logger.info(f"Starting LangGraph pipeline for project={project_id}, run={run_id}")

    initial_state: TestPilotState = {
        "run_id": run_id,
        "project_id": project_id,
        "repo_url": repo_url,
        "website_url": website_url,
        "status": "analyzing",
        "error": None,
        "auth_session": None,
        "repo_analysis": None,
        "page_inspections": None,
        "code_analysis": None,
        "app_understanding": None,
        "features": None,
        "test_plan_doc": None,
        "test_plan": None,
        "generated_tests": None,
        "execution_results": None,
        "pr_url": None,
        "messages": [],
        # Feedback loop fields (initialized empty)
        "evaluation_results": {},
        "failure_analyses": {},
        "repair_attempts": {},
        "inconclusive_retries": {},
        "repaired_tests": {},
        "suspected_app_bugs": [],
        "tests_to_execute": None,
    }

    config = {
        "configurable": {"thread_id": run_id},
        "recursion_limit": GRAPH_RECURSION_LIMIT,
    }

    # Stream node-by-node to emit status updates between steps
    final_state = initial_state
    async for event in pipeline_app.astream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            status = NODE_STATUS_MAP.get(node_name, "executing")
            logger.info(f"[Pipeline] Node '{node_name}' completed → status='{status}'")
            if on_status_change:
                on_status_change(status)
            # Brief yield to let the event loop serve polling requests
            await asyncio.sleep(1.5)

    # Get the final checkpointed state
    final_snapshot = await pipeline_app.aget_state(config)
    final_state = dict(final_snapshot.values)

    return final_state
