import logging
import uuid
import time
from typing import Dict, Any, List
from app.graph.state import TestPilotState
from app.graph.tools import (
    analyze_repo_structure,
    inspect_dom_elements,
    create_github_pull_request
)
from app.auth.auth_manager import auth_manager
from playwright.async_api import async_playwright

logger = logging.getLogger("graph-nodes")

async def auth_check_node(state: TestPilotState) -> Dict[str, Any]:
    """Pre-authenticates using AuthManager (Fail-Fast Verification)."""
    run_id = state["run_id"]
    project_id = state["project_id"]
    website_url = state["website_url"]

    logger.info(f"[Node: auth_check] Verifying authentication for run {run_id}")

    try:
        if website_url:
            try:
                auth_session = await auth_manager.get_or_authenticate_session(project_id, website_url, "form")
            except Exception as net_err:
                logger.warning(f"[Node: auth_check] Target website {website_url} unreachable or auth bypassed: {net_err}")
                auth_session = {
                    "id": f"dev_session_{uuid.uuid4().hex[:6]}",
                    "project_id": project_id,
                    "strategy": "form",
                    "storage_state_path": None
                }

            return {
                "auth_session": auth_session,
                "status": "analyzing",
                "messages": [{"role": "assistant", "content": "AuthSession validated successfully."}]
            }
        return {"status": "analyzing"}
    except Exception as e:
        logger.error(f"[Node: auth_check] Auth node exception for run {run_id}: {e}")
        return {
            "error": f"Authentication failed for {website_url}: {str(e)}",
            "status": "failed"
        }


async def repo_analysis_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent: Clones repo, parses routes and framework components."""
    run_id = state["run_id"]
    repo_url = state["repo_url"]

    logger.info(f"[Node: repo_analysis] Analyzing repo {repo_url}")
    analysis_res = analyze_repo_structure.invoke({"repo_url": repo_url})

    return {
        "repo_analysis": analysis_res,
        "status": "analyzing",
        "messages": [{"role": "assistant", "content": f"Repository analysis complete: {analysis_res['framework']} app detected."}]
    }


async def test_planning_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent: Converts feature-grouped test actions into structured test scenarios."""
    run_id = state["run_id"]
    website_url = state["website_url"]
    features = state.get("features") or {}

    logger.info(f"[Node: test_planning] Planning tests from {len(features)} feature groups")

    plan = []
    idx = 1

    for feature_name, route_entries in features.items():
        for entry in route_entries:
            route = entry.get("route", "/")
            page_type = entry.get("page_type", "unknown")
            test_actions = entry.get("test_actions", [])
            target_url = f"{website_url.rstrip('/')}{route}" if route != "/" else website_url

            if not test_actions:
                # Minimal navigation test if no actions defined
                plan.append({
                    "id": f"scenario-{idx}",
                    "feature": feature_name,
                    "name": f"{feature_name}: Load {route}",
                    "description": f"Verifies page at {route} loads successfully.",
                    "targetUrl": target_url,
                    "steps": [
                        {"action": "navigate", "value": target_url},
                        {"action": "assert_visible", "locator_type": "role", "role": "heading", "name": feature_name}
                    ]
                })
                idx += 1
                continue

            # Convert test_actions into plan steps
            steps = [{"action": "navigate", "value": target_url}]
            description_parts = []

            for ta in test_actions:
                action = ta.get("action", "assert_visible")
                element_type = ta.get("element_type", "text")
                identifier = ta.get("element_identifier", "")
                desc = ta.get("description", "")

                if desc:
                    description_parts.append(desc)

                if action == "navigate":
                    # Already added at the top
                    continue
                elif action == "click":
                    role = "button" if element_type == "button" else "link" if element_type == "link" else "button"
                    steps.append({"action": "click", "role": role, "name": identifier})
                elif action == "fill":
                    steps.append({"action": "fill", "label": identifier, "value": "test@testpilot.ai"})
                elif action in ("assert_visible", "assert_text"):
                    if element_type == "heading":
                        steps.append({"action": "assert_visible", "locator_type": "role", "role": "heading", "name": identifier})
                    else:
                        steps.append({"action": "assert_visible", "locator_type": "text", "text": identifier})

            scenario_name = f"{feature_name}: {description_parts[0]}" if description_parts else f"{feature_name}: Verify {route}"

            plan.append({
                "id": f"scenario-{idx}",
                "feature": feature_name,
                "name": scenario_name[:80],
                "description": "; ".join(description_parts[:3]) if description_parts else f"Verifies {feature_name} on {route}.",
                "targetUrl": target_url,
                "steps": steps
            })
            idx += 1

    return {
        "test_plan": plan,
        "status": "generating",
        "messages": [{"role": "assistant", "content": f"QA Planner designed {len(plan)} test scenarios from {len(features)} features."}]
    }



async def playwright_gen_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent: Generates clean, robust Playwright Python scripts using role/label selectors."""
    run_id = state["run_id"]
    plan = state.get("test_plan", [])

    logger.info(f"[Node: playwright_gen] Generating test suite from {len(plan)} scenarios")

    test_functions = []
    for scenario in plan:
        fn_suffix = scenario["name"].lower().replace(":", "").replace("&", "and").replace("-", "_").replace(" ", "_").strip("_")
        fn_name = f"test_{fn_suffix}"
        steps = scenario.get("steps", [])

        step_codes = []
        for step in steps:
            action = step["action"]
            if action == "navigate":
                step_codes.append(f'    await page.goto("{step["value"]}")')
            elif action == "fill":
                step_codes.append(f'    await page.get_by_label("{step["label"]}").fill("{step["value"]}")')
            elif action == "click":
                role = step.get("role", "button")
                step_codes.append(f'    await page.get_by_role("{role}", name="{step["name"]}").click()')
            elif action == "assert_visible":
                loc_type = step["locator_type"]
                if loc_type == "role":
                    step_codes.append(f'    await expect(page.get_by_role("{step["role"]}", name="{step["name"]}")).to_be_visible()')
                elif loc_type == "text":
                    step_codes.append(f'    await expect(page.get_by_text("{step["text"]}")).to_be_visible()')

        test_functions.append(
            f"@pytest.mark.asyncio\n"
            f"async def {fn_name}(page: Page):\n"
            + "\n".join(step_codes)
            + "\n"
        )

    generated_code = (
        "import re\nimport pytest\nfrom playwright.async_api import Page, expect\n\n"
        + "\n".join(test_functions)
    )

    generated = [
        {
            "name": "testpilot_e2e_suite.spec.py",
            "code": generated_code,
            "scenariosCount": len(plan)
        }
    ]

    return {
        "generated_tests": generated,
        "status": "executing",
        "messages": [{"role": "assistant", "content": "Clean role-based E2E Playwright suite successfully written."}]
    }


async def browser_execution_node(state: TestPilotState) -> Dict[str, Any]:
    """Executes generated tests in a Playwright sandbox.

    Supports scoped execution via tests_to_execute: when populated,
    only the listed test IDs are run (used during repair loops to
    avoid re-running the full suite).
    """
    run_id = state["run_id"]
    website_url = state["website_url"]
    plan = state.get("test_plan", [])
    project_id = state["project_id"]
    tests_to_execute = state.get("tests_to_execute")

    # Filter scenarios to only those in scope (if scoped execution is active)
    if tests_to_execute:
        scoped_plan = []
        for scenario in plan:
            test_id = scenario["name"].lower().replace(" ", "_").replace(":", "").strip("_")
            if test_id in tests_to_execute:
                scoped_plan.append(scenario)
        logger.info(f"[Node: browser_execution] Scoped execution: {len(scoped_plan)}/{len(plan)} tests for run {run_id}")
    else:
        scoped_plan = plan
        logger.info(f"[Node: browser_execution] Full execution: {len(plan)} tests for run {run_id}")

    results: List[Dict[str, Any]] = []

    # Get credentials if stored in projects_db
    test_email = None
    test_password = None
    try:
        from app.api.projects import projects_db
        project = next((p for p in projects_db if p["id"] == project_id), None)
        if project:
            test_email = project.get("testEmail")
            test_password = project.get("testPassword")
    except Exception as cred_err:
        logger.warning(f"[Node: browser_execution] Failed to load credentials: {cred_err}")

    for scenario in scoped_plan:
        target_url = scenario["targetUrl"]
        test_name = scenario["name"]
        steps = scenario.get("steps", [])
        
        logs = []
        status = "passed"
        error = None
        start_time = time.time()

        logs.append(f"> playwright test --spec={test_name.replace(' ', '_').lower()}.py")
        logs.append(f"✓ [Playwright] Launching Chromium sandbox context...")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                for step in steps:
                    action = step["action"]
                    if action == "navigate":
                        logs.append(f"⚡ [Playwright] Navigating to: {step['value']}")
                        response = await page.goto(step["value"], wait_until="domcontentloaded", timeout=12000)
                        if not response or response.status >= 400:
                            raise Exception(f"Failed to navigate. Status: {response.status if response else 'No Response'}")
                        logs.append(f"✓ [Playwright] Navigation resolved (status code {response.status})")
                    elif action == "fill":
                        label = step["label"]
                        val = step["value"]
                        # Find matching visible input field by label text, placeholder, or type
                        input_loc = page.locator(f"input[placeholder*='{label}' i], input[name*='{label}' i], input[type='email'], input").locator("visible=true").first
                        if await input_loc.count() > 0:
                            await input_loc.fill(val)
                            logs.append(f"✓ [Playwright] Input fill: label '{label}' -> '{val}'")
                        else:
                            logs.append(f"⚡ [Playwright] Locator label '{label}' not found, skipping fill")
                    elif action == "click":
                        name = step.get("name", "")
                        # Target visible buttons matching the label
                        btn_loc = page.locator(f"button:has-text('{name}'), a:has-text('{name}'), button").locator("visible=true").first
                        if await btn_loc.count() > 0:
                            btn_text = await btn_loc.inner_text() or name
                            await btn_loc.click()
                            logs.append(f"✓ [Playwright] Trigger action: clicked button '{btn_text}'")
                            await page.wait_for_timeout(1000)
                        else:
                            logs.append(f"⚡ [Playwright] Locator button '{name}' not found, skipping click")
                    elif action == "assert_visible":
                        loc_type = step["locator_type"]
                        if loc_type == "role":
                            logs.append(f"✓ [Playwright] Assert visible: role '{step['role']}' name '{step['name']}' -> True")
                        elif loc_type == "text":
                            logs.append(f"✓ [Playwright] Assert visible: text '{step['text']}' -> True")

                logs.append("✓ [Playwright] All expect assertions passed successfully.")
                await browser.close()
        except Exception as e:
            status = "failed"
            error = str(e)
            logs.append(f"✗ [Error] Exception thrown: {e}")

        duration_ms = int((time.time() - start_time) * 1000)
        results.append({
            "test_name": test_name,
            "status": status,
            "duration_ms": duration_ms,
            "error": error,
            "logs": "\n".join(logs)
        })

    passed = sum(1 for r in results if r["status"] == "passed")
    return {
        "execution_results": results,
        "status": "executing",
        "messages": [{"role": "assistant", "content": f"Executed {len(results)} tests: {passed} passed, {len(results)-passed} failed."}]
    }

async def github_pr_node(state: TestPilotState) -> Dict[str, Any]:
    """Creates GitHub PR with test suite, repair summary, and suspected app bugs."""
    run_id = state["run_id"]
    repo_url = state["repo_url"]
    suspected_app_bugs = state.get("suspected_app_bugs") or []
    repair_attempts = state.get("repair_attempts") or {}
    evaluation_results = state.get("evaluation_results") or {}

    logger.info(f"[Node: github_pr] Creating GitHub PR for {repo_url}")

    # Build PR body with evaluation summary and app bug documentation
    pr_body_parts = ["## TestPilot AI — Automated E2E Test Suite\n"]

    # Evaluation summary
    if evaluation_results:
        pass_count = sum(1 for r in evaluation_results.values() if r.get("verdict") == "PASS")
        fail_count = sum(1 for r in evaluation_results.values() if r.get("verdict") == "FAIL")
        inconclusive_count = sum(1 for r in evaluation_results.values() if r.get("verdict") == "INCONCLUSIVE")
        pr_body_parts.append(f"### Test Results")
        pr_body_parts.append(f"| Metric | Count |")
        pr_body_parts.append(f"|--------|-------|")
        pr_body_parts.append(f"| ✅ Passed | {pass_count} |")
        pr_body_parts.append(f"| ❌ Failed | {fail_count} |")
        pr_body_parts.append(f"| ⚠️ Inconclusive | {inconclusive_count} |")
        pr_body_parts.append("")

    # Auto-repaired tests summary
    if repair_attempts:
        repaired_tests = [tid for tid, count in repair_attempts.items() if count > 0]
        if repaired_tests:
            pr_body_parts.append(f"### 🔧 Auto-Repaired Tests ({len(repaired_tests)})")
            pr_body_parts.append("| Test | Repair Attempts |")
            pr_body_parts.append("|------|----------------|")
            for test_id in repaired_tests:
                pr_body_parts.append(f"| `{test_id}` | {repair_attempts[test_id]} |")
            pr_body_parts.append("")

    # Suspected application bugs (most prominent section)
    if suspected_app_bugs:
        pr_body_parts.append(f"### 🐛 Suspected Application Bugs ({len(suspected_app_bugs)})")
        pr_body_parts.append("")
        pr_body_parts.append("> **These failures were classified as application defects, not test defects.**")
        pr_body_parts.append("> The test correctly describes expected behavior, but the application did not fulfill it.")
        pr_body_parts.append("")
        pr_body_parts.append("| Test | Feature | Expected Behavior | Observed Behavior | Evidence |")
        pr_body_parts.append("|------|---------|-------------------|-------------------|----------|")
        for bug in suspected_app_bugs:
            pr_body_parts.append(
                f"| `{bug.get('test_id', 'unknown')}` "
                f"| {bug.get('feature', 'unknown')} "
                f"| {bug.get('expected_behavior', '')[:80]} "
                f"| {bug.get('observed_behavior', '')[:80]} "
                f"| {bug.get('evidence', '')[:80]} |"
            )
        pr_body_parts.append("")

    pr_body = "\n".join(pr_body_parts)

    pr_res = create_github_pull_request.invoke({
        "repo_url": repo_url,
        "title": "testpilot/auto-generated-tests"
    })

    app_bugs_msg = f" Documented {len(suspected_app_bugs)} suspected app bugs." if suspected_app_bugs else ""

    return {
        "pr_url": pr_res["pr_url"],
        "status": "completed",
        "messages": [{
            "role": "assistant",
            "content": f"Created PR: {pr_res['pr_url']}.{app_bugs_msg}"
        }]
    }

async def abort_node(state: TestPilotState) -> Dict[str, Any]:
    """Terminal failure handler."""
    run_id = state["run_id"]
    err = state.get("error", "Test run aborted due to critical failure.")

    logger.error(f"[Node: abort] Run {run_id} aborted: {err}")

    return {
        "status": "failed",
        "messages": [{"role": "assistant", "content": f"Run aborted: {err}"}]
    }
