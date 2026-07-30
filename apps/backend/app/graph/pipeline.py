import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.graph.state import TestPilotState
from app.graph.nodes import (
    auth_check_node,
    repo_analysis_node,
    test_planning_node,
    playwright_gen_node,
    browser_execution_node,
    failure_analysis_node,
    github_pr_node,
    abort_node
)
from app.graph.edges import route_after_auth, route_after_execution

logger = logging.getLogger("graph-pipeline")

def build_pipeline():
    """Assembles and compiles the LangGraph StateGraph pipeline."""
    graph = StateGraph(TestPilotState)

    # 1. Register Nodes
    graph.add_node("auth_check", auth_check_node)
    graph.add_node("repo_analysis", repo_analysis_node)
    graph.add_node("test_planning", test_planning_node)
    graph.add_node("playwright_gen", playwright_gen_node)
    graph.add_node("browser_execution", browser_execution_node)
    graph.add_node("failure_analysis", failure_analysis_node)
    graph.add_node("github_pr", github_pr_node)
    graph.add_node("abort", abort_node)

    # 2. Wire Edges & Transitions
    graph.set_entry_point("auth_check")
    graph.add_conditional_edges("auth_check", route_after_auth)
    graph.add_edge("repo_analysis", "test_planning")
    graph.add_edge("test_planning", "playwright_gen")
    graph.add_edge("playwright_gen", "browser_execution")
    graph.add_conditional_edges("browser_execution", route_after_execution)
    graph.add_edge("failure_analysis", "browser_execution")
    graph.add_edge("github_pr", END)
    graph.add_edge("abort", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)

pipeline_app = build_pipeline()

async def run_pipeline(project_id: str, run_id: str, website_url: str, repo_url: str) -> Dict[str, Any]:
    """Invokes the LangGraph StateGraph pipeline end-to-end."""
    logger.info(f"Starting LangGraph pipeline for project={project_id}, run={run_id}")

    initial_state: TestPilotState = {
        "run_id": run_id,
        "project_id": project_id,
        "repo_url": repo_url,
        "website_url": website_url,
        "status": "analyzing",
        "error": None,
        "retry_count": 0,
        "auth_session": None,
        "repo_analysis": None,
        "test_plan": None,
        "generated_tests": None,
        "execution_results": None,
        "failure_analysis": None,
        "pr_url": None,
        "messages": []
    }

    config = {"configurable": {"thread_id": run_id}}
    final_state = await pipeline_app.ainvoke(initial_state, config=config)
    return final_state
