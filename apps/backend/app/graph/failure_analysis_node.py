import logging
import json
from typing import Dict, Any, List
from app.graph.state import TestPilotState
from app.config import settings

logger = logging.getLogger("graph-failure-analysis")

# Root cause categories that are repairable test defects
REPAIRABLE_ROOT_CAUSES = {"selector_wrong", "timing_issue", "test_assumption_wrong"}


def _build_failure_context(
    test_id: str,
    evaluation: dict,
    execution_result: dict,
    test_plan_entry: dict,
    page_inspection: dict,
) -> str:
    """Builds the failure context string to send to the LLM."""
    lines = []

    lines.append(f"Test ID: {test_id}")
    lines.append(f"Evaluation verdict: {evaluation.get('verdict')}")
    lines.append(f"Evaluation category: {evaluation.get('category')}")
    lines.append(f"Evaluation reason: {evaluation.get('reason')}")

    if evaluation.get("evidence"):
        lines.append(f"Evidence: {evaluation['evidence']}")

    if execution_result.get("error"):
        lines.append(f"\nExecution error:\n{execution_result['error']}")

    if execution_result.get("logs"):
        lines.append(f"\nExecution logs:\n{execution_result['logs'][:1500]}")

    if test_plan_entry:
        lines.append(f"\nOriginal test plan:")
        lines.append(f"  Feature: {test_plan_entry.get('feature', 'unknown')}")
        lines.append(f"  Name: {test_plan_entry.get('name', 'unknown')}")
        lines.append(f"  Description: {test_plan_entry.get('description', '')}")
        steps = test_plan_entry.get("steps", [])
        if steps:
            lines.append(f"  Steps: {json.dumps(steps[:5], indent=2)}")

    if page_inspection:
        route = page_inspection.get("route", "/")
        buttons = [b.get("text", "") for b in page_inspection.get("buttons", []) if b.get("text")]
        inputs_info = []
        for inp in page_inspection.get("inputs", []):
            label = inp.get("label") or inp.get("placeholder") or inp.get("name") or inp.get("type", "")
            inputs_info.append(label)
        headings = [h.get("text", "") for h in page_inspection.get("headings", []) if h.get("text")]

        lines.append(f"\nPage inspection for route '{route}':")
        if headings:
            lines.append(f"  Headings: {headings[:6]}")
        if buttons:
            lines.append(f"  Buttons: {buttons[:10]}")
        if inputs_info:
            lines.append(f"  Inputs: {inputs_info[:8]}")

        # Use Accessibility Tree if available
        aom = page_inspection.get("accessibility_tree")
        if aom:
            lines.append(f"\nAccessibility Tree (AOM):\n{aom[:2000]}")

    return "\n".join(lines)


def _find_execution_result(test_id: str, execution_results: list) -> dict:
    """Finds the execution result matching a test_id."""
    for result in execution_results:
        name = result.get("test_name", "")
        normalized = name.lower().replace(" ", "_").replace(":", "").strip("_")
        if normalized == test_id:
            return result
    return {}


def _find_test_plan_entry(test_id: str, test_plan: list) -> dict:
    """Finds the test plan entry matching a test_id."""
    for entry in test_plan:
        name = entry.get("name", "")
        normalized = name.lower().replace(" ", "_").replace(":", "").strip("_")
        if normalized == test_id:
            return entry
    return {}


def _find_page_inspection(route: str, inspections: list) -> dict:
    """Finds the page inspection matching a route."""
    for insp in inspections:
        if insp.get("route") == route:
            return insp
    return inspections[0] if inspections else {}


async def _llm_analyze_failure(context: str) -> Dict[str, Any]:
    """Sends the failure context to the LLM for root cause classification."""
    from langchain_groq import ChatGroq

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.groq_api_key,
        temperature=0.1,
    )

    prompt = f"""You are a senior QA engineer analyzing a failed end-to-end Playwright test.

Your task: determine the ROOT CAUSE of the failure.

=== FAILURE CONTEXT ===
{context}
=== END CONTEXT ===

Classify the root cause into exactly ONE of these categories:

1. "selector_wrong" — The generated locator (CSS selector, role, text) does not match the actual DOM element. The element exists but with a different name, role, or identifier.
2. "timing_issue" — The element exists but was not ready when the assertion ran. The test needs explicit waits or the page loads asynchronously.
3. "test_assumption_wrong" — The test logic is incorrect: wrong navigation flow, wrong expected value, or wrong sequence of interactions.
4. "application_bug" — The application itself is broken. The test correctly describes the expected behavior, but the app does not fulfill it (state not updated, API error, missing feature, visual regression).

CRITICAL RULE: Only classify as "application_bug" if the test is logically correct and the application genuinely fails to meet the expected behavior. Do NOT classify infrastructure/env issues as app bugs.

Return ONLY a JSON object with these exact keys:
- "root_cause": one of the 4 categories above
- "explanation": 1-2 sentences explaining why you chose this category, referencing specific evidence
- "repairable": true if root_cause is selector_wrong, timing_issue, or test_assumption_wrong; false if application_bug

No markdown fences, no extra text."""

    response = await llm.ainvoke(prompt)
    content = response.content.strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning(
            "LLM returned non-JSON for failure analysis, using fallback",
            extra={"raw_response": content[:200]}
        )
        return None


async def failure_analysis_node(state: TestPilotState) -> Dict[str, Any]:
    """Analyzes the root cause of each test with a FAIL verdict.

    Classifies each failure as a test defect (repairable) or an
    application bug (not repairable), using the LLM with execution
    context, test plan, and page inspection data.
    """
    run_id = state["run_id"]
    evaluation_results = state.get("evaluation_results") or {}
    execution_results = state.get("execution_results") or []
    test_plan = state.get("test_plan") or []
    inspections = state.get("page_inspections") or []

    # Filter only tests with FAIL verdict
    failed_tests = {
        test_id: evaluation
        for test_id, evaluation in evaluation_results.items()
        if evaluation.get("verdict") == "FAIL"
    }

    logger.info(
        "Analyzing failure root causes",
        extra={"run_id": run_id, "failed_count": len(failed_tests)}
    )

    failure_analyses: Dict[str, dict] = {}
    new_app_bugs: List[dict] = []

    for test_id, evaluation in failed_tests.items():
        exec_result = _find_execution_result(test_id, execution_results)
        plan_entry = _find_test_plan_entry(test_id, test_plan)

        # Find page inspection for the test's route
        route = "/"
        if plan_entry:
            for step in plan_entry.get("steps", []):
                if step.get("action") == "navigate":
                    nav_url = step.get("value", "")
                    website_url = state.get("website_url", "")
                    if website_url and nav_url.startswith(website_url):
                        route = nav_url[len(website_url.rstrip("/")):] or "/"
                    break
        page_insp = _find_page_inspection(route, inspections)

        context = _build_failure_context(
            test_id, evaluation, exec_result, plan_entry, page_insp
        )

        analysis = None
        try:
            analysis = await _llm_analyze_failure(context)
        except Exception as e:
            logger.warning(
                "LLM failure analysis failed, defaulting to selector_wrong",
                extra={"run_id": run_id, "test_id": test_id, "error": str(e)}
            )

        # Deterministic fallback if the LLM fails
        if not analysis:
            analysis = {
                "root_cause": "selector_wrong",
                "explanation": "LLM analysis unavailable. Defaulting to selector_wrong based on evaluation category.",
                "repairable": True,
            }

        failure_analyses[test_id] = analysis

        # Record suspected application bugs
        if analysis.get("root_cause") == "application_bug":
            new_app_bugs.append({
                "test_id": test_id,
                "test_name": plan_entry.get("name", test_id),
                "feature": plan_entry.get("feature", "unknown"),
                "expected_behavior": plan_entry.get("description", ""),
                "observed_behavior": evaluation.get("reason", ""),
                "evidence": analysis.get("explanation", ""),
                "execution_error": exec_result.get("error", ""),
            })

        logger.info(
            "Failure analyzed",
            extra={
                "run_id": run_id,
                "test_id": test_id,
                "root_cause": analysis.get("root_cause"),
                "repairable": analysis.get("repairable"),
            }
        )

    repairable_count = sum(
        1 for a in failure_analyses.values() if a.get("repairable")
    )
    app_bug_count = len(new_app_bugs)

    summary = (
        f"Failure analysis complete: {repairable_count} repairable test defects, "
        f"{app_bug_count} suspected application bugs."
    )

    result: Dict[str, Any] = {
        "failure_analyses": failure_analyses,
        "status": "executing",
        "messages": [{"role": "assistant", "content": summary}],
    }

    # Only add suspected_app_bugs if there are new ones (operator.add concatenates)
    if new_app_bugs:
        result["suspected_app_bugs"] = new_app_bugs

    return result
