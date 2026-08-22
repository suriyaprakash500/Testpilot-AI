import logging
import json
from typing import Dict, Any, List
from app.graph.state import TestPilotState
from app.config import settings

logger = logging.getLogger("graph-test-repair")

MAX_REPAIR_ATTEMPTS = 3


def _find_test_code_by_id(test_id: str, generated_tests: list) -> str:
    """Extracts the test code from the generated suite file containing the test_id."""
    if not generated_tests:
        return ""
    # The full suite code is in the first generated file
    full_code = generated_tests[0].get("code", "")
    return full_code


def _find_execution_result(test_id: str, execution_results: list) -> dict:
    """Finds the execution result matching a test_id."""
    for result in execution_results:
        name = result.get("test_name", "")
        normalized = name.lower().replace(" ", "_").replace(":", "").strip("_")
        if normalized == test_id:
            return result
    return {}


def _find_page_inspection(test_id: str, test_plan: list, inspections: list, website_url: str) -> dict:
    """Finds the relevant page inspection for a test."""
    for entry in test_plan:
        name = entry.get("name", "")
        normalized = name.lower().replace(" ", "_").replace(":", "").strip("_")
        if normalized == test_id:
            for step in entry.get("steps", []):
                if step.get("action") == "navigate":
                    nav_url = step.get("value", "")
                    if website_url and nav_url.startswith(website_url):
                        route = nav_url[len(website_url.rstrip("/")):] or "/"
                        for insp in inspections:
                            if insp.get("route") == route:
                                return insp
            break
    return inspections[0] if inspections else {}


def _build_repair_prompt(
    test_id: str,
    test_code: str,
    failure_analysis: dict,
    execution_result: dict,
    page_inspection: dict,
) -> str:
    """Builds the prompt for the LLM to repair the test."""
    lines = []

    lines.append(f"Test ID: {test_id}")
    lines.append(f"Root cause: {failure_analysis.get('root_cause', 'unknown')}")
    lines.append(f"Failure explanation: {failure_analysis.get('explanation', '')}")

    if execution_result.get("error"):
        lines.append(f"\nExecution error:\n{execution_result['error']}")

    if execution_result.get("logs"):
        lines.append(f"\nExecution logs:\n{execution_result['logs'][:1500]}")

    lines.append(f"\nOriginal test code:\n```python\n{test_code}\n```")

    if page_inspection:
        buttons = [b.get("text", "") for b in page_inspection.get("buttons", []) if b.get("text")]
        inputs_info = []
        for inp in page_inspection.get("inputs", []):
            label = inp.get("label") or inp.get("placeholder") or inp.get("name") or inp.get("type", "")
            inputs_info.append(f"{label} [{inp.get('type', 'text')}]")
        headings = [h.get("text", "") for h in page_inspection.get("headings", []) if h.get("text")]

        lines.append(f"\nActual page elements (ground truth):")
        if headings:
            lines.append(f"  Headings: {headings[:6]}")
        if buttons:
            lines.append(f"  Buttons: {buttons[:10]}")
        if inputs_info:
            lines.append(f"  Inputs: {inputs_info[:8]}")

        # Prefer Accessibility Tree over raw HTML
        aom = page_inspection.get("accessibility_tree")
        if aom:
            lines.append(f"\nAccessibility Tree (semantic page structure):\n{aom[:2000]}")

    return "\n".join(lines)


async def _llm_repair_test(repair_context: str, root_cause: str) -> list:
    """Sends the repair context to the LLM to generate corrected test steps.

    Returns a list of step dicts in the format consumed by browser_execution_node:
    [{"action": "navigate", "value": "..."}, {"action": "assert_visible", ...}]
    """
    from app.llm import get_llm

    llm = get_llm(temperature=0.2)

    repair_strategies = {
        "selector_wrong": (
            "The test locator does not match the actual DOM. Fix the selector to match "
            "the actual element text, role, or label shown in the page elements above. "
            "Use ONLY elements that actually exist in the ground truth data."
        ),
        "timing_issue": (
            "The element exists but was not ready when the assertion ran. Add a "
            "'wait_for_load' step before the failing interaction, or increase the "
            "assertion timeout."
        ),
        "test_assumption_wrong": (
            "The test logic is incorrect. Fix the navigation flow, expected values, "
            "or interaction sequence to match the actual application behavior shown "
            "in the execution logs and page elements."
        ),
    }

    strategy = repair_strategies.get(root_cause, repair_strategies["selector_wrong"])

    prompt = f"""You are a senior QA engineer. A generated E2E test has failed, and you must repair it.

REPAIR STRATEGY: {strategy}

=== FAILURE CONTEXT ===
{repair_context}
=== END CONTEXT ===

Return a JSON array of repaired test steps. Each step is an object with one of these formats:

1. Navigate: {{"action": "navigate", "value": "https://example.com/page"}}
2. Click: {{"action": "click", "role": "button" | "link", "name": "Button Text", "first": true}} OR {{"action": "click", "role": "button", "name": "Button Text", "parent_selector": ".card", "parent_text": "Title"}}
3. Fill: {{"action": "fill", "label": "Input Label", "value": "test value"}}
4. Assert visible by role: {{"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Page Title", "first": true}}
5. Assert visible by text: {{"action": "assert_visible", "locator_type": "text", "text": "Some text on page", "first": true}}

RULES:
1. Fix ONLY the specific issue identified by the root cause.
2. If the error was a Playwright strict mode violation (multiple elements matched), scope to a parent container (`"parent_selector"`, `"parent_text"`) or set `"first": true` / `"nth": <index>`.
3. Use ONLY elements that exist in the "Actual page elements" section above.
4. Do NOT invent selectors or element names that were not in the evidence.
5. Keep the original test intent â€” do NOT remove assertions to force a pass.

Return ONLY the JSON array. No markdown fences, no explanation."""

    response = await llm.ainvoke(prompt)
    content = response.content.strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

    try:
        steps = json.loads(content)
        if isinstance(steps, list) and len(steps) > 0:
            return steps
        return None
    except json.JSONDecodeError:
        logger.warning(
            "LLM returned non-JSON for test repair",
            extra={"raw_response": content[:200]}
        )
        return None


async def test_repair_node(state: TestPilotState) -> Dict[str, Any]:
    """Repairs tests classified as test defects (not application bugs).

    Receives failed tests with root cause analysis, generates corrected
    code using the LLM, and sets tests_to_execute so that only the
    repaired tests are re-executed in the next cycle.
    """
    run_id = state["run_id"]
    failure_analyses = state.get("failure_analyses") or {}
    repair_attempts = state.get("repair_attempts") or {}
    generated_tests = state.get("generated_tests") or []
    execution_results = state.get("execution_results") or []
    test_plan = state.get("test_plan") or []
    inspections = state.get("page_inspections") or []
    website_url = state.get("website_url", "")

    # Filter repairable tests that have not exhausted attempts
    repairable_tests = {
        test_id: analysis
        for test_id, analysis in failure_analyses.items()
        if analysis.get("repairable")
        and analysis.get("root_cause") in {"selector_wrong", "timing_issue", "test_assumption_wrong"}
        and repair_attempts.get(test_id, 0) < MAX_REPAIR_ATTEMPTS
    }

    logger.info(
        "Repairing failed tests",
        extra={"run_id": run_id, "repairable_count": len(repairable_tests)}
    )

    new_repair_attempts: Dict[str, int] = {}
    new_repaired_tests: Dict[str, list] = {}
    repaired_ids: List[str] = []

    for test_id, analysis in repairable_tests.items():
        current_attempts = repair_attempts.get(test_id, 0)
        new_attempt_count = current_attempts + 1

        logger.info(
            "Repairing test",
            extra={
                "run_id": run_id,
                "test_id": test_id,
                "root_cause": analysis.get("root_cause"),
                "attempt": new_attempt_count,
            }
        )

        test_code = _find_test_code_by_id(test_id, generated_tests)
        exec_result = _find_execution_result(test_id, execution_results)
        page_insp = _find_page_inspection(test_id, test_plan, inspections, website_url)

        repair_context = _build_repair_prompt(
            test_id, test_code, analysis, exec_result, page_insp
        )

        try:
            repaired_steps = await _llm_repair_test(
                repair_context, analysis.get("root_cause", "selector_wrong")
            )

            if repaired_steps:
                new_repaired_tests[test_id] = repaired_steps
                repaired_ids.append(test_id)
                logger.info(
                    "Test repaired successfully",
                    extra={
                        "run_id": run_id,
                        "test_id": test_id,
                        "attempt": new_attempt_count,
                        "repaired_steps_count": len(repaired_steps),
                    }
                )
            else:
                logger.warning(
                    "LLM returned insufficient repair data",
                    extra={"run_id": run_id, "test_id": test_id}
                )
        except Exception as e:
            logger.error(
                "Test repair failed",
                extra={"run_id": run_id, "test_id": test_id, "error": str(e)}
            )

        new_repair_attempts[test_id] = new_attempt_count

    summary = (
        f"Repaired {len(repaired_ids)} tests. "
        f"Setting scoped re-execution for: {repaired_ids}"
    )

    result: Dict[str, Any] = {
        "repair_attempts": new_repair_attempts,
        "tests_to_execute": repaired_ids if repaired_ids else None,
        "status": "executing",
        "messages": [{"role": "assistant", "content": summary}],
    }

    if new_repaired_tests:
        result["repaired_tests"] = new_repaired_tests

    return result

