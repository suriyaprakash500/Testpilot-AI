"""App + Feature Analysis Node (merged).

This node consolidates two previously-sequential LLM nodes that operated on
the exact same evidence:

* ``app_understanding_node``  — reasoned about the application as a whole
  (name, type, purpose, user flows, testable features, risks).
* ``feature_segregation_node`` — mapped those features onto concrete routes
  and DOM elements (routes, page types, suggested test actions).

Both consumed the *same* inputs (live ``page_inspections`` + ``repo_analysis``)
and their outputs were each consumed only by ``test_planning_node``. The second
node's only extra input was the first node's own output, so the two are now
produced by a single LLM call.

To keep the rest of the pipeline unchanged, the node still writes the two
existing state keys — ``app_understanding`` and ``features`` — so
``test_planning_node`` and the state schema behave exactly as before.

A deterministic rule-based fallback (no LLM) is preserved for both halves.
"""

import logging
from typing import Any, Dict, List, Tuple

from app.graph.state import TestPilotState

logger = logging.getLogger("graph-app-feature-analysis")


def _build_evidence(inspections: list, repo_info: dict) -> str:
    """Assembles the shared evidence used to reason about the application.

    Combines repository basics (framework, language, discovered routes) with a
    detailed per-page view of the concrete elements found during live DOM
    inspection. This is the union of the two prompts it replaces.
    """
    lines: List[str] = []

    framework = repo_info.get("framework", "Unknown")
    language = repo_info.get("language", "Unknown")
    routes = repo_info.get("routes", [])
    lines.append(f"Framework: {framework}, Language: {language}")
    lines.append(f"Discovered routes: {routes}")

    lines.append("\n--- INSPECTED PAGES ---")
    for insp in inspections:
        route = insp.get("route", "/")
        page_type = insp.get("page_type", "unknown")
        title = insp.get("title", "")

        headings = [h.get("text", "") for h in insp.get("headings", []) if h.get("text")]
        buttons = [b.get("text", "") for b in insp.get("buttons", []) if b.get("text")]
        inputs = []
        for inp in insp.get("inputs", []):
            label = inp.get("label") or inp.get("placeholder") or inp.get("name") or inp.get("type", "")
            inputs.append(f"{label} [{inp.get('type', 'text')}]")
        forms_count = len(insp.get("forms", []))
        tables = insp.get("tables", [])
        cards_count = len(insp.get("cards", []))
        links = [lk.get("text", "") for lk in insp.get("links", []) if lk.get("text")][:10]

        page_desc = f"\nRoute: {route} (type: {page_type}, title: '{title}')"
        if headings:
            page_desc += f"\n  Headings: {headings[:6]}"
        if buttons:
            page_desc += f"\n  Buttons: {buttons[:10]}"
        if inputs:
            page_desc += f"\n  Inputs: {inputs[:8]}"
        if forms_count:
            page_desc += f"\n  Forms: {forms_count}"
        if tables:
            table_info = [
                f"table({t.get('rowsCount', t.get('rows', 0))} rows, headers={t.get('headers', [])})"
                for t in tables[:3]
            ]
            page_desc += f"\n  Tables: {table_info}"
        if cards_count:
            page_desc += f"\n  Cards: {cards_count}"
        if links:
            page_desc += f"\n  Links: {links}"

        lines.append(page_desc)

    return "\n".join(lines)


async def _llm_analyze_app_features(evidence: str) -> Dict[str, Any]:
    """Single LLM call producing both the app-level understanding and the feature map."""
    from app.services.llm.service import llm_service

    prompt = f"""You are a senior QA engineer analyzing a web application before writing tests.

Below is structured evidence collected from the live application DOM and repository analysis.

=== APPLICATION EVIDENCE ===
{evidence}
=== END EVIDENCE ===

Produce ONE JSON object with exactly two top-level keys: "app" and "features".

1. "app": an object describing the application as a whole with:
   - "name": Short name for this application (infer from title, repo, or domain).
   - "type": One of: "e-commerce", "saas-dashboard", "content-site", "admin-panel", "portfolio", "social-platform", "developer-tool", "form-app", "other".
   - "purpose": One sentence describing what this application does for its users.
   - "user_flows": Array of 3-7 strings, each a distinct user workflow.
   - "testable_features": Array of objects, each with:
       * "name": Feature name (e.g. "User Authentication", "Product Search")
       * "importance": "critical", "high", or "medium"
       * "evidence": Brief explanation of why this feature exists (which DOM elements or signals prove it)
   - "critical_paths": Array of 2-4 end-to-end flows that must never break.
   - "risk_areas": Array of 1-3 areas likely to have bugs (forms without validation, complex state, etc).

2. "features": an object grouping the discovered pages into testable feature areas where:
   - Each key is a feature name (e.g. "User Authentication", "Product Catalog", "Navigation").
   - Each value is an array of route entries that belong to that feature.
   - Each route entry is an object with:
       * "route": the route path (e.g. "/login")
       * "page_type": the page type classification
       * "test_actions": array of 2-5 concrete test actions. Each action is an object with:
           - "description": What this action tests (e.g. "Submit login form with invalid email")
           - "element_type": "button" | "input" | "link" | "heading" | "table" | "card" | "text"
           - "element_identifier": The actual button text, input label, heading text, etc. found on the page
           - "action": "click" | "fill" | "assert_visible" | "assert_text" | "navigate"

Rules:
- Only reference elements that actually exist in the inspected page data above. Do NOT invent elements or text.
- Each feature should have at least one route.
- A route can appear in multiple features if it serves multiple purposes.
- Prioritize critical and high-importance features.
- Include a "Page Navigation" feature if there are 2+ routes.

Return ONLY the JSON object. No markdown fences, no explanation."""

    data = await llm_service.invoke_json(prompt, expect="object")
    if isinstance(data, dict) and ("app" in data or "features" in data):
        return data
    if data is not None:
        logger.warning("[Node: app_feature_analysis] LLM returned JSON without 'app'/'features' keys")
    return None


def _map_app(app_out: dict) -> Dict[str, Any]:
    """Normalizes the LLM 'app' object into the existing app_understanding schema."""
    return {
        "app_name": app_out.get("name") or app_out.get("app_name") or "Web Application",
        "app_type": app_out.get("type") or app_out.get("app_type") or "other",
        "purpose": app_out.get("purpose", ""),
        "user_flows": app_out.get("user_flows", []),
        "testable_features": app_out.get("testable_features", []),
        "critical_paths": app_out.get("critical_paths", []),
        "risk_areas": app_out.get("risk_areas", []),
    }


def _rule_based_understanding(inspections: list, repo_info: dict) -> Dict[str, Any]:
    """Fallback: deterministic app understanding when the LLM is unavailable."""
    app_name = (
        repo_info.get("repo_url", "").split("/")[-1].replace(".git", "").replace("-", " ").title()
        or "Web App"
    )

    all_buttons: List[str] = []
    all_inputs: List[str] = []
    page_types = set()

    for insp in inspections:
        page_types.add(insp.get("page_type", "unknown"))
        for b in insp.get("buttons", []):
            if b.get("text"):
                all_buttons.append(b["text"])
        for inp in insp.get("inputs", []):
            label = inp.get("label") or inp.get("placeholder") or inp.get("name")
            if label:
                all_inputs.append(label)

    testable_features = []
    if "authentication_page" in page_types:
        testable_features.append({"name": "User Authentication", "importance": "critical", "evidence": "Login/signup page with password inputs detected"})
    if "dashboard" in page_types:
        testable_features.append({"name": "Dashboard Overview", "importance": "high", "evidence": "Dashboard page with metrics/summary detected"})
    if "product_listing" in page_types or "product_detail" in page_types:
        testable_features.append({"name": "Product Catalog", "importance": "high", "evidence": "Product listing/detail pages detected"})
    if "contact_page" in page_types or "form_page" in page_types:
        testable_features.append({"name": "Form Submission", "importance": "high", "evidence": "Form page with input fields detected"})
    if "settings_page" in page_types:
        testable_features.append({"name": "Settings Management", "importance": "medium", "evidence": "Settings/profile page detected"})
    if len(inspections) > 1:
        testable_features.append({"name": "Page Navigation", "importance": "high", "evidence": f"{len(inspections)} routes discovered with successful page loads"})

    user_flows = []
    if any("sign" in b.lower() or "log" in b.lower() for b in all_buttons):
        user_flows.append("User signs in with credentials")
    if any("cart" in b.lower() or "buy" in b.lower() or "add" in b.lower() for b in all_buttons):
        user_flows.append("User adds items to cart")
    if any("submit" in b.lower() or "send" in b.lower() for b in all_buttons):
        user_flows.append("User submits a form")
    if any("save" in b.lower() or "update" in b.lower() for b in all_buttons):
        user_flows.append("User saves settings or updates")
    if not user_flows:
        user_flows = ["User navigates through application pages"]

    return {
        "app_name": app_name,
        "app_type": "other",
        "purpose": f"Web application with {len(inspections)} pages providing {', '.join(pt for pt in page_types if pt != 'unknown')} functionality.",
        "user_flows": user_flows,
        "testable_features": testable_features,
        "critical_paths": [f"Navigation across {len(inspections)} routes loads without errors"],
        "risk_areas": ["Forms without visible validation feedback"],
    }


def _rule_based_segregation(inspections: list) -> Dict[str, List[Dict[str, Any]]]:
    """Fallback: deterministic feature segregation when the LLM is unavailable."""
    feature_groups: Dict[str, List[Dict[str, Any]]] = {}

    type_to_feature = {
        "authentication_page": "User Authentication",
        "dashboard": "Dashboard",
        "product_listing": "Product Catalog",
        "product_detail": "Product Detail",
        "settings_page": "Settings",
        "contact_page": "Contact Form",
        "form_page": "Form Submission",
        "crud_table": "Data Management",
        "landing_page": "Homepage",
    }

    for insp in inspections:
        route = insp.get("route", "/")
        page_type = insp.get("page_type", "unknown")
        buttons = [b.get("text", "") for b in insp.get("buttons", []) if b.get("text")]
        inputs = []
        for inp in insp.get("inputs", []):
            label = inp.get("label") or inp.get("placeholder") or inp.get("name")
            if label:
                inputs.append(label)

        feature_name = type_to_feature.get(page_type, f"Page: {route}")

        test_actions = [{
            "description": f"Navigate to {route} and verify page loads",
            "element_type": "text",
            "element_identifier": insp.get("title", route),
            "action": "navigate",
        }]
        for btn_text in buttons[:3]:
            test_actions.append({
                "description": f"Click '{btn_text}' button",
                "element_type": "button",
                "element_identifier": btn_text,
                "action": "click",
            })
        for input_label in inputs[:3]:
            test_actions.append({
                "description": f"Fill '{input_label}' input field",
                "element_type": "input",
                "element_identifier": input_label,
                "action": "fill",
            })

        feature_groups.setdefault(feature_name, []).append({
            "route": route,
            "page_type": page_type,
            "test_actions": test_actions[:5],
        })

    return feature_groups


def _rule_based_app_features(
    inspections: list, repo_info: dict
) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
    """Deterministic fallback producing both outputs."""
    understanding = _rule_based_understanding(inspections, repo_info)
    features = _rule_based_segregation(inspections)
    return understanding, features


async def app_feature_analysis_node(state: TestPilotState) -> Dict[str, Any]:
    """Agent Node: reasons about the application AND maps features to routes.

    Merges the former ``app_understanding_node`` + ``feature_segregation_node``
    into a single LLM call, while preserving both existing state outputs
    (``app_understanding`` and ``features``) for downstream consumers.
    """
    run_id = state["run_id"]
    repo_info = state.get("repo_analysis") or {}
    inspections = state.get("page_inspections") or []

    logger.info(
        f"[Node: app_feature_analysis] Analyzing application & segmenting features "
        f"for run {run_id} ({len(inspections)} inspections)"
    )

    evidence = _build_evidence(inspections, repo_info)

    llm_result = None
    try:
        llm_result = await _llm_analyze_app_features(evidence)
    except Exception as e:
        logger.warning(f"[Node: app_feature_analysis] LLM analysis failed: {e}. Falling back to rule-based.")

    llm_app = llm_result.get("app") if isinstance(llm_result, dict) else None
    llm_features = llm_result.get("features") if isinstance(llm_result, dict) else None

    if isinstance(llm_app, dict) and llm_app:
        understanding = _map_app(llm_app)
        logger.info(
            f"[Node: app_feature_analysis] LLM identified app as '{understanding.get('app_name')}' "
            f"({understanding.get('app_type')})"
        )
    else:
        understanding = _rule_based_understanding(inspections, repo_info)
        logger.info("[Node: app_feature_analysis] Using rule-based app understanding fallback")

    if isinstance(llm_features, dict) and llm_features:
        features = llm_features
        logger.info(f"[Node: app_feature_analysis] LLM produced {len(features)} feature groups")
    else:
        features = _rule_based_segregation(inspections)
        logger.info(f"[Node: app_feature_analysis] Using rule-based feature segregation ({len(features)} groups)")

    return {
        "app_understanding": understanding,
        "features": features,
        "status": "app_understanding",
        "messages": [{
            "role": "assistant",
            "content": (
                f"Application understood: {understanding.get('app_name', 'App')} "
                f"({understanding.get('app_type', 'web app')}) — "
                f"{len(understanding.get('testable_features', []))} testable features "
                f"mapped across {len(features)} feature groups."
            ),
        }],
    }