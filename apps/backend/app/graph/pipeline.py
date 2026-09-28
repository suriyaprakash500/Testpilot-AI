import logging
import asyncio
import time
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
from app.graph.app_feature_analysis_node import app_feature_analysis_node
from app.graph.test_evaluation_node import test_evaluation_node
from app.graph.failure_analysis_node import failure_analysis_node
from app.graph.test_repair_node import test_repair_node
from app.graph.inconclusive_retry_node import inconclusive_retry_node
from app.graph.live_verify_node import live_verify_node
from app.graph.edges import (
    route_after_auth,
    route_after_evaluation,
    route_after_failure_analysis,
    route_after_inconclusive_retry,
)

logger = logging.getLogger("graph-pipeline")


def _normalize_test_id(name: str) -> str:
    """Normalizes a test name into the state key used across the graph.

    Mirrors ``app.graph.nodes._normalize_test_id`` so per-test failure data
    (keyed by this ID) lines up with execution results.
    """
    return (name or "").lower().replace(" ", "_").replace(":", "").strip("_")

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
    graph.add_node("app_feature_analysis", app_feature_analysis_node)
    graph.add_node("test_planning", test_planning_node)
    graph.add_node("playwright_gen", playwright_gen_node)
    graph.add_node("live_verify", live_verify_node)
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
    graph.add_edge("page_inspection", "app_feature_analysis")
    graph.add_edge("app_feature_analysis", "test_planning")
    graph.add_edge("test_planning", "playwright_gen")
    # Live Verify: validate generated selectors against the live DOM
    # before any full execution (pre-delivery grounding).
    graph.add_edge("playwright_gen", "live_verify")
    graph.add_edge("live_verify", "browser_execution")

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
# Feedback-loop nodes emit DISTINCT statuses so the UI can visualize
# evaluation / triage / repair / PR phases instead of a frozen "executing".
NODE_STATUS_MAP = {
    "auth_check": "repo_analysis",
    "repo_analysis": "repo_analysis",
    "page_inspection": "page_inspection",
    "app_feature_analysis": "app_understanding",
    "test_planning": "test_planning",
    "playwright_gen": "playwright_gen",
    "live_verify": "live_verify",
    "browser_execution": "execution",
    "test_evaluation": "evaluating",
    "failure_analysis": "analyzing_failures",
    "test_repair": "repairing",
    "inconclusive_retry": "retrying",
    "github_pr": "creating_pr",
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
        # Live Verify (pre-execution selector validation)
        "live_verifications": {},
        # Repair integrity (Fix 4/5): immutable original intents + verdicts
        "test_intents": {},
        "repair_statuses": {},
    }

    config = {
        "configurable": {"thread_id": run_id},
        "recursion_limit": GRAPH_RECURSION_LIMIT,
    }

    # Stream node-by-node to emit status updates between steps
    final_state = initial_state
    timeline: list = []
    started_at = time.time()
    first_pass_stats: Optional[Dict[str, int]] = None
    # Per-test snapshot of the FIRST execution cycle (before any repair re-runs).
    # Repaired tests ultimately pass, so the final execution_results no longer
    # carry the original failure - we must capture it here.
    first_pass_results: Dict[str, dict] = {}

    async for event in pipeline_app.astream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            status = NODE_STATUS_MAP.get(node_name, "executing")
            logger.info(f"[Pipeline] Node '{node_name}' completed -> status='{status}'")
            timeline.append({
                "node": node_name,
                "status": status,
                "elapsedSec": round(time.time() - started_at, 1),
            })
            # Capture first-pass execution stats (before any repair re-runs)
            if node_name == "browser_execution" and first_pass_stats is None:
                exec_results = (node_output or {}).get("execution_results") or []
                first_pass_stats = {
                    "passed": sum(1 for r in exec_results if r.get("status") == "passed"),
                    # Only genuine failures count here; not-executed
                    # (fail-closed live-verify) results are NOT failures.
                    "failed": sum(1 for r in exec_results if r.get("status") == "failed"),
                }
                first_pass_results = {
                    _normalize_test_id(r.get("test_name", "")): {
                        "status": r.get("status"),
                        "error": r.get("error"),
                    }
                    for r in exec_results
                }
            if on_status_change:
                on_status_change(status)
            # Brief yield to let the event loop serve polling requests
            await asyncio.sleep(1.5)

    # Get the final checkpointed state
    final_snapshot = await pipeline_app.aget_state(config)
    final_state = dict(final_snapshot.values)

    # Attach non-checkpointed reporting data. These keys are consumed by the
    # API layer (test_runs router) to persist run summaries; they are NOT part
    # of TestPilotState and never flow back into the graph.
    final_results = final_state.get("execution_results") or []
    repair_attempts = final_state.get("repair_attempts") or {}
    live_verifications = final_state.get("live_verifications") or {}
    final_state["run_summary"] = {
        "plannedTotal": len(final_state.get("test_plan") or []),
        "passedFirstPass": (first_pass_stats or {}).get("passed"),
        "failedFirstPass": (first_pass_stats or {}).get("failed"),
        "passedFinal": sum(1 for r in final_results if r.get("status") == "passed"),
        "failedFinal": sum(1 for r in final_results if r.get("status") == "failed"),
        # Fail-closed live-verify outcomes: never-executed, never failures.
        "notExecutedFinal": sum(1 for r in final_results if r.get("status") == "not_executed"),
        "inconclusiveFinal": sum(
            1 for r in final_results
            if r.get("status") not in ("passed", "failed", "not_executed")
        ),
        "repairedCount": sum(1 for v in repair_attempts.values() if v > 0),
        "appBugCount": len(final_state.get("suspected_app_bugs") or []),
        "retryCount": sum(1 for v in (final_state.get("inconclusive_retries") or {}).values() if v > 0),
        "liveVerifiedCount": sum(1 for v in live_verifications.values() if v.get("status") == "verified"),
        "liveCorrectedCount": sum(1 for v in live_verifications.values() if v.get("status") == "corrected"),
        "liveUnverifiedCount": sum(1 for v in live_verifications.values() if v.get("status") == "unverified"),
    }

    # Per-case failure/repair provenance. Final execution_results alone cannot
    # tell the UI WHICH cases failed on the first pass or WHY, because repaired
    # tests are re-run and end up passing. We merge the first-pass snapshot with
    # the feedback-loop analyses so each persisted test case carries its own
    # failure story (root cause + LLM "mention").
    failure_analyses = final_state.get("failure_analyses") or {}
    repair_statuses = final_state.get("repair_statuses") or {}
    case_details: Dict[str, dict] = {}
    for result in final_results:
        tid = _normalize_test_id(result.get("test_name", ""))
        first = first_pass_results.get(tid) or {}
        analysis = failure_analyses.get(tid) or {}
        live = live_verifications.get(tid) or {}
        case_details[tid] = {
            "failedFirstPass": 1 if (first and first.get("status") == "failed") else 0,
            "firstPassError": first.get("error"),
            "rootCause": analysis.get("root_cause"),
            "analysisNote": analysis.get("explanation"),
            "repairAttempts": repair_attempts.get(tid, 0),
            "repairStatus": (repair_statuses.get(tid) or {}).get("status"),
            "liveStatus": live.get("status"),
            "verificationStatus": live.get("verification_status"),
            "executionStatus": live.get("execution_status"),
        }
    final_state["case_details"] = case_details
    final_state["timeline"] = timeline

    return final_state
