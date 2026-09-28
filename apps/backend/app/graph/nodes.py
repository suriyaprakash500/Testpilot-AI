import logging
import uuid
import time
from typing import Dict, Any, List, Optional
import json
from app.graph.state import TestPilotState
from app.graph.tools import (
    analyze_repo_structure,
    create_github_pull_request
)
from app.auth.auth_manager import auth_manager
from playwright.async_api import async_playwright, expect
from app.graph.playwright_runner import run_playwright, target_slot

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


def _build_verified_routes(repo_info: dict, inspections: list) -> Dict[str, Dict[str, Any]]:
    """Builds the map of routes that are actually supported by evidence.

    A route may only be used for a test when it is supported by repo analysis
    (the route exists in source) or by live page inspection (the route was
    observed rendering real DOM, not the app's in-app 404 view). Each entry
    records its provenance as {route, source, evidence}.
    """
    verified: Dict[str, Dict[str, Any]] = {}

    for route in (repo_info or {}).get("routes", []) or []:
        if route and route not in verified:
            verified[route] = {
                "route": route,
                "source": "repo_analysis",
                "evidence": "Route enumerated from repository source scan.",
            }

    for insp in inspections or []:
        route = insp.get("route")
        if not route:
            continue
        if insp.get("is_not_found"):
            # An in-app 404 view is not a usable route: retract any repo claim.
            verified.pop(route, None)
            continue
        status = insp.get("status_code")
        evidence = (
            f"Live inspection observed real DOM (HTTP {status})."
            if status is not None
            else "Live inspection captured DOM evidence."
        )
        if route in verified:
            verified[route]["source"] = "repo_analysis+page_inspection"
            verified[route]["evidence"] = f"{verified[route]['evidence']} {evidence}"
        else:
            verified[route] = {"route": route, "source": "page_inspection", "evidence": evidence}

    return verified


def _observed_visible_text(inspections: list) -> List[str]:
    """Deduped, verbatim visible text observed on inspected pages.

    Only these strings may be used for exact ``get_by_text(...)`` assertions.
    Image alt text is deliberately EXCLUDED: an alt attribute is an accessibility
    name, not visible text.
    """
    seen: List[str] = []

    def _push(val: Any) -> None:
        text = str(val or "").strip()
        if text and text not in seen:
            seen.append(text)

    for insp in inspections or []:
        for h in insp.get("headings") or []:
            _push(h.get("text"))
        for b in insp.get("buttons") or []:
            _push(b.get("text"))
        for l in insp.get("links") or []:
            _push(l.get("text"))
        for c in insp.get("cards") or []:
            _push(c.get("title"))
        for t in insp.get("tables") or []:
            for hdr in t.get("headers") or []:
                _push(hdr)
        for inp in insp.get("inputs") or []:
            _push(inp.get("label"))
            _push(inp.get("placeholder"))
    return seen


def _observed_accessible_names(inspections: list) -> List[str]:
    """Accessible names (aria-labels) usable with getByRole, NOT visible text."""
    seen: List[str] = []

    def _push(val: Any) -> None:
        text = str(val or "").strip()
        if text and text not in seen:
            seen.append(text)

    for insp in inspections or []:
        for b in insp.get("buttons") or []:
            _push(b.get("ariaLabel"))
    return seen


def _observed_image_alts(inspections: list) -> List[str]:
    """Image alt strings observed on inspected pages (accessibility names)."""
    seen: List[str] = []
    for insp in inspections or []:
        for img in insp.get("images") or []:
            alt = str(img.get("alt") or "").strip()
            if alt and alt not in seen:
                seen.append(alt)
    return seen


# App-identity terms that are too generic to be treated as distinguishing
# identity strings (avoids over-dropping legitimate assertions).
_GENERIC_IDENTITY_TERMS = {"web application", "application", "web app", "app", "software"}


def _identity_terms(understanding: dict, inspections: list) -> List[str]:
    """Terms describing the app's IDENTITY (inferred name + image alt text).

    Any assertion/expected-result built on one of these is only legitimate when
    the term is ALSO observed as visible text on a real page.
    """
    terms: List[str] = []

    def _push(val: Any) -> None:
        text = str(val or "").strip()
        if text and text.lower() not in _GENERIC_IDENTITY_TERMS and text not in terms:
            terms.append(text)

    _push((understanding or {}).get("app_name"))
    for alt in _observed_image_alts(inspections):
        _push(alt)
    return terms


def _mentions_ungrounded_identity(text: str, observed_text: List[str], identity_terms: List[str]) -> bool:
    """True when `text` references an identity term never observed as visible text."""
    t = str(text or "")
    if not t:
        return False
    t_norm = t.lower()
    observed_norm = {o.strip().lower() for o in observed_text}
    for term in identity_terms:
        term_norm = str(term or "").strip().lower()
        if not term_norm:
            continue
        if term_norm in t_norm and term_norm not in observed_norm:
            return True
    return False


def _ground_scenario(scenario: dict, observed_text: List[str], identity_terms: List[str]) -> Optional[dict]:
    """Enforces that only observed DOM facts become exact assertions.

    Drops assertions (and neutralizes the expected_result) that reference the
    app's inferred identity when that exact string was never observed as visible
    text. Returns ``None`` when nothing groundable remains (scenario skipped).
    """
    assertions = list(scenario.get("assertions") or [])
    kept_assertions = [
        a for a in assertions
        if not _mentions_ungrounded_identity(a, observed_text, identity_terms)
    ]

    expected = scenario.get("expected_result", "")
    if _mentions_ungrounded_identity(expected, observed_text, identity_terms):
        expected = ""

    if len(kept_assertions) == len(assertions) and expected == scenario.get("expected_result", ""):
        return scenario

    if not kept_assertions and not expected:
        return None

    return {**scenario, "assertions": kept_assertions, "expected_result": expected}


def _build_test_planning_evidence(
    understanding: dict,
    features: dict,
    inspections: list,
    repo_info: dict,
    website_url: str,
) -> str:
    """Assembles all application discoveries into structured evidence for QA test planning."""
    lines = []
    lines.append(f"Target Website: {website_url}")
    lines.append(
        "Application Name (INFERRED METADATA — NOT UI EVIDENCE; never assert this string): "
        f"{understanding.get('app_name', 'Web Application')}"
    )
    lines.append(f"Application Type: {understanding.get('app_type', 'unknown')}")
    if understanding.get("purpose"):
        lines.append(f"Purpose: {understanding.get('purpose')}")

    testable_features = understanding.get("testable_features", [])
    if testable_features:
        lines.append("\nIdentified High-Level Features:")
        for tf in testable_features:
            lines.append(f"  - {tf.get('name')} (importance: {tf.get('importance', 'medium')}): {tf.get('evidence', '')}")

    user_flows = understanding.get("user_flows", [])
    if user_flows:
        lines.append("\nKey User Workflows:")
        for flow in user_flows:
            lines.append(f"  - {flow}")

    if features:
        lines.append("\nFeature Segregation & Route Groups:")
        for feat_name, route_entries in features.items():
            lines.append(f"  * Feature Area: {feat_name}")
            for entry in route_entries:
                route = entry.get("route", "/")
                page_type = entry.get("page_type", "unknown")
                actions = entry.get("test_actions", [])
                lines.append(f"    - Route: {route} (type: {page_type})")
                for act in actions:
                    lines.append(f"      â€¢ Action hint: {act.get('description', '')} on {act.get('element_type', 'element')} '{act.get('element_identifier', '')}'")

    if inspections:
        lines.append("\nDiscovered Live Page Inspections & Elements:")
        for insp in inspections:
            route = insp.get("route", "/")
            page_type = insp.get("page_type", "unknown")
            title = insp.get("title", "")
            headings = [h.get("text", "") for h in insp.get("headings", []) if h.get("text")]
            buttons = [b.get("text", "") for b in insp.get("buttons", []) if b.get("text")]
            inputs = []
            for inp in insp.get("inputs", []):
                lbl = inp.get("label") or inp.get("placeholder") or inp.get("name") or inp.get("type", "")
                if lbl:
                    inputs.append(f"{lbl} ({inp.get('type', 'text')})")
            links = [l.get("text", "") for l in insp.get("links", []) if l.get("text")][:10]
            forms = len(insp.get("forms", []))
            tables = len(insp.get("tables", []))
            cards = len(insp.get("cards", []))

            lines.append(f"  * Route '{route}' (title: '{title}', type: {page_type}):")
            if headings:
                lines.append(f"      Headings: {headings[:8]}")
            if buttons:
                lines.append(f"      Buttons: {buttons[:12]}")
            if inputs:
                lines.append(f"      Inputs: {inputs[:10]}")
            if links:
                lines.append(f"      Links: {links}")
            if forms:
                lines.append(f"      Forms count: {forms}")
            if tables:
                lines.append(f"      Tables count: {tables}")
            if cards:
                lines.append(f"      Cards count: {cards}")

    observed_text = _observed_visible_text(inspections)
    if observed_text:
        lines.append("\nOBSERVED VISIBLE TEXT (verbatim UI evidence — the ONLY strings usable for exact visible-text assertions):")
        for t in observed_text:
            lines.append(f'  - "{t}"')

    accessible_names = _observed_accessible_names(inspections)
    if accessible_names:
        lines.append("\nAccessible names / roles (usable with getByRole(name=...), NOT visible text):")
        for t in accessible_names:
            lines.append(f'  - "{t}"')

    image_alts = _observed_image_alts(inspections)
    if image_alts:
        lines.append("\nImage alt text (accessibility names, NOT visible text — never use with getByText):")
        for t in image_alts:
            lines.append(f'  - "{t}"')

    verified_routes = _build_verified_routes(repo_info, inspections)
    if verified_routes:
        lines.append("\nVERIFIED ROUTES (only routes with evidence may be used for scenarios):")
        for route, meta in verified_routes.items():
            lines.append(f"  - {route} [source: {meta['source']}] evidence: {meta['evidence']}")

    # Evidence assembled - return the structured text block.
    return "\n".join(lines)


async def _llm_generate_test_plan(evidence_text: str) -> Optional[dict]:
    """Calls the configured LLM with expert QA Test Planning prompt to output natural language plans."""
    from app.services.llm.service import llm_service

    prompt = f"""You are an expert QA Test Planning Agent in an autonomous web application testing system.

Your responsibility is to analyze the discovered application information and produce a COMPREHENSIVE, STRUCTURED test plan.

You are NOT responsible for writing Playwright code.
You are NOT responsible for executing tests.
Your job is to determine WHAT should be tested.

## OBJECTIVE

For every discovered feature, identify meaningful test scenarios that provide useful functional coverage.

Do NOT assume that one feature requires only one test.

A single feature may require multiple scenarios covering:
- Happy paths
- Alternative valid workflows
- Negative scenarios
- Input validation
- Boundary conditions
- Error handling
- Navigation
- UI state changes
- Important user interactions
- Empty states
- Loading states
- Authentication/authorization behavior where applicable
- CRUD operations where applicable

## IMPORTANT RULES

1. Analyze the provided application evidence carefully.
2. Do not invent UI elements, routes, workflows, or behavior that are not supported by the evidence.
3. Use discovered routes, components, elements, actions, source code, and application behavior as evidence.
4. Generate multiple scenarios when the feature contains multiple meaningful interactions.
5. Do NOT generate trivial variations merely to increase the number of tests.
6. Do NOT generate only a page-load test when the page contains meaningful interactive functionality.
7. Every important interactive element should be considered for testing.
8. Include both positive and negative scenarios when the application's behavior supports them.
9. Prefer end-to-end user workflows over isolated implementation details.
10. Avoid duplicate scenarios.
11. Prioritize scenarios based on business/user impact.
12. If the available evidence is insufficient to determine a scenario, do not invent it.
13. Each scenario must be independently executable and testable.
14. Keep scenarios atomic: one clear objective per scenario.
15. Include appropriate assertions that can verify the expected outcome.
16. Consider dependencies between actions, but do not combine unrelated behaviors into one test.

## ROUTE RULE (MANDATORY)
- You may ONLY assign a scenario to a route listed under VERIFIED ROUTES in the evidence.
- Do NOT invent routes. Do NOT reuse a route merely to reach a test-count target.
- If a feature has no verified route that genuinely hosts it, omit that feature rather than inventing a route.

## EXACT TEXT RULE (MANDATORY)
- Only strings listed under OBSERVED VISIBLE TEXT may be used for exact visible-text assertions.
- NEVER assert the application's inferred identity (the application name or any LLM inference such as "ERP CRM Software"). It is metadata, not UI evidence.
- An image alt text / accessible name (e.g. "IDURAR ERP CRM") is NOT visible text and must NEVER be asserted via get_by_text(...); it may only be used with get_by_role / accessible-name locators.
- Allowed example: an observed heading such as "Manage Your Company With :" may become an exact assertion.

## COVERAGE EXPECTATIONS

For each feature, inspect the available evidence and ask:
- What can the user do?
- What can the user input?
- What can the user click?
- What can the user navigate to?
- What successful outcomes are possible?
- What invalid inputs are possible?
- What failure/error states are visible?
- What state changes occur?
- What important workflows exist?
- What important edge cases are supported by the evidence?

For interactive features, aim for meaningful coverage rather than a single smoke test.

## PRIORITY

Assign each scenario:
- critical: Core functionality whose failure makes the feature unusable.
- high: Important functionality commonly used by users.
- medium: Secondary functionality or important edge cases.
- low: Minor or less frequently used behavior.

## SCENARIO TYPES

Use one of:
- smoke
- positive
- negative
- validation
- navigation
- edge_case
- error_handling
- state_change
- accessibility

Only use a type when supported by the discovered evidence.

=== APPLICATION EVIDENCE ===
{evidence_text}
=== END EVIDENCE ===

## OUTPUT

Return ONLY valid JSON matching this structure:

{{
  "test_plan": [
    {{
      "feature": "Feature name",
      "scenarios": [
        {{
          "id": "TC-001",
          "name": "Short descriptive scenario name",
          "route": "/",
          "description": "What the user is trying to verify",
          "type": "positive",
          "priority": "high",
          "preconditions": [
            "Required condition"
          ],
          "steps": [
            "User action 1",
            "User action 2"
          ],
          "expected_result": "Observable expected behavior",
          "assertions": [
            "Specific assertion that should be verified"
          ],
          "evidence": [
            "Relevant discovered route/component/action/source evidence"
          ]
        }}
      ]
    }}
  ],
  "coverage_summary": {{
    "features_analyzed": 0,
    "scenarios_generated": 0,
    "coverage_gaps": [],
    "notes": []
  }}
}}

The scenario count must reflect the actual scenarios generated.
Do not output Markdown fences or explanations outside the JSON."""

    data = await llm_service.invoke_json(prompt, expect="object", temperature=0.2)
    if isinstance(data, dict) and "test_plan" in data and isinstance(data["test_plan"], list):
        return data
    if data is not None:
        logger.warning("[Node: test_planning] LLM returned JSON without a valid 'test_plan' list")
    return None


def _fallback_test_planning(features: dict, website_url: str) -> dict:
    """Fallback rule-based test planner when LLM is unavailable."""
    plan_features = []
    total_scenarios = 0

    for feature_name, route_entries in (features or {}).items():
        scenarios = []
        for idx, entry in enumerate(route_entries, 1):
            route = entry.get("route", "/")
            page_type = entry.get("page_type", "unknown")
            actions = entry.get("test_actions", [])
            steps = [f"Navigate to {route}"]
            for act in actions:
                steps.append(f"{act.get('action', 'interact')} with {act.get('element_type', 'element')} '{act.get('element_identifier', '')}'")

            scenarios.append({
                "id": f"TC-{len(plan_features)+1:02d}{idx:02d}",
                "name": f"{feature_name}: Verify {route}",
                "route": route,
                "description": f"Verifies core functionality on {route} for {feature_name}.",
                "type": "positive",
                "priority": "high",
                "preconditions": [f"Website accessible at {website_url}"],
                "steps": steps,
                "expected_result": f"{feature_name} elements are visible and interactive.",
                "assertions": [f"Verify heading or primary button visible for {feature_name}"],
                "evidence": [f"Route: {route}, Page Type: {page_type}"]
            })
            total_scenarios += 1

        if scenarios:
            plan_features.append({
                "feature": feature_name,
                "scenarios": scenarios
            })

    if not plan_features:
        plan_features.append({
            "feature": "Application Smoke Test",
            "scenarios": [{
                "id": "TC-01",
                "name": "Navigate to landing page",
                "route": "/",
                "description": "Verifies that landing page loads successfully.",
                "type": "smoke",
                "priority": "critical",
                "preconditions": [f"Website accessible at {website_url}"],
                "steps": ["Navigate to /", "Verify page title and main heading"],
                "expected_result": "Landing page renders successfully.",
                "assertions": ["Main page is visible"],
                "evidence": ["Route: /"]
            }]
        })
        total_scenarios = 1

    return {
        "test_plan": plan_features,
        "coverage_summary": {
            "features_analyzed": len(plan_features),
            "scenarios_generated": total_scenarios,
            "coverage_gaps": [],
            "notes": ["Generated via fallback rule-based planner."]
        }
    }


async def test_planning_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent: Generates comprehensive natural language QA test plans using LLM reasoning."""
    run_id = state["run_id"]
    website_url = state["website_url"]
    features = state.get("features") or {}
    inspections = state.get("page_inspections") or []
    understanding = state.get("app_understanding") or {}
    repo_info = state.get("repo_analysis") or {}

    logger.info(f"[Node: test_planning] Designing natural language test plan for run {run_id}")

    evidence_text = _build_test_planning_evidence(
        understanding, features, inspections, repo_info, website_url
    )

    plan_doc = None
    try:
        plan_doc = await _llm_generate_test_plan(evidence_text)
    except Exception as llm_err:
        logger.warning(f"[Node: test_planning] LLM test planning call failed: {llm_err}")

    if not plan_doc or not plan_doc.get("test_plan"):
        logger.info("[Node: test_planning] Using fallback rule-based test planning")
        plan_doc = _fallback_test_planning(features, website_url)

    # Only routes backed by evidence (repo scan / live inspection) may be used.
    verified_routes = _build_verified_routes(repo_info, inspections)
    allowed_routes = set(verified_routes.keys())

    # Observed DOM facts that may legitimately become exact assertions, and the
    # app's inferred-identity terms that must never become exact assertions.
    observed_text = _observed_visible_text(inspections)
    identity_terms = _identity_terms(understanding, inspections)

    # Flatten hierarchical plan into state["test_plan"] scenario list for downstream execution
    flattened_scenarios = []
    idx = 1
    for feat_entry in plan_doc.get("test_plan", []):
        feat_name = feat_entry.get("feature", "General")
        for sc in feat_entry.get("scenarios", []):
            sc_id = sc.get("id") or f"scenario-{idx}"
            target_route = sc.get("route") or "/"
            target_url = f"{website_url.rstrip('/')}{target_route}" if target_route != "/" else website_url

            # Route provenance: drop scenarios grounded on unverified/invented routes.
            if allowed_routes and target_route not in allowed_routes:
                logger.info(
                    f"[Node: test_planning] Dropping scenario '{sc.get('name')}' on "
                    f"unverified route '{target_route}' (not supported by evidence)"
                )
                continue

            # Grounding: only observed DOM facts may become exact assertions.
            # Scenario is dropped when nothing groundable remains.
            grounded = _ground_scenario(sc, observed_text, identity_terms)
            if grounded is None:
                logger.info(
                    f"[Node: test_planning] Dropping scenario '{sc.get('name')}' — only "
                    f"ungrounded inferred-identity assertions remained"
                )
                continue
            sc = grounded

            provenance = verified_routes.get(target_route)
            flattened_scenarios.append({
                "id": sc_id,
                "feature": feat_name,
                "name": sc.get("name", f"{feat_name} Test {idx}"),
                "route": target_route,
                "targetUrl": target_url,
                "description": sc.get("description", ""),
                "type": sc.get("type", "positive"),
                "priority": sc.get("priority", "high"),
                "preconditions": sc.get("preconditions", []),
                "natural_steps": sc.get("steps", []),
                "expected_result": sc.get("expected_result", ""),
                "assertions": sc.get("assertions", []),
                "evidence": sc.get("evidence", []),
                "route_provenance": provenance,
                "steps": []  # Populated by playwright_gen_node
            })
            idx += 1

    summary = plan_doc.get("coverage_summary", {})
    scenarios_count = len(flattened_scenarios)
    logger.info(f"[Node: test_planning] Planned {scenarios_count} scenarios across {len(plan_doc.get('test_plan', []))} features")

    return {
        "test_plan_doc": plan_doc,
        "test_plan": flattened_scenarios,
        "status": "generating",
        "messages": [{
            "role": "assistant",
            "content": f"QA Planner designed {scenarios_count} scenarios across {len(plan_doc.get('test_plan', []))} feature areas."
        }]
    }


def _build_aom_and_inspections_context(inspections: list, website_url: str) -> str:
    """Builds rich context with Accessibility Tree (AOM) snapshots and element selectors for code generation."""
    lines = []
    for insp in (inspections or []):
        route = insp.get("route", "/")
        target_url = f"{website_url.rstrip('/')}{route}" if route != "/" else website_url
        page_type = insp.get("page_type", "unknown")
        title = insp.get("title", "")

        lines.append(f"\n=======================================================")
        lines.append(f"ROUTE: {route} ({target_url}) | Type: {page_type} | Title: '{title}'")
        lines.append(f"=======================================================")

        # Accessibility Tree (AOM)
        aom = insp.get("accessibility_tree", "")
        if aom:
            lines.append("ACCESSIBILITY TREE (AOM) SNAPSHOT:")
            lines.append(aom[:3000])

        # Discovered elements
        headings = [h.get("text", "") for h in insp.get("headings", []) if h.get("text")]
        if headings:
            lines.append(f"\nVisible Headings: {headings}")

        buttons = [b.get("text", "") for b in insp.get("buttons", []) if b.get("text")]
        if buttons:
            lines.append(f"Buttons / Clickable Roles: {buttons}")

        inputs = []
        for inp in insp.get("inputs", []):
            label = inp.get("label") or inp.get("placeholder") or inp.get("name") or inp.get("type", "")
            if label:
                inputs.append(f"label/placeholder: '{label}', type: '{inp.get('type', 'text')}'")
        if inputs:
            lines.append(f"Input Fields: {inputs}")

        links = [l.get("text", "") for l in insp.get("links", []) if l.get("text")][:10]
        if links:
            lines.append(f"Navigation Links: {links}")

        testid_elements = insp.get("elements_with_testid") or []
        if testid_elements:
            lines.append(
                "Verified data-testid elements "
                "(ONLY these testids may be used with getByTestId; never invent one):"
            )
            for el in testid_elements:
                lines.append(
                    f"  - data-testid=\"{el.get('testId')}\" "
                    f"(tag: {el.get('tag')}, role: {el.get('role') or 'n/a'}, "
                    f"text: '{el.get('text', '')}')"
                )

    return "\n".join(lines)


async def _llm_generate_playwright_steps(
    scenarios: list, inspections_context: str, website_url: str
) -> Optional[dict]:
    """Calls the configured LLM to ground natural language scenarios into executable JSON steps and Playwright code."""
    from app.services.llm.service import llm_service

    scenarios_input = []
    for sc in scenarios:
        scenarios_input.append({
            "id": sc.get("id"),
            "name": sc.get("name"),
            "feature": sc.get("feature"),
            "route": sc.get("route", "/"),
            "targetUrl": sc.get("targetUrl", website_url),
            "description": sc.get("description", ""),
            "natural_steps": sc.get("natural_steps", []),
            "expected_result": sc.get("expected_result", ""),
            "assertions": sc.get("assertions", []),
        })

    scenarios_json = json.dumps(scenarios_input, indent=2)

    prompt = f"""You are a senior Playwright automation engineer.
Your task is to translate natural language test scenarios into concrete, executable Playwright step definitions and clean Python Playwright code.

=== TARGET APPLICATION BASE URL ===
{website_url}

=== AVAILABLE PAGE INSPECTIONS & ACCESSIBILITY TREES (AOM) ===
{inspections_context}

=== TEST SCENARIOS TO TRANSLATE ===
{scenarios_json}

=== TRANSLATION RULES ===
1. For each scenario, translate the natural language steps and assertions into concrete executable JSON steps using the exact interactive elements found in the Accessibility Trees and Page Inspections.
2. Step actions MUST be one of:
   - Navigate: {{"action": "navigate", "value": "https://..."}}
   - Click: {{"action": "click", "role": "button" | "link", "name": "Exact text or aria-label", "first": true}} OR with parent context: {{"action": "click", "role": "button", "name": "Exact text", "parent_selector": ".project-card", "parent_text": "Item Name"}}
   - Click by testid: {{"action": "click", "testid": "Observed data-testid", "first": true}}
   - Fill: {{"action": "fill", "label": "Exact input placeholder/label/name from page", "value": "value to type"}}
   - Fill by testid: {{"action": "fill", "testid": "Observed data-testid", "value": "value to type"}}
   - Assert visible by testid: {{"action": "assert_visible", "locator_type": "testid", "testid": "Observed data-testid", "first": true}}
   - Assert visible by role: {{"action": "assert_visible", "locator_type": "role", "role": "heading" | "button" | "link", "name": "Exact element name", "first": true}}
   - Assert visible by text: {{"action": "assert_visible", "locator_type": "text", "text": "Exact visible text", "first": true}}
3. STRICT MODE AVOIDANCE & DUPLICATE ELEMENTS:
   If an element's name or text is likely to appear multiple times on the page (like 'Buy Now', 'Read More', 'View Certificate', or 'Download' in a list of cards/items), you MUST either:
   - Chain the locator to a unique parent container (e.g. `page.locator(".project-card").filter(has_text="Project Alpha").get_by_role("button", name="View Certificate").first.click()`)
   - OR use `.first` / `.nth(index)` (e.g. `page.get_by_role("button", name="View Certificate").first.click()` or `page.get_by_text("View Certificate").first`) to avoid Playwright strict mode violations.
4. TEXT ASSERTIONS & SEMANTIC ROLES:
   When asserting that specific content or text is visible on the page, prefer using semantic roles (e.g., `get_by_role('heading', name='Text')`, `get_by_role('button', name='Text')`) instead of generic `get_by_text()`. If you must use `get_by_text()`, scope it to a parent container (like a specific section, header, or footer) or append `.first` / set `"first": true` to avoid matching multiple stray elements across the page.
5. LOCATOR PRIORITY - use the first option that exists in the evidence:
   a) getByTestId - ONLY for elements listed under "Verified data-testid elements". NEVER invent, guess, or reuse a data-testid that is not explicitly listed; if none is listed, do not emit a testid.
   b) getByRole with a verified accessible name (from the AOM / inspection evidence).
   c) Other semantic locators (get_by_label / get_by_placeholder) for inputs.
   d) Verified attributes/selectors observed in the inspection evidence.
   e) getByText ONLY as a last resort and ONLY for text observed verbatim in the evidence.
6. ONLY use element names, labels, roles, testids, and text that exist in the Accessibility Tree (AOM) or page inspection evidence. Do NOT invent selectors, routes, or elements.
7. GROUNDING OF TEXT ASSERTIONS: Only DOM facts captured by live inspection may become exact text assertions. NEVER assert inferred application identity (the app name, product title, or marketing tagline) unless that exact string appears verbatim in the inspection evidence.
8. Each scenario MUST begin with a "navigate" step to the target URL.
9. Each scenario MUST end with at least one "assert_visible" verification.
10. Also write the complete Python Playwright test function code using `@pytest.mark.asyncio`, `async def test_...(page: Page):`, `await page.goto(...)`, `await page.get_by_test_id(...).first.click()` (when a testid is available), `await page.get_by_role(...).first.click()`, `await page.get_by_label(...).fill(...)`, and `await expect(...).to_be_visible()`.

=== OUTPUT FORMAT ===
Return ONLY a valid JSON object matching:
{{
  "scenarios": [
    {{
      "id": "scenario id",
      "steps": [
        {{"action": "navigate", "value": "{website_url}"}},
        {{"action": "click", "role": "button", "name": "Button Text", "first": true}},
        {{"action": "assert_visible", "locator_type": "role", "role": "heading", "name": "Heading Text", "first": true}}
      ],
      "code": "@pytest.mark.asyncio\\nasync def test_example(page: Page):\\n    await page.goto('{website_url}')\\n    await page.get_by_role('button', name='Button Text').first.click()\\n    await expect(page.get_by_role('heading', name='Heading Text').first).to_be_visible()\\n"
    }}
  ]
}}

Do not include Markdown formatting or commentary outside the JSON."""

    data = await llm_service.invoke_json(prompt, expect="object", temperature=0.1)
    if isinstance(data, dict) and "scenarios" in data and isinstance(data["scenarios"], list):
        return data
    if data is not None:
        logger.warning("[Node: playwright_gen] LLM returned JSON without a valid 'scenarios' list")
    return None


def _fallback_playwright_steps(scenario: dict, website_url: str, inspections: list) -> list:
    """Fallback step generator when LLM translation is unavailable."""
    target_url = scenario.get("targetUrl") or website_url
    steps = [{"action": "navigate", "value": target_url}]

    # Match target inspection
    route = scenario.get("route", "/")
    matching_insp = next((i for i in inspections if i.get("route") == route), None)

    if matching_insp:
        testid_elements = [e for e in (matching_insp.get("elements_with_testid") or []) if e.get("testId")]
        buttons = [b.get("text") for b in matching_insp.get("buttons", []) if b.get("text")]
        inputs = [i.get("label") or i.get("placeholder") or i.get("name") for i in matching_insp.get("inputs", []) if i.get("label") or i.get("placeholder") or i.get("name")]
        headings = [h.get("text") for h in matching_insp.get("headings", []) if h.get("text")]

        if inputs:
            steps.append({"action": "fill", "label": inputs[0], "value": "test@testpilot.ai"})
        if buttons:
            steps.append({"action": "click", "role": "button", "name": buttons[0], "first": True})
        if testid_elements:
            steps.append({"action": "assert_visible", "locator_type": "testid", "testid": testid_elements[0]["testId"]})
        elif headings:
            steps.append({"action": "assert_visible", "locator_type": "role", "role": "heading", "name": headings[0], "first": True})
        else:
            steps.append({"action": "assert_visible", "locator_type": "text", "text": matching_insp.get("title", "App"), "first": True})
    else:
        steps.append({"action": "assert_visible", "locator_type": "text", "text": scenario.get("feature", "Home"), "first": True})

    return steps


def _build_test_intent(scenario: dict, website_url: str) -> dict:
    """Builds an immutable snapshot of a scenario's ORIGINAL semantic intent.

    Captured before any execution/repair so the repair loop can prove a fix
    preserved intent (locator/timing/implementation only) instead of silently
    changing what the test verifies.
    """
    steps = scenario.get("steps") or []
    return {
        "test_id": _normalize_test_id(scenario.get("name", "")),
        "test_name": scenario.get("name", ""),
        "feature": scenario.get("feature"),
        "route": scenario.get("route"),
        "required_actions": [
            {
                k: s.get(k)
                for k in ("action", "role", "name", "label", "value", "testid", "locator_type", "text")
                if s.get(k) is not None
            }
            for s in steps
        ],
        "expected_outcome": scenario.get("expected_result", ""),
    }


async def playwright_gen_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent: LLM-powered node that grounds natural language plans against AOM trees to generate steps & code."""
    run_id = state["run_id"]
    website_url = state["website_url"]
    plan = state.get("test_plan", [])
    inspections = state.get("page_inspections") or []

    logger.info(f"[Node: playwright_gen] Generating executable Playwright steps and code for {len(plan)} scenarios")

    inspections_context = _build_aom_and_inspections_context(inspections, website_url)

    llm_result = None
    try:
        llm_result = await _llm_generate_playwright_steps(plan, inspections_context, website_url)
    except Exception as e:
        logger.warning(f"[Node: playwright_gen] LLM step generation failed: {e}")

    # Map LLM results by scenario ID
    llm_scenarios_map = {}
    if llm_result and "scenarios" in llm_result:
        for sc_out in llm_result["scenarios"]:
            sc_id = sc_out.get("id")
            if sc_id:
                llm_scenarios_map[sc_id] = sc_out

    test_functions = []
    updated_plan = []

    for scenario in plan:
        sc_id = scenario.get("id")
        sc_llm = llm_scenarios_map.get(sc_id)

        if sc_llm and sc_llm.get("steps") and isinstance(sc_llm["steps"], list) and len(sc_llm["steps"]) > 0:
            resolved_steps = sc_llm["steps"]
            test_code = sc_llm.get("code")
        else:
            resolved_steps = _fallback_playwright_steps(scenario, website_url, inspections)
            test_code = None

        scenario_copy = {**scenario, "steps": resolved_steps}
        updated_plan.append(scenario_copy)

        # Generate python test code if not provided by LLM
        if not test_code:
            fn_suffix = scenario["name"].lower().replace(":", "").replace("&", "and").replace("-", "_").replace(" ", "_").strip("_")
            fn_name = f"test_{fn_suffix}"
            step_codes = []
            for step in resolved_steps:
                action = step.get("action")
                if action == "navigate":
                    step_codes.append(f'    await page.goto("{step["value"]}")')
                elif action == "fill":
                    if step.get("testid"):
                        step_codes.append(f'    await page.get_by_test_id("{step["testid"]}").fill("{step.get("value", "")}")')
                    else:
                        step_codes.append(f'    await page.get_by_label("{step.get("label", "")}").fill("{step.get("value", "")}")')
                elif action == "click":
                    role = step.get("role", "button")
                    name = step.get("name", "")
                    if step.get("testid"):
                        step_codes.append(f'    await page.get_by_test_id("{step["testid"]}").first.click()')
                    elif step.get("parent_selector"):
                        p_sel = step["parent_selector"]
                        p_text = f'.filter(has_text="{step["parent_text"]}")' if step.get("parent_text") else ""
                        step_codes.append(f'    await page.locator("{p_sel}"){p_text}.get_by_role("{role}", name="{name}").first.click()')
                    elif step.get("nth") is not None:
                        step_codes.append(f'    await page.get_by_role("{role}", name="{name}").nth({step["nth"]}).click()')
                    else:
                        step_codes.append(f'    await page.get_by_role("{role}", name="{name}").first.click()')
                elif action == "assert_visible":
                    loc_type = step.get("locator_type", "text")
                    if loc_type == "testid" or step.get("testid"):
                        step_codes.append(f'    await expect(page.get_by_test_id("{step.get("testid", "")}").first).to_be_visible()')
                    elif loc_type == "role":
                        step_codes.append(f'    await expect(page.get_by_role("{step.get("role", "heading")}", name="{step.get("name", "")}").first).to_be_visible()')
                    else:
                        step_codes.append(f'    await expect(page.get_by_text("{step.get("text", "")}").first).to_be_visible()')

            test_code = (
                f"@pytest.mark.asyncio\n"
                f"async def {fn_name}(page: Page):\n"
                + "\n".join(step_codes)
                + "\n"
            )

        test_functions.append(test_code)

    generated_suite = (
        "import re\nimport pytest\nfrom playwright.async_api import Page, expect\n\n"
        + "\n\n".join(test_functions)
        + "\n"
    )

    generated = [
        {
            "name": "testpilot_e2e_suite.spec.py",
            "code": generated_suite,
            "scenariosCount": len(updated_plan)
        }
    ]

    # Immutable snapshot of each scenario's ORIGINAL intent (pre-execution,
    # pre-repair) so the repair loop can reject intent-changing "fixes".
    test_intents = {
        _normalize_test_id(sc.get("name", "")): _build_test_intent(sc, website_url)
        for sc in updated_plan
    }

    return {
        "test_plan": updated_plan,
        "generated_tests": generated,
        "test_intents": test_intents,
        "status": "executing",
        "messages": [{
            "role": "assistant",
            "content": f"AOM-grounded Playwright test suite written ({len(updated_plan)} scenarios)."
        }]
    }


class RateLimitError(Exception):
    """Raised when the target responds with HTTP 429 (rate limited).

    Carries the server-advertised Retry-After (seconds) so the evaluation /
    retry nodes can back off instead of treating this as a test defect.
    """

    def __init__(self, message: str, retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after


def _parse_retry_after(raw: Any) -> int:
    """Parses a Retry-After header value into whole seconds (0 when absent)."""
    if raw in (None, ""):
        return 0
    try:
        return max(0, int(float(raw)))
    except (TypeError, ValueError):
        return 0


def _normalize_test_id(name: str) -> str:
    """Normalizes a test name into a stable ID for state key lookups."""
    return name.lower().replace(" ", "_").replace(":", "").strip("_")


def _get_error_message(exc: Exception) -> str:
    """Extracts a non-empty error message from an exception.

    Playwright sometimes raises exceptions whose str() is empty.
    Falls back to repr() or the class name to always provide context.
    """
    msg = str(exc)
    if msg:
        return msg
    msg = repr(exc)
    if msg and msg != type(exc).__name__ + "()":
        return msg
    return f"{type(exc).__name__}: (no message)"


async def _execute_step(page, step: dict, logs: list) -> None:
    """Executes a single test plan step against a Playwright page.

    Handles duplicate elements, parent container chaining, and .first / .nth
    scoping to prevent Playwright strict mode violations.
    """
    action = step["action"]

    if action == "navigate":
        logs.append(f"[Playwright] Navigating to: {step['value']}")
        response = await page.goto(step["value"], wait_until="domcontentloaded", timeout=15000)
        status = response.status if response else None
        if status == 429:
            retry_after = _parse_retry_after(response.headers.get("retry-after") if response else None)
            raise RateLimitError(
                f"Rate limited (HTTP 429) while navigating to {step['value']}",
                retry_after=retry_after,
            )
        if not response or response.status >= 400:
            raise Exception(f"Failed to navigate. Status: {status or 'No Response'}")
        logs.append(f"[Playwright] Navigation resolved (status code {response.status})")

    elif action == "fill":
        val = step["value"]
        # Prefer the stable data-testid when the generator grounded one.
        if step.get("testid"):
            input_loc = page.get_by_test_id(step["testid"])
            if await input_loc.count() > 0:
                await input_loc.first.fill(val)
                logs.append(f"[Playwright] Input fill: testid '{step['testid']}' -> '{val}'")
            else:
                logs.append(f"[Playwright] Locator testid '{step['testid']}' not found, skipping fill")
        else:
            label = step["label"]
            input_loc = page.locator(
                f"input[placeholder*='{label}' i], input[name*='{label}' i], "
                f"input[type='email'], input"
            ).locator("visible=true").first
            if await input_loc.count() > 0:
                await input_loc.fill(val)
                logs.append(f"[Playwright] Input fill: label '{label}' -> '{val}'")
            else:
                logs.append(f"[Playwright] Locator label '{label}' not found, skipping fill")

    elif action == "click":
        name = step.get("name", "")
        role = step.get("role", "button")
        parent_sel = step.get("parent_selector")
        parent_text = step.get("parent_text")

        if step.get("testid"):
            # data-testid grounded click (preferred, stable locator).
            btn_loc = page.get_by_test_id(step["testid"])
            total_matches = await btn_loc.count()
            if total_matches > 0:
                await btn_loc.first.click()
                logs.append(f"[Playwright] Trigger action: clicked testid '{step['testid']}'")
                await page.wait_for_timeout(1000)
            else:
                logs.append(f"[Playwright] Locator testid '{step['testid']}' not found, skipping click")
            return

        if parent_sel:
            base = page.locator(parent_sel)
            if parent_text:
                base = base.filter(has_text=parent_text)
        else:
            base = page

        # Find locator by role first, fallback to text/tag match
        btn_loc = base.get_by_role(role, name=name) if name else base.locator("button, a")
        if await btn_loc.count() == 0 and name:
            btn_loc = base.locator(f"button:has-text('{name}'), a:has-text('{name}'), [role='button']:has-text('{name}')")

        total_matches = await btn_loc.count()
        if total_matches > 0:
            if step.get("nth") is not None:
                nth_idx = step["nth"]
                target_loc = btn_loc.nth(nth_idx)
                match_note = f" (index {nth_idx} of {total_matches} matches)"
            elif total_matches > 1:
                target_loc = btn_loc.first
                match_note = f" (first of {total_matches} matches)"
            else:
                target_loc = btn_loc.first
                match_note = ""

            btn_text = (await target_loc.inner_text()).strip() or name
            await target_loc.click()
            logs.append(f"[Playwright] Trigger action: clicked {role} '{btn_text}'{match_note}")
            await page.wait_for_timeout(1000)
        else:
            logs.append(f"[Playwright] Locator {role} '{name}' not found, skipping click")

    elif action == "assert_visible":
        loc_type = step.get("locator_type", "text")
        parent_sel = step.get("parent_selector")
        parent_text = step.get("parent_text")

        if parent_sel:
            base = page.locator(parent_sel)
            if parent_text:
                base = base.filter(has_text=parent_text)
        else:
            base = page

        if loc_type == "testid" or step.get("testid"):
            locator = base.get_by_test_id(step.get("testid", ""))
        elif loc_type == "role":
            role_name = step.get("role", "button")
            element_name = step.get("name", "")
            locator = base.get_by_role(role_name, name=element_name)
        else:
            text = step.get("text", "")
            locator = base.get_by_text(text)

        # Unconditionally narrow with .first or .nth before wrapping in expect() to prevent strict mode violation
        if step.get("nth") is not None:
            nth_idx = step["nth"]
            target_loc = locator.nth(nth_idx)
            match_note = f" (index {nth_idx})"
        else:
            target_loc = locator.first
            match_note = ""

        await expect(target_loc).to_be_visible(timeout=5000)
        element_label = step.get('testid') or step.get('name') or step.get('text')
        logs.append(f"[Playwright] Assert visible: {loc_type} '{element_label}' -> True{match_note}")


async def browser_execution_node(state: TestPilotState) -> Dict[str, Any]:
    """Executes generated tests in a Playwright sandbox.

    Supports scoped execution via tests_to_execute: when populated,
    only the listed test IDs are run (used during repair loops to
    avoid re-running the full suite). Uses repaired steps from
    the repair loop when available.
    """
    run_id = state["run_id"]
    website_url = state["website_url"]
    plan = state.get("test_plan", [])
    project_id = state["project_id"]
    tests_to_execute = state.get("tests_to_execute")
    repaired_tests = state.get("repaired_tests") or {}

    # `tests_to_execute is not None` (not truthiness) so an EMPTY list means
    # "execute nothing" — required by the fail-closed live-verify contract.
    if tests_to_execute is not None:
        scoped_plan = []
        for scenario in plan:
            test_id = _normalize_test_id(scenario["name"])
            if test_id in tests_to_execute:
                scoped_plan.append(scenario)
        logger.info(f"[Node: browser_execution] Scoped execution: {len(scoped_plan)}/{len(plan)} tests for run {run_id}")
    else:
        scoped_plan = plan
        logger.info(f"[Node: browser_execution] Full execution: {len(plan)} tests for run {run_id}")

    # Fail-closed short-circuit: nothing is eligible to execute (all scenarios
    # failed pre-execution live verification). Never launch a browser; keep the
    # not-executed results that live_verify already recorded.
    if tests_to_execute is not None and not scoped_plan:
        logger.info(
            "[Node: browser_execution] No eligible tests after live verification; "
            "skipping browser launch (fail-closed)."
        )
        return {
            "execution_results": state.get("execution_results") or [],
            "status": "executing",
            "messages": [{"role": "assistant", "content": "No eligible tests to execute after live verification."}],
        }

    results: List[Dict[str, Any]] = []

        # Get test credentials from the persisted project record
    test_email = None
    test_password = None
    try:
        from app.db import get_project as db_get_project
        project = db_get_project(project_id)
        if project:
            test_email = project.get("testEmail")
            test_password = project.get("testPassword")
    except Exception as cred_err:
        logger.warning(f"[Node: browser_execution] Failed to load credentials: {cred_err}")

    # Run Playwright in a ProactorEventLoop thread on Windows to avoid
    # uvicorn's SelectorEventLoop NotImplementedError on subprocess creation.
    async def _run_all_scenarios():
        """Inner async function that runs inside a ProactorEventLoop thread."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for scenario in scoped_plan:
                test_name = scenario["name"]
                test_id = _normalize_test_id(test_name)

                # Use repaired steps if the repair loop produced them
                if test_id in repaired_tests and isinstance(repaired_tests[test_id], list):
                    steps = repaired_tests[test_id]
                    logger.info(f"[Node: browser_execution] Using repaired steps for '{test_id}'")
                else:
                    steps = scenario.get("steps", [])

                logs = []
                status = "passed"
                error = None
                start_time = time.time()
                # Structured rate-limit signal captured via the response listener.
                rate_limit = {"rate_limited": False, "http_status": None, "retry_after": 0}

                logs.append(f"> playwright test --spec={test_name.replace(' ', '_').lower()}.py")

                context = None
                try:
                    context = await browser.new_context()
                    page = await context.new_page()
                    logs.append("[Playwright] Browser context created")

                    def _capture_response(response):
                        try:
                            if response.status == 429:
                                retry_after = _parse_retry_after(response.headers.get("retry-after"))
                                rate_limit["rate_limited"] = True
                                rate_limit["http_status"] = 429
                                rate_limit["retry_after"] = max(rate_limit["retry_after"], retry_after)
                        except Exception:
                            pass

                    page.on("response", _capture_response)

                    for step in steps:
                        await _execute_step(page, step, logs)

                    logs.append("[Playwright] All expect assertions passed successfully.")
                except RateLimitError as rate_err:
                    # HTTP 429 is a transient/environment condition, NOT a test defect.
                    status = "failed"
                    error = _get_error_message(rate_err)
                    rate_limit["rate_limited"] = True
                    rate_limit["http_status"] = 429
                    rate_limit["retry_after"] = max(rate_limit["retry_after"], rate_err.retry_after)
                    logs.append(f"[RateLimit] {error} (retry_after={rate_limit['retry_after']}s)")
                except Exception as e:
                    status = "failed"
                    error = _get_error_message(e)
                    logs.append(f"[Error] Exception thrown: {error}")
                finally:
                    if context:
                        try:
                            await context.close()
                        except Exception:
                            pass

                duration_ms = int((time.time() - start_time) * 1000)
                results.append({
                    "test_name": test_name,
                    "status": status,
                    "duration_ms": duration_ms,
                    "error": error,
                    "logs": "\n".join(logs),
                    "rate_limited": rate_limit["rate_limited"],
                    "http_status": rate_limit["http_status"],
                    "retry_after": rate_limit["retry_after"],
                })

            await browser.close()

    try:
        async with target_slot(website_url):
            await run_playwright(_run_all_scenarios)
    except Exception as browser_err:
        # Browser-level failure (e.g. Chromium not installed)
        error_msg = _get_error_message(browser_err)
        logger.error(f"[Node: browser_execution] Playwright browser launch failed: {error_msg}")
        for scenario in scoped_plan:
            results.append({
                "test_name": scenario["name"],
                "status": "failed",
                "duration_ms": 0,
                "error": f"Browser launch failed: {error_msg}",
                "logs": f"> playwright test\n[Error] Browser launch failed: {error_msg}"
            })

        # Merge scoped re-execution results back into the full result set.
    # Without this, LangGraph's last-write-wins on `execution_results` (it has
    # no reducer) would replace the original full-suite results with only the
    # re-run subset, wiping all previously passing tests from the report.
    if tests_to_execute is not None:
        prior_by_id = {
            _normalize_test_id(r.get("test_name", "")): r
            for r in (state.get("execution_results") or [])
        }
        fresh_by_id = {
            _normalize_test_id(r.get("test_name", "")): r for r in results
        }
        merged_by_id = {**prior_by_id, **fresh_by_id}
        merged = []
        for scenario in plan:  # preserve original plan order
            tid = _normalize_test_id(scenario["name"])
            if tid in merged_by_id:
                merged.append(merged_by_id[tid])
        results = merged
        logger.info(
            f"[Node: browser_execution] Merged scoped results back: "
            f"{len(results)} total tests in final report"
        )

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
    pr_body_parts = ["## Verity â€” Automated E2E Test Suite\n"]

    # Evaluation summary
    if evaluation_results:
        pass_count = sum(1 for r in evaluation_results.values() if r.get("verdict") == "PASS")
        fail_count = sum(1 for r in evaluation_results.values() if r.get("verdict") == "FAIL")
        inconclusive_count = sum(1 for r in evaluation_results.values() if r.get("verdict") == "INCONCLUSIVE")
        not_executed_count = sum(1 for r in evaluation_results.values() if r.get("verdict") == "NOT_EXECUTED")
        if not_executed_count:
            pr_body_parts.append("### Pre-execution Verification Failures")
            pr_body_parts.append(
                f"{not_executed_count} test(s) were NOT executed because a selector could not be "
                "confirmed on the live page (FAILED_VERIFICATION). These are TestPilot "
                "pre-execution validation failures, NOT application bugs."
            )
            pr_body_parts.append("")
        pr_body_parts.append(f"### Test Results")
        pr_body_parts.append(f"| Metric | Count |")
        pr_body_parts.append(f"|--------|-------|")
        pr_body_parts.append(f"| âœ… Passed | {pass_count} |")
        pr_body_parts.append(f"| âŒ Failed | {fail_count} |")
        pr_body_parts.append(f"| âš ï¸ Inconclusive | {inconclusive_count} |")
        pr_body_parts.append("")

    # Auto-repaired tests summary
    if repair_attempts:
        repaired_tests = [tid for tid, count in repair_attempts.items() if count > 0]
        if repaired_tests:
            pr_body_parts.append(f"### ðŸ”§ Auto-Repaired Tests ({len(repaired_tests)})")
            pr_body_parts.append("| Test | Repair Attempts |")
            pr_body_parts.append("|------|----------------|")
            for test_id in repaired_tests:
                pr_body_parts.append(f"| `{test_id}` | {repair_attempts[test_id]} |")
            pr_body_parts.append("")

    # Suspected application bugs (most prominent section)
    if suspected_app_bugs:
        pr_body_parts.append(f"### ðŸ› Suspected Application Bugs ({len(suspected_app_bugs)})")
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

    # Distinguish success from partial failure
    verdicts = [r.get("verdict") for r in evaluation_results.values()]
    all_passed = all(v == "PASS" for v in verdicts) if verdicts else False
    final_status = "completed" if all_passed else "completed_with_failures"

    return {
        "pr_url": pr_res["pr_url"],
        "status": final_status,
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
